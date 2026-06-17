"""代理创建与选择模块（Agent Creator）
【正经注释】
本模块提供研究代理的自动选择功能，通过 LLM 分析查询内容，
自动匹配最合适的研究代理类型和角色提示词。
包含 JSON 解析容错机制：json.loads → json_repair → 正则提取 → 默认代理。
【大白话注释】
这个文件负责"选研究员"——让 AI 看看你的问题，自动选一个最合适的专家来研究。
AI 返回的选择结果可能格式不对，所以有四层容错确保总能选出一个研究员。
"""
import json													# 正经注释：JSON 解析库 / 大白话注释：解析 JSON
import logging												# 正经注释：日志库 / 大白话注释：记日志
import re														# 正经注释：正则表达式库 / 大白话注释：用模式匹配从文字里抠东西

import json_repair											# 正经注释：JSON 修复库，容忍格式错误 / 大白话注释：AI 返回的 JSON 经常格式不对，这个能自动修

from ..prompts import PromptFamily							# 正经注释：提示词模板家族 / 大白话注释：怎么跟 AI 提问的模板
from ..utils.llm import create_chat_completion				# 正经注释：LLM 调用接口 / 大白话注释：跟 AI 对话的函数

logger = logging.getLogger(__name__)							# 正经注释：创建日志记录器 / 大白话注释：准备记事本

async def choose_agent(										# 正经注释：异步函数，通过 LLM 自动选择最合适的研究代理 / 大白话注释：让 AI 选一个"研究员"
    query,
    cfg,
    parent_query=None,
    cost_callback: callable = None,
    headers=None,
    prompt_family: type[PromptFamily] | PromptFamily = PromptFamily,
    **kwargs
):
    """
    自动选择研究代理
    【正经注释】
    将查询发送给 LLM，由 LLM 根据查询内容选择合适的研究代理。
    LLM 返回 JSON 格式的代理信息（server 和 agent_role_prompt）。
    包含多层 JSON 解析容错机制。
    【大白话注释】
    把你的问题告诉 AI，让 AI 选一个合适的"研究员"来研究。
    比如"Python vs JS"→ AI 会选"科技专家"。
    Args:
        parent_query: 父级查询（大白话：如果是子课题，主问题是什么）
        query: 原始查询（大白话：你的问题）
        cfg: 配置对象（大白话：各种设置）
        cost_callback: 费用回调（大白话：算钱的函数）
        headers: 请求头（大白话：额外的请求信息）
        prompt_family: 提示词家族（大白话：用哪套提问模板）
    Returns:
        tuple: (代理名称, 角色提示词)（大白话：(选的什么专家, 专家的角色描述)）
    """
    query = f"{parent_query} - {query}" if parent_query else f"{query}"	# 正经注释：拼接父查询和子查询 / 大白话注释：如果有主问题就拼在一起
    response = None  # Initialize response to ensure it's defined	# 正经注释：初始化响应变量，确保后续异常处理中可访问 / 大白话注释：先设为空

    try:
        response = await create_chat_completion(				# 正经注释：调用 LLM 进行代理选择 / 大白话注释：问 AI "该选什么专家"
            model=cfg.smart_llm_model,							# 正经注释：使用智能模型 / 大白话注释：用聪明但不太贵的 AI
            messages=[
                {"role": "system", "content": f"{prompt_family.auto_agent_instructions()}"},	# 正经注释：系统提示词，包含所有可用代理的描述 / 大白话注释：告诉 AI 有哪些专家可选
                {"role": "user", "content": f"task: {query}"},	# 正经注释：用户消息，包含研究查询 / 大白话注释：你的问题
            ],
            temperature=0.15,									# 正经注释：低温度保证选择的稳定性和一致性 / 大白话注释：让 AI 的回答尽量稳定，别太随机
            llm_provider=cfg.smart_llm_provider,
            llm_kwargs=cfg.llm_kwargs,
            cost_callback=cost_callback,
            **kwargs
        )

        agent_dict = json.loads(response)						# 正经注释：解析 LLM 返回的 JSON / 大白话注释：把 AI 返回的文字变成字典
        return agent_dict["server"], agent_dict["agent_role_prompt"]	# 正经注释：返回代理名称和角色提示词 / 大白话注释：交出去（专家名字 + 角色描述）

    except Exception as e:										# 正经注释：JSON 解析失败时的容错处理 / 大白话注释：解析出错了，试试别的方法
        return await handle_json_error(response)				# 正经注释：调用 JSON 错误处理函数 / 大白话注释：交给容错函数处理


async def handle_json_error(response: str | None):
    """处理 LLM 返回的 JSON 解析错误
    【正经注释】
    三层容错机制：json_repair → 正则提取 → 默认代理。
    确保无论 LLM 返回什么格式，总能返回有效的代理信息。
    【大白话注释】
    AI 返回的 JSON 格式坏了怎么办？按这个顺序修：
    1. 用 json_repair 库自动修复
    2. 用正则表达式从文字里抠 JSON
    3. 实在不行就用默认的"通用研究员"
    Args:
        response: LLM 响应字符串（大白话：AI 返回的文字）
    Returns:
        tuple: (代理名称, 角色提示词)（大白话：(专家名字, 角色描述)）
    """
    try:
        agent_dict = json_repair.loads(response)				# 正经注释：第一层容错 - 用 json_repair 修复格式 / 大白话注释：先试试自动修复
        if agent_dict.get("server") and agent_dict.get("agent_role_prompt"):
            return agent_dict["server"], agent_dict["agent_role_prompt"]	# 正经注释：修复成功，返回代理信息 / 大白话注释：修好了，交出去
    except Exception as e:										# 正经注释：json_repair 也失败了 / 大白话注释：修复不了
        error_type = type(e).__name__
        error_msg = str(e)
        logger.warning(
            f"Failed to parse agent JSON with json_repair: {error_type}: {error_msg}",
            exc_info=True
        )
        if response:
            logger.debug(f"LLM response that failed to parse: {response[:500]}...")	# 正经注释：记录导致解析失败的原始响应 / 大白话注释：日志——AI 返回了什么导致解析失败

    json_string = extract_json_with_regex(response)			# 正经注释：第二层容错 - 用正则从文本中提取 JSON / 大白话注释：用正则抠一抠看有没有 JSON
    if json_string:
        try:
            json_data = json.loads(json_string)				# 正经注释：解析提取的 JSON / 大白话注释：把抠到的 JSON 解析一下
            return json_data["server"], json_data["agent_role_prompt"]	# 正经注释：提取成功，返回代理信息 / 大白话注释：抠到了，交出去
        except json.JSONDecodeError as e:						# 正经注释：提取的 JSON 仍然无法解析 / 大白话注释：抠到了但解析不了
            logger.warning(
                f"Failed to decode JSON from regex extraction: {str(e)}",
                exc_info=True
            )

    logger.info("No valid JSON found in LLM response. Falling back to default agent.")	# 正经注释：第三层容错 - 使用默认代理 / 大白话注释：都不行，用默认的"通用研究员"
    return "Default Agent", (									# 正经注释：返回默认代理名称和通用角色提示词 / 大白话注释：默认的"什么都能研究"的专家
        "You are an AI critical thinker research assistant. Your sole purpose is to write well written, "
        "critically acclaimed, objective and structured reports on given text."
    )


def extract_json_with_regex(response: str | None) -> str | None:
    """用正则表达式从字符串中提取 JSON 对象
    【正经注释】搜索第一个匹配 {.*?} 模式的 JSON 对象（DOTALL 模式支持多行）。
    【大白话注释】从一段文字里找找有没有 {} 包裹的 JSON，找到就拿出来。
    Args:
        response: 要搜索的字符串（大白话：AI 返回的文字）
    Returns:
        str | None: 提取的 JSON 字符串或 None（大白话：找到的 JSON 或空）
    """
    if not response:											# 正经注释：空响应直接返回 None / 大白话注释：啥都没有就不用找了
        return None
    json_match = re.search(r"{.*?}", response, re.DOTALL)		# 正经注释：正则匹配第一个 JSON 对象（非贪婪，支持多行） / 大白话注释：找第一个 {...}
    if json_match:
        return json_match.group(0)								# 正经注释：返回匹配的 JSON 字符串 / 大白话注释：找到了，交出去
    return None												# 正经注释：未找到返回 None / 大白话注释：没找到
