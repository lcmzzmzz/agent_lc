"""
EcomResearcher 运行入口与文件输出（含按次全链路日志文件）。

【正经注释】
run_ecommerce_research 是对外统一入口：构造初始状态 → 跑完整 graph →
把报告 / 审计日志 / 质量检查分别写成 .md / .json 文件。
每次研究还会在 logs/ecommerce/ 下创建一个独立 log 文件，文件名为
<时间戳>_<关键词>.log，绑定到 multi_agents.ecommerce logger，
捕获整条链路（graph 阶段 / 各 Agent / LLM 调用）的 INFO/WARNING/ERROR，
便于事后排查。default_search_fn 复用 GPT Researcher 默认检索器，失败降级为空结果。

【大白话注释】
一键启动按钮：输入品类，跑完整条流程，存报告/日志/质检三类文件。
另外每次跑都会单独生成一个日志文件（名字是"时间+关键词"），
全程每一步都记进去，出问题能回看。
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import re
from pathlib import Path
from typing import Any

from multi_agents.ecommerce.config import get_budget_config
from multi_agents.ecommerce.evaluation import build_evaluation_summary
from multi_agents.ecommerce.graph import ProgressFn, run_ecommerce_graph
from multi_agents.ecommerce.llm_helper import LlmFn
from multi_agents.ecommerce.runtime.budget_manager import BudgetManager
from multi_agents.ecommerce.runtime.policy_guard import (
    PolicyViolation,
    validate_research_request,
)
from multi_agents.ecommerce.state import EcommerceResearchState, create_initial_state
from multi_agents.ecommerce.tools.mcp_adapter import McpSearchFn, make_mcp_augmented_search_fn
from multi_agents.ecommerce.tools.product_search import SearchFn

# 全链路日志统一走这个 logger；各子模块 logger（logging.getLogger("multi_agents.ecommerce.xxx")）
# 会自动 propagate 冒泡到这里，所以只在这挂一个 handler 就能收整条链路的日志
logger = logging.getLogger("multi_agents.ecommerce")

_SLUG_RE = re.compile(r"\W+", flags=re.UNICODE)  # 匹配「非单词字符」（空格/标点等）→ slugify 用来切成短横
_LOG_FORMAT = logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s")  # 日志行格式：时间 级别 logger名 - 消息


def slugify(value: str) -> str:
    """把品类关键词转成安全的文件名片段（兼容中英文，无结果时回退）。"""
    slug = _SLUG_RE.sub("-", value.lower()).strip("-")  # 非单词字符→短横，如"便携 榨汁机!"→"便携-榨汁机"
    return slug or "ecommerce-research"   # 全是符号时回退，保证文件名非空


async def default_search_fn(query: str, max_results: int) -> list[dict[str, Any]]:
    """复用 GPT Researcher 默认检索器；任何异常都降级为空结果。

    检索器是同步阻塞 IO，用 asyncio.to_thread 放到线程池，
    让三个研究 Agent 的多次检索能真正并发执行。
    """

    def _sync_search() -> list[dict[str, Any]]:
        # 延迟 import：只在真正检索时才依赖 gpt_researcher，避免 runner 一导入就强耦合
        try:
            from gpt_researcher.actions.retriever import get_default_retriever

            retriever_cls = get_default_retriever()  # 例如 TavilySearch 类
            retriever = retriever_cls(query=query)
            return retriever.search(max_results=max_results) or []
        except Exception as exc:  # 检索失败不应中断主流程 → 降级返回空，让上游走"无证据"分支
            logger.warning(f"[search] 默认检索失败 query='{query}': {exc}")
            return []

    # 关键：retriever.search() 是【同步阻塞】调用，直接 await 会卡住事件循环；
    # asyncio.to_thread 把它丢到线程池 → trend/competitor/review 三路的多次检索才能【真正并发】
    return await asyncio.to_thread(_sync_search)


def _setup_run_log(query: str) -> tuple[logging.FileHandler, Path]:
    """为本次研究创建独立 log 文件 handler，文件名 = 时间戳_关键词.log。"""
    log_dir = Path("logs/ecommerce")
    log_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"{ts}_{slugify(query)}.log"   # 每次研究一个独立日志文件（时间戳保证不重名）
    handler = logging.FileHandler(log_path, encoding="utf-8")  # 出口：往这个文件写（utf-8 支持中文）
    handler.setLevel(logging.INFO)                      # 闸门②（handler 级别）：只记 INFO+
    handler.setFormatter(_LOG_FORMAT)                   # 套上行格式
    ecommerce_logger = logging.getLogger("multi_agents.ecommerce")
    ecommerce_logger.addHandler(handler)                # 挂到父 logger → 子模块日志靠 propagate 冒泡进来
    # 确保该 logger 不会因自身 level 过滤掉 INFO
    if ecommerce_logger.level == logging.NOTSET or ecommerce_logger.level > logging.INFO:
        ecommerce_logger.setLevel(logging.INFO)         # 闸门①（logger 级别）：默认 WARNING 会先把 INFO 拦掉，必须主动开
    return handler, log_path                            # 返回 handler：结束时 _teardown_run_log 要拿它摘掉


def _teardown_run_log(handler: logging.FileHandler) -> None:
    ecommerce_logger = logging.getLogger("multi_agents.ecommerce")
    ecommerce_logger.removeHandler(handler)   # 摘掉本次 handler → 之后的日志不再写这个文件
    handler.flush()                           # 刷盘：把缓冲区剩余内容写进文件
    handler.close()                           # 关文件句柄，防泄漏


def _resolve_search_fn(search_fn: SearchFn | None) -> SearchFn:
    """选择检索源：显式传入优先（测试/程序化用），否则 Tavily 默认检索器。

    （曾支持 ECOMMERCE_SEARCH_BACKEND=apify 走 apify_search.py，但该模块字段名与
    actor schema 不匹配且零测试，正确实现已在 review_scraper 的两步链路里，故移除。）
    """
    if search_fn is not None:
        return search_fn      # 调用方显式传了（测试传 fake_search、程序化传自定义）→ 用它
    return default_search_fn  # 没传 → 用默认 Tavily 检索


def _write_json(path: Path, payload: Any) -> None:
    """统一 JSON 落盘：utf-8 + 缩进2 + 保留中文，消除重复 json.dumps(...).write_text(...) 样板。"""
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


async def run_ecommerce_research(
    *,                                  # 关键字参数分隔符：调用时必须写参数名
    query: str,                         # 选品关键词（如"便携榨汁机"）
    target_market: str = "US",          # 目标市场（影响检索/价格区间口径）
    platforms: list[str] | None = None, # 关注的平台（None → 默认 ["amazon","google"]）
    depth: str = "standard",            # 研究深度：fast / standard / deep（影响检索条数与并发量）
    output_dir: str | Path = "outputs/ecommerce",  # 报告/审计/质检/评估文件的输出目录
    search_fn: SearchFn | None = None,  # 检索函数（None → 默认 Tavily；测试传 fake_search）
    llm_fn: LlmFn | None = None,        # 大模型函数（None → 全程不调 LLM，走规则）
    progress_callback: ProgressFn | None = None,  # 前端进度回调（None = 无前端/测试）
    # MCP 相关：Task 4 接住 mcp_enabled/mcp_strategy/mcp_configs 并写进 state["mcp_context"]；
    # Task 8 在此基础上新增 mcp_search_fn 参数，并在 resolved_search_fn 外再包一层
    # make_mcp_augmented_search_fn —— 真正按 mcp_enabled 把 MCP 证据追加到 base 检索结果之后。
    # 默认值保持向后兼容：不传 = 关闭 MCP、不注入 MCP 客户端 → 等价于纯 base 检索。
    mcp_enabled: bool = False,          # 是否启用 MCP 工具检索
    mcp_strategy: str = "fast",         # MCP 策略：fast / standard / deep
    mcp_configs: list[dict[str, Any]] | None = None,  # MCP server 配置（None = 不附加额外配置）
    mcp_search_fn: McpSearchFn | None = None,  # MCP 检索函数（None → 空实现兜底，不追加任何 MCP 结果）
) -> EcommerceResearchState:            # 返回完整 state（含 output_paths / evaluation_summary）
    """端到端跑一次跨境电商选品调研，并写出报告/审计/质检/log 文件。"""
    # ── ① 开日志：挂本次研究的 FileHandler + 开两道闸门（返回 handler 供结束时摘）──
    handler, log_path = _setup_run_log(query)   # 挂文件日志出口；handler 结束时要摘、log_path 给返回/前端用
    logger.info(
        f"========== 开始研究 query='{query}' market={target_market} "
        f"depth={depth} platforms={platforms or ['amazon','google']} =========="   # 在 log 留一条开始分隔线，便于定位本次研究
    )

    # ── ② 策略校验：输入不合规就直接终止（PolicyGuard 先验）──
    try:
        validate_research_request(              # PolicyGuard：检查 query/market/platforms/depth 是否合法（防注入/越权/非法值）
            query=query,
            target_market=target_market,
            platforms=platforms or ["amazon", "google"],
            depth=depth,
        )
    except PolicyViolation as exc:              # 校验不过 → 抛业务异常
        # 已挂的 handler 必须先摘掉再抛，否则文件句柄泄漏
        _teardown_run_log(handler)              # ⚠️ 先回收日志 handler，再抛错（资源清理）
        raise ValueError(str(exc)) from exc     # 转成 ValueError 往上抛（统一错误类型）；from exc 保留原始异常链

    # ── ③ 跑 graph：planner → {trend, competitor, review} → scoring → writer → quality ──
    try:
        state = create_initial_state(           # 1. 造初始 state：填用户输入 + 各结果置空 + governance 初始化
            query=query,
            target_market=target_market,
            platforms=platforms,
            depth=depth,
        )
        # 【正经注释】用本次调用传入的 MCP 参数覆盖 create_initial_state 的默认 mcp_context；
        # Task 4 只是把"是否启用 / 策略 / 配置"如实记进 state（供 evaluation_summary、API 返回读取），
        # 不改变任何检索行为 —— 真正按 mcp_enabled 切到 MCP 检索的工作在 Task 8。
        # 【大白话注释】先把用户给的 MCP 开关/策略抄到 state 里，留个记号；至于"按这个开关切检索"
        # 那是后面 Task 8 干的活，本任务不动。
        state["mcp_context"] = {
            "enabled": mcp_enabled,
            "strategy": mcp_strategy,
            "tool_calls": [],  # Task 8 会在这里追加真实 MCP 工具调用记录
            **({"configs": mcp_configs} if mcp_configs is not None else {}),
        }
        budget_manager = BudgetManager(state["governance"], get_budget_config())  # 2. 建预算管家：传 governance【引用】（闭包共享起点）+ 工厂取预算上限
        resolved_search_fn = _resolve_search_fn(search_fn)                        # 3. 选检索源：传入优先，否则默认 Tavily
        # 【正经注释】Task 8：在 base 检索外再包一层 MCP 增强。mcp_enabled=False 或无 mcp_configs
        # 时，augmented 函数等价于透传 base（不追加任何 MCP 结果、不记账）；
        # mcp_enabled=True 且配置了 server 时，每次检索会先跑 base，再跑 MCP、归一化、追加（capped at max_results），
        # MCP 抛任何异常都降级为「仅返回 base」，绝不阻塞主链路。governance 与 mcp_context 共享同一引用，
        # augmented 函数原地写账本，evaluation_summary / API 返回能直接读到 tool_calls / external_api_call_count。
        # 【大白话注释】给刚选好的搜索函数再套个「MCP 外挂」——开了 MCP 就把 MCP 结果接在后面，
        # 没开或 MCP 出错都不影响原本的搜索，只是顺带在治理账本上记一笔。
        resolved_search_fn = make_mcp_augmented_search_fn(
            resolved_search_fn,
            mcp_enabled=mcp_enabled,
            mcp_configs=mcp_configs or [],
            mcp_strategy=mcp_strategy,
            governance=state["governance"],
            mcp_context=state["mcp_context"],
            mcp_search_fn=mcp_search_fn,
        )
        final_state = await run_ecommerce_graph(  # 4. ★ 跑完整 langgraph（内部 build + compile + ainvoke）
            state,
            search_fn=resolved_search_fn,        # 注入检索能力（闭包进节点）  这只是个类
            llm_fn=llm_fn,                       # 注入大模型能力
            progress_callback=progress_callback,  # 注入前端进度回调
            budget_manager=budget_manager,       # 注入预算管家
        )
    finally:                                     # ⚠️ finally：不管 graph 成功/失败都执行
        # 不管成功失败都要摘 handler（关文件、防泄漏）
        logger.info(f"========== 研究结束，日志见 {log_path} ==========")
        _teardown_run_log(handler)               # 必摘 handler（成败都要清理文件句柄）

    # ── ④ 落盘：把结果写成 report/audit/quality/evaluation/trace/human-review/run 文件，并回填路径 ──
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)  # 建输出目录（已存在不报错）

    slug = slugify(query)                        # 关键词→安全文件名（"便携 榨汁机"→"便携-榨汁机"）
    report_path = output_path / f"{slug}-report.md"           # 选品报告（Markdown）
    audit_path = output_path / f"{slug}-audit.json"           # 审计日志（每步 agent 记录）
    quality_path = output_path / f"{slug}-quality.json"       # 质量检查
    evaluation_path = output_path / f"{slug}-evaluation.json" # 评估汇总（评分/置信度/治理）
    trace_path = output_path / f"{slug}-trace.json"           # 全链路 trace（每个节点的输入/输出/耗时/治理引用）
    human_review_path = output_path / f"{slug}-human-review.json"  # 人工评审（HITL）记录
    run_path = output_path / f"{slug}-run.json"               # 本次运行的元数据（run_id/output_paths/评估摘要）

    report_path.write_text(final_state["final_report"], encoding="utf-8")   # 写报告 .md（纯文本，不走 _write_json）
    _write_json(audit_path, final_state["audit_log"])          # 写审计 .json
    _write_json(quality_path, final_state["quality_check"])    # 写质检 .json

    # 【正经注释】evaluation_summary 必须先算：evaluation.json 的内容就是它，run.json 还要把它嵌进去。
    # 【大白话注释】先把"评估总表"算出来——后面两个文件都指望它。
    evaluation_summary = build_evaluation_summary(final_state)  # 聚合评估指标（总分/置信度/证据数/降级数/耗时/trace/HITL/MCP）
    final_state["evaluation_summary"] = evaluation_summary      # 顺手塞回 state，调用方可直接读

    _write_json(evaluation_path, evaluation_summary)            # 写评估 .json
    _write_json(trace_path, final_state.get("agent_trace", []))  # 写 trace .json（节点级执行记录）
    _write_json(                                          # 写人工评审 .json（HITL；未评审则兜底 pending）
        human_review_path,
        final_state.get("human_review", {"review_status": "pending"}),
    )

    # output_paths 在 graph 跑完、落盘后才产生 → 不进图的 channel（所以 EcommerceGraphState 没这个字段）
    final_state["output_paths"] = {              # 汇总所有输出文件路径，供调用方/前端定位
        "report": str(report_path),
        "audit": str(audit_path),
        "quality": str(quality_path),
        "evaluation": str(evaluation_path),
        "trace": str(trace_path),
        "human_review": str(human_review_path),
        "run": str(run_path),
        "log": str(log_path),                    # 带上 log 文件路径（块①那个，方便回看全链路日志）
    }
    run_metadata = {                             # 组装 run.json：把 run_id/output_paths/评估摘要打成一个可索引的整体
        "run_id": final_state.get("run_id", ""),
        "query": final_state.get("query", ""),
        "target_market": final_state.get("target_market", ""),
        "created_at_ms": int(datetime.datetime.now().timestamp() * 1000),  # 毫秒级时间戳（与 trace_recorder 口径一致）
        "output_paths": final_state["output_paths"],
        "evaluation_summary": evaluation_summary,
    }
    _write_json(run_path, run_metadata)          # 写 run.json
    return final_state                           # 返回完整 state（含 output_paths + evaluation_summary）


if __name__ == '__main__':
    # ── debug 全流程入口：用 Module name 模式跑 multi_agents.ecommerce.runner（见 PyCharm 配置）──
    # 断点打法：在 graph.py 的 planner_node / trend_node / scoring_node 等任意节点打断点，
    # Debug 跑本配置，即可单步追 START→planner→{trend,competitor,review}→scoring→writer→quality→END。
    import asyncio
    from pathlib import Path

    from dotenv import load_dotenv

    from multi_agents.ecommerce.llm_helper import default_llm_fn

    # ① 加载项目根 .env（TAVILY_API_KEY / OPENAI_API_KEY+OPENAI_BASE_URL=DeepSeek / APIFY_API_TOKEN）。
    #    runner.py 在 multi_agents/ecommerce/，往上 3 层 parent 才到项目根；load_dotenv 不带参数按 cwd 找（不稳），这里显式定位。
    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

    # ② debug 参数：改这里换关键词/市场/深度。depth: fast=最省最快 / standard=完整6维 / deep=最全最贵。
    _QUERY = "汽车玩具"
    _MARKET = "US"
    _DEPTH = "standard"

    async def _print_progress(event: str, payload: dict) -> None:
        """轻量进度回调：把 graph 各阶段事件打到控制台（不用 WebSocket 也能看流程节奏）。"""
        print(f"[progress] {event} {payload if payload else ''}")

    async def _main() -> None:
        print(
            f"========== debug 全流程：query='{_QUERY}' market={_MARKET} depth={_DEPTH} =========="
        )
        # llm_fn=default_llm_fn 复用 GPT Researcher 的 SMART_LLM（DeepSeek）；
        #   想【不花钱纯规则跑】就把 llm_fn 改成 None（scoring/summary 全走规则兜底）。
        # 不传 search_fn → 默认 Tavily 检索（需 TAVILY_API_KEY + 联网，会消耗检索额度）。
        state = await run_ecommerce_research(
            query=_QUERY,
            target_market=_MARKET,
            depth=_DEPTH,
            llm_fn=default_llm_fn,
            progress_callback=_print_progress,
        )
        # ③ 打印关键产出（report/audit/quality/evaluation/log 文件路径 + 评分 + 评估）
        score = state.get("opportunity_score", {})
        print("\n========== 关键产出 ==========")
        print(f"overall_score  : {score.get('overall_score')}  (by {score.get('scored_by')})")
        print(f"recommendation : {score.get('recommendation')}")
        print(f"evaluation     : {state.get('evaluation_summary')}")
        print("output_paths   :")
        for _k, _v in state.get("output_paths", {}).items():
            print(f"  {_k:11}: {_v}")

    asyncio.run(_main())

