"""GPT Researcher 查询处理模块
【正经注释】
本模块提供研究流程中的查询处理功能，包括：
- get_search_results: 执行搜索并返回结果（统一处理普通检索器和 MCP 检索器）
- generate_sub_queries: 通过 LLM 将原始查询分解为多个子查询
- plan_research_outline: 规划研究大纲（包含 MCP 检索器的特殊处理逻辑）

核心职责：把用户的大问题拆成 AI 可以逐一搜索的小问题。

【大白话注释】
这个文件就是"问题拆分器"——负责：
- 拿着问题去搜索引擎搜一下
- 让 AI 把大问题拆成几个更有针对性的小问题
- 如果用了外部工具（MCP），还有特殊的处理逻辑
"""
import json_repair										# 正经注释：JSON 修复库，用于解析 LLM 返回的可能格式不正确的 JSON / 大白话注释：AI 返回的 JSON 经常格式不对，这个库能自动修复

from gpt_researcher.llm_provider.generic.base import ReasoningEfforts	# 正经注释：LLM 推理努力程度的枚举（Low/Medium/High） / 大白话注释：控制 AI "想多深"的设置
from ..utils.llm import create_chat_completion			# 正经注释：LLM 通用调用接口 / 大白话注释：跟 AI 对话的函数
from ..prompts import PromptFamily						# 正经注释：提示词模板家族，提供各种场景的提示词 / 大白话注释：一套"怎么跟 AI 提问"的模板
from typing import Any, List, Dict						# 正经注释：类型提示 / 大白话注释：告诉代码"这些是什么类型"
from ..config import Config								# 正经注释：配置管理类 / 大白话注释：读取配置文件的类
import logging											# 正经注释：日志记录库 / 大白话注释：记日志

logger = logging.getLogger(__name__)						# 正经注释：创建以当前模块名命名的日志记录器 / 大白话注释：准备记事本


async def get_search_results(query: str, retriever: Any, query_domains: List[str] = None, researcher=None) -> List[Dict[str, Any]]:
    """
    执行搜索并返回结果

    【正经注释】
    通用的搜索执行函数，根据检索器类型进行差异化实例化：
    - 普通检索器：仅需 query 和 query_domains
    - MCP 检索器：额外需要 researcher 实例（包含 cfg 配置和 mcp_configs）
    调用检索器的 search() 方法执行搜索并返回结果列表。

    【大白话注释】
    拿着问题去搜——会自动判断是普通搜索引擎还是外部工具（MCP）：
    - 普通搜索引擎：给个问题就能搜
    - 外部工具：还要把"老板的完整信息"传过去

    Args:
        query: 搜索查询（大白话：要搜什么）
        retriever: 检索器类（大白话：用哪个搜索引擎）
        query_domains: 限制搜索的域名列表（大白话：只在哪些网站搜）
        researcher: GPTResearcher 实例（大白话：MCP 检索器需要这个来读配置）

    Returns:
        List[Dict]: 搜索结果列表（大白话：搜到的东西，每条有标题、链接、内容）
    """
    # Check if this is an MCP retriever and pass the researcher instance	# 正经注释：判断是否为 MCP 检索器，需要传递 researcher 实例 / 大白话注释：看看是不是外部工具
    if "mcpretriever" in retriever.__name__.lower():		# 正经注释：通过类名判断是否为 MCP 检索器 / 大白话注释：名字里有没有"mcp"
        search_retriever = retriever(						# 正经注释：MCP 检索器需要额外传入 researcher 实例 / 大白话注释：外部工具需要"老板信息"才能用
            query,
            query_domains=query_domains,
            researcher=researcher  # Pass researcher instance for MCP retrievers	# 正经注释：传递 researcher 实例以访问 cfg 和 mcp_configs / 大白话注释：把老板信息传过去
        )
    else:
        search_retriever = retriever(query, query_domains=query_domains)	# 正经注释：普通检索器仅需 query 和域名限制 / 大白话注释：普通搜索引擎，给个问题就行

    return search_retriever.search()						# 正经注释：调用检索器的 search 方法执行搜索 / 大白话注释：开始搜！返回搜到的结果


async def generate_sub_queries(							# 正经注释：通过 LLM 将原始查询分解为多个子查询 / 大白话注释：让 AI 把大问题拆成小问题
    query: str,
    parent_query: str,
    report_type: str,
    context: List[Dict[str, Any]],
    cfg: Config,
    cost_callback: callable = None,
    prompt_family: type[PromptFamily] | PromptFamily = PromptFamily,
    **kwargs
) -> List[str]:
    """
    使用 LLM 生成子查询列表

    【正经注释】
    将原始查询、父查询、报告类型和搜索上下文组合成提示词，
    调用策略模型（Strategic LLM）生成子查询列表。
    包含三层回退机制：策略模型无限制 → 策略模型带 token 限制 → 智能模型。
    使用 json_repair 解析 LLM 返回的 JSON，容忍格式错误。

    【大白话注释】
    让 AI 把大问题拆成小问题：
    1. 先把大问题和搜到的背景信息告诉 AI
    2. AI 返回一组小问题的 JSON 列表
    3. 如果最强的 AI 出错了，就换个弱一点的 AI 重试
    4. AI 返回的 JSON 格式可能不标准，用 json_repair 自动修复

    Args:
        query: 原始查询（大白话：用户问的大问题）
        parent_query: 父级查询（大白话：如果是子课题，它属于哪个大问题）
        report_type: 报告类型（大白话：什么格式的报告）
        context: 搜索结果上下文（大白话：之前搜到的背景信息）
        cfg: 配置对象（大白话：各种设置）
        cost_callback: 费用回调（大白话：算钱的函数）
        prompt_family: 提示词家族（大白话：用哪套提问模板）

    Returns:
        List[str]: 子查询列表（大白话：拆出来的小问题清单）
    """
    gen_queries_prompt = prompt_family.generate_search_queries_prompt(	# 正经注释：使用提示词家族生成子查询提示词 / 大白话注释：按模板生成"请帮我拆问题"的提示
        query,
        parent_query,
        report_type,
        max_iterations=cfg.max_iterations or 3,			# 正经注释：最大研究迭代次数，默认 3 / 大白话注释：最多拆几轮
        context=context,									# 正经注释：传入搜索上下文帮助 LLM 理解查询背景 / 大白话注释：把背景信息也给 AI 看看
    )

    try:													# 正经注释：第一层尝试 - 策略模型（最强推理），无 token 限制 / 大白话注释：用最强的 AI，不限字数
        response = await create_chat_completion(
            model=cfg.strategic_llm_model,					# 正经注释：策略模型，最擅长复杂推理 / 大白话注释：最强的 AI
            messages=[{"role": "user", "content": gen_queries_prompt}],
            llm_provider=cfg.strategic_llm_provider,
            max_tokens=None,								# 正经注释：不限制输出 token 数 / 大白话注释：不限字数，让 AI 自由发挥
            llm_kwargs=cfg.llm_kwargs,
            reasoning_effort=ReasoningEfforts.Medium.value,	# 正经注释：中等推理努力程度 / 大白话注释：让 AI "想得差不多就行"
            cost_callback=cost_callback,
            **kwargs
        )
    except Exception as e:									# 正经注释：第一层失败 → 第二层：策略模型但加 token 限制 / 大白话注释：最强 AI 出错了，试试限制字数
        logger.warning(f"Error with strategic LLM: {e}. Retrying with max_tokens={cfg.strategic_token_limit}.")
        logger.warning(f"See https://github.com/assafelovic/gpt-researcher/issues/1022")
        try:
            response = await create_chat_completion(
                model=cfg.strategic_llm_model,				# 正经注释：仍用策略模型 / 大白话注释：还是最强 AI
                messages=[{"role": "user", "content": gen_queries_prompt}],
                max_tokens=cfg.strategic_token_limit,		# 正经注释：加上 token 限制，避免超长输出导致的错误 / 大白话注释：这次限制字数
                llm_provider=cfg.strategic_llm_provider,
                llm_kwargs=cfg.llm_kwargs,
                cost_callback=cost_callback,
                **kwargs
            )
            logger.warning(f"Retrying with max_tokens={cfg.strategic_token_limit} successful.")
        except Exception as e:								# 正经注释：第二层也失败 → 第三层：降级到智能模型 / 大白话注释：还是不行？换个便宜点的 AI 试试
            logger.warning(f"Retrying with max_tokens={cfg.strategic_token_limit} failed.")
            logger.warning(f"Error with strategic LLM: {e}. Falling back to smart LLM.")
            response = await create_chat_completion(
                model=cfg.smart_llm_model,					# 正经注释：降级到智能模型（次强但更稳定） / 大白话注释：换个性价比高的 AI
                messages=[{"role": "user", "content": gen_queries_prompt}],
                temperature=cfg.temperature,				# 正经注释：使用配置的温度参数控制创造性 / 大白话注释：控制 AI 的"发散程度"
                max_tokens=cfg.smart_token_limit,			# 正经注释：智能模型的 token 限制 / 大白话注释：这个 AI 的字数上限
                llm_provider=cfg.smart_llm_provider,
                llm_kwargs=cfg.llm_kwargs,
                cost_callback=cost_callback,
                **kwargs
            )

    return json_repair.loads(response)						# 正经注释：用 json_repair 解析 LLM 返回的 JSON，自动修复常见格式错误 / 大白话注释：把 AI 返回的文字修成标准 JSON 列表


async def plan_research_outline(							# 正经注释：规划研究大纲，决定要搜索哪些子查询 / 大白话注释：制定"调研计划"——应该搜哪些小问题
    query: str,
    search_results: List[Dict[str, Any]],
    agent_role_prompt: str,
    cfg: Config,
    parent_query: str,
    report_type: str,
    cost_callback: callable = None,
    retriever_names: List[str] = None,
    **kwargs
) -> List[str]:
    """
    规划研究大纲（生成子查询列表）

    【正经注释】
    研究大纲规划的核心入口，包含 MCP 检索器的特殊优化逻辑：
    - 仅 MCP 检索器时：跳过子查询生成，直接返回原始查询
      （因为 MCP 内部已有智能工具选择和搜索机制）
    - 混合检索器时：正常生成子查询供非 MCP 检索器使用
    - 无 MCP 时：标准子查询生成流程

    【大白话注释】
    制定调研计划：
    - 如果只用了外部工具（MCP），就不拆问题了——因为外部工具自己会智能搜索
    - 如果同时用了普通搜索引擎和外部工具，就正常拆问题给搜索引擎用
    - 如果只有普通搜索引擎，就走正常流程

    Args:
        query: 原始查询（大白话：用户的大问题）
        search_results: 初始搜索结果（大白话：之前搜到的背景信息）
        agent_role_prompt: 代理角色提示词（大白话：用什么"专家"的口吻）
        cfg: 配置对象（大白话：各种设置）
        parent_query: 父级查询（大白话：属于哪个大问题）
        report_type: 报告类型（大白话：什么格式的报告）
        cost_callback: 费用回调（大白话：算钱的函数）
        retriever_names: 检索器名称列表（大白话：用了哪些搜索引擎/工具）

    Returns:
        List[str]: 子查询列表（大白话：要搜的小问题清单）
    """
    # Handle the case where retriever_names is not provided	# 正经注释：处理未提供检索器名称的情况 / 大白话注释：没说用了哪些搜索引擎就当没说
    if retriever_names is None:
        retriever_names = []

    # For MCP retrievers, we may want to skip sub-query generation	# 正经注释：MCP 检索器的特殊优化——可能跳过子查询生成 / 大白话注释：如果用了外部工具，可能不用拆问题
    # Check if MCP is the only retriever or one of multiple retrievers	# 正经注释：判断 MCP 是唯一的还是多个检索器之一 / 大白话注释：看看外部工具是"独占"还是"跟别人一起"
    if retriever_names and ("mcp" in retriever_names or "MCPRetriever" in retriever_names):	# 正经注释：检测是否存在 MCP 检索器 / 大白话注释：有没有外部工具？
        mcp_only = (len(retriever_names) == 1 and			# 正经注释：判断是否只有 MCP 一个检索器 / 大白话注释：是不是只有外部工具，没有普通搜索引擎？
                   ("mcp" in retriever_names or "MCPRetriever" in retriever_names))

        if mcp_only:										# 正经注释：MCP 独占模式——跳过子查询生成 / 大白话注释：只有外部工具就不用拆了
            logger.info("Using MCP retriever only - skipping sub-query generation")
            # Return the original query to prevent additional search iterations	# 正经注释：返回原始查询，避免多余的搜索迭代 / 大白话注释：直接返回原问题，外部工具自己会智能处理
            return [query]
        else:												# 正经注释：混合模式——MCP 和其他检索器并存，正常生成子查询 / 大白话注释：外部工具和普通搜索引擎都有，正常拆问题
            logger.info("Using MCP with other retrievers - generating sub-queries for non-MCP retrievers")

    # Generate sub-queries for research outline				# 正经注释：调用 generate_sub_queries 生成子查询 / 大白话注释：让 AI 拆问题
    sub_queries = await generate_sub_queries(
        query,
        parent_query,
        report_type,
        search_results,
        cfg,
        cost_callback,
        **kwargs
    )

    return sub_queries									# 正经注释：返回子查询列表 / 大白话注释：把拆好的小问题交出去