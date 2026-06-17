"""报告生成模块（Report Generation）
【正经注释】
本模块提供研究报告的生成功能，包括：
- write_report_introduction: 生成报告引言
- write_conclusion: 生成报告结论
- summarize_url: 摘要单个 URL 内容
- generate_draft_section_titles: 生成草稿章节标题
- generate_report: 生成完整研究报告（核心函数）
所有函数通过 create_chat_completion 调用 LLM 生成文本，支持流式输出和费用追踪。
【大白话注释】
这个文件就是"写手"用的工具箱——写开头、写结尾、总结网页、列提纲、写完整报告。
全部都是让 AI 来写的，人工只负责告诉它"写什么"。
"""
import asyncio														# 正经注释：异步 I/O 库 / 大白话注释：异步工具
from typing import List, Dict, Any									# 正经注释：类型提示 / 大白话注释：类型标记
from ..config.config import Config									# 正经注释：配置类 / 大白话注释：读取设置
from ..utils.llm import create_chat_completion						# 正经注释：LLM 调用接口 / 大白话注释：跟 AI 对话的函数
from ..utils.logger import get_formatted_logger						# 正经注释：格式化日志器 / 大白话注释：记事本
from ..prompts import PromptFamily, get_prompt_by_report_type		# 正经注释：提示词模板和按报告类型获取模板的函数 / 大白话注释：提问模板 + 按格式选模板
from ..utils.enum import Tone										# 正经注释：语气枚举 / 大白话注释：报告语气（客观/主观等）

logger = get_formatted_logger()										# 正经注释：创建日志记录器 / 大白话注释：准备记事本


async def write_report_introduction(								# 正经注释：生成报告引言 / 大白话注释：写报告的"开头"
    query: str,
    context: str,
    agent_role_prompt: str,
    config: Config,
    websocket=None,
    cost_callback: callable = None,
    prompt_family: type[PromptFamily] | PromptFamily = PromptFamily,
    **kwargs
) -> str:
    """
    生成报告引言
    【正经注释】使用智能模型基于研究查询和上下文生成报告开篇引言，支持流式输出。
    【大白话注释】让 AI 根据问题和素材写一个"开头"，介绍研究什么、为什么研究。
    Args:
        query: 研究查询（大白话：研究的问题）
        context: 研究上下文（大白话：搜集到的素材）
        agent_role_prompt: 代理角色提示词（大白话：用什么专家的口吻写）
        config: 配置对象（大白话：各种设置）
        websocket: WebSocket 连接（大白话：实时推送通道）
        cost_callback: 费用回调（大白话：算钱的函数）
        prompt_family: 提示词家族（大白话：用哪套提问模板）
    Returns:
        str: 生成的引言文本（大白话：写好的开头）
    """
    try:
        introduction = await create_chat_completion(				# 正经注释：调用 LLM 生成引言 / 大白话注释：让 AI 写开头
            model=config.smart_llm_model,							# 正经注释：智能模型 / 大白话注释：聪明但不太贵的 AI
            messages=[
                {"role": "system", "content": f"{agent_role_prompt}"},	# 正经注释：系统提示词设置角色 / 大白话注释：告诉 AI 用什么角色
                {"role": "user", "content": prompt_family.generate_report_introduction(	# 正经注释：用户消息包含引言生成提示 / 大白话注释：让 AI 写引言
                    question=query,
                    research_summary=context,
                    language=config.language							# 正经注释：指定输出语言 / 大白话注释：用什么语言写
                )},
            ],
            temperature=0.25,										# 正经注释：较低温度保证质量 / 大白话注释：不要太多创造性，写稳一点
            llm_provider=config.smart_llm_provider,
            stream=True,											# 正经注释：启用流式输出 / 大白话注释：边写边推送
            websocket=websocket,
            max_tokens=config.smart_token_limit,
            llm_kwargs=config.llm_kwargs,
            cost_callback=cost_callback,
            **kwargs
        )
        return introduction											# 正经注释：返回生成的引言 / 大白话注释：交出去
    except Exception as e:
        logger.error(f"Error in generating report introduction: {e}")	# 正经注释：记录错误 / 大白话注释：日志——写开头出错了
    return ""														# 正经注释：出错返回空字符串 / 大白话注释：出错了就返回空


async def write_conclusion(											# 正经注释：生成报告结论 / 大白话注释：写报告的"结尾"
    query: str,
    context: str,
    agent_role_prompt: str,
    config: Config,
    websocket=None,
    cost_callback: callable = None,
    prompt_family: type[PromptFamily] | PromptFamily = PromptFamily,
    **kwargs
) -> str:
    """
    生成报告结论
    【正经注释】基于报告正文生成总结性结论段落，涵盖研究发现和关键见解。
    【大白话注释】让 AI 看了报告正文后，写一个"总结"——归纳核心结论。
    Args:
        query: 研究查询（大白话：研究的问题）
        context: 报告正文（大白话：已经写好的报告）
        agent_role_prompt: 代理角色提示词（大白话：用什么专家的口吻）
        config: 配置对象（大白话：各种设置）
        websocket: WebSocket 连接（大白话：实时推送通道）
        cost_callback: 费用回调（大白话：算钱的函数）
        prompt_family: 提示词家族（大白话：用哪套提问模板）
    Returns:
        str: 生成的结论文本（大白话：写好的总结）
    """
    try:
        conclusion = await create_chat_completion(					# 正经注释：调用 LLM 生成结论 / 大白话注释：让 AI 写总结
            model=config.smart_llm_model,
            messages=[
                {"role": "system", "content": f"{agent_role_prompt}"},	# 正经注释：设置角色 / 大白话注释：告诉 AI 用什么角色
                {
                    "role": "user",
                    "content": prompt_family.generate_report_conclusion(query=query,	# 正经注释：结论生成提示 / 大白话注释：让 AI 写结论
                                                                        report_content=context,
                                                                        language=config.language),
                },
            ],
            temperature=0.25,
            llm_provider=config.smart_llm_provider,
            stream=True,											# 正经注释：流式输出 / 大白话注释：边写边推
            websocket=websocket,
            max_tokens=config.smart_token_limit,
            llm_kwargs=config.llm_kwargs,
            cost_callback=cost_callback,
            **kwargs
        )
        return conclusion											# 正经注释：返回生成的结论 / 大白话注释：交出去
    except Exception as e:
        logger.error(f"Error in writing conclusion: {e}")			# 正经注释：记录错误 / 大白话注释：日志——写结尾出错了
    return ""														# 正经注释：出错返回空字符串 / 大白话注释：出错了就返回空


async def summarize_url(											# 正经注释：摘要单个 URL 的内容 / 大白话注释：总结一个网页的内容
    url: str,
    content: str,
    role: str,
    config: Config,
    websocket=None,
    cost_callback: callable = None,
    **kwargs
) -> str:
    """
    摘要 URL 内容
    【正经注释】将指定 URL 的内容发送给 LLM 进行摘要总结。
    【大白话注释】让 AI 看看这个网页的内容，用一两段话总结一下。
    Args:
        url: URL 地址（大白话：网页链接）
        content: 网页内容（大白话：网页上的文字）
        role: 代理角色（大白话：用什么角色的口吻）
        config: 配置对象（大白话：各种设置）
        websocket: WebSocket 连接（大白话：实时推送通道）
        cost_callback: 费用回调（大白话：算钱的函数）
    Returns:
        str: 摘要内容（大白话：总结好的文字）
    """
    try:
        summary = await create_chat_completion(						# 正经注释：调用 LLM 进行摘要 / 大白话注释：让 AI 总结
            model=config.smart_llm_model,
            messages=[
                {"role": "system", "content": f"{role}"},			# 正经注释：设置角色 / 大白话注释：告诉 AI 用什么角色
                {"role": "user", "content": f"Summarize the following content from {url}:\n\n{content}"},	# 正经注释：摘要提示 / 大白话注释："帮我总结这个网页"
            ],
            temperature=0.25,
            llm_provider=config.smart_llm_provider,
            stream=True,
            websocket=websocket,
            max_tokens=config.smart_token_limit,
            llm_kwargs=config.llm_kwargs,
            cost_callback=cost_callback,
            **kwargs
        )
        return summary												# 正经注释：返回摘要 / 大白话注释：交出去
    except Exception as e:
        logger.error(f"Error in summarizing URL: {e}")				# 正经注释：记录错误 / 大白话注释：日志——总结出错了
    return ""														# 正经注释：出错返回空字符串 / 大白话注释：出错了就返回空


async def generate_draft_section_titles(							# 正经注释：生成草稿章节标题 / 大白话注释：给报告列个"写作提纲"
    query: str,
    current_subtopic: str,
    context: str,
    role: str,
    config: Config,
    websocket=None,
    cost_callback: callable = None,
    prompt_family: type[PromptFamily] | PromptFamily = PromptFamily,
    **kwargs
) -> List[str]:
    """
    生成草稿章节标题
    【正经注释】基于查询和上下文，让 LLM 生成报告的章节标题列表。
    【大白话注释】让 AI 看着素材，列一个"这节写什么、那节写什么"的提纲。
    Args:
        query: 研究查询（大白话：研究的问题）
        current_subtopic: 当前子课题（大白话：正在写的小话题）
        context: 上下文（大白话：素材）
        role: 角色（大白话：用什么口吻）
        config: 配置（大白话：各种设置）
        websocket: WebSocket（大白话：实时推送）
        cost_callback: 费用回调（大白话：算钱的函数）
        prompt_family: 提示词家族（大白话：提问模板）
    Returns:
        List[str]: 章节标题列表（大白话：小节标题清单）
    """
    try:
        section_titles = await create_chat_completion(				# 正经注释：调用 LLM 生成标题 / 大白话注释：让 AI 列提纲
            model=config.smart_llm_model,
            messages=[
                {"role": "system", "content": f"{role}"},
                {"role": "user", "content": prompt_family.generate_draft_titles_prompt(
                    current_subtopic, query, context)},				# 正经注释：章节标题生成提示 / 大白话注释："帮我列个提纲"
            ],
            temperature=0.25,
            llm_provider=config.smart_llm_provider,
            stream=True,
            websocket=None,											# 正经注释：不流式推送标题生成 / 大白话注释：标题不需要实时推送
            max_tokens=config.smart_token_limit,
            llm_kwargs=config.llm_kwargs,
            cost_callback=cost_callback,
            **kwargs
        )
        return section_titles.split("\n")							# 正经注释：按换行拆分为标题列表 / 大白话注释：一行一个标题，切成列表
    except Exception as e:
        logger.error(f"Error in generating draft section titles: {e}")	# 正经注释：记录错误 / 大白话注释：日志——列提纲出错了
    return []														# 正经注释：出错返回空列表 / 大白话注释：出错了就返回空


async def generate_report(											# 正经注释：生成完整研究报告——本模块的核心函数 / 大白话注释：写完整报告！这是最重要的函数
    query: str,
    context,
    agent_role_prompt: str,
    report_type: str,
    tone: Tone,
    report_source: str,
    websocket,
    cfg,
    main_topic: str = "",
    existing_headers: list = [],
    relevant_written_contents: list = [],
    cost_callback: callable = None,
    custom_prompt: str = "", # This can be any prompt the user chooses with the context	# 正经注释：用户自定义提示词 / 大白话注释：给写手的特别指示
    headers=None,
    prompt_family: type[PromptFamily] | PromptFamily = PromptFamily,
    available_images: list = None,
    **kwargs
):
    """
    生成完整研究报告
    【正经注释】
    根据报告类型选择对应的提示词模板，组合查询、上下文、语气等参数，
    调用 LLM 生成完整报告。支持子课题报告、自定义提示词和预生成图片嵌入。
    包含两层异常回退：先尝试 system+user 消息，失败后改为单条 user 消息。
    【大白话注释】
    这是写完整报告的核心！流程是：
    1. 根据报告类型选一个提问模板
    2. 把问题、素材、语气等参数填进去
    3. 如果有预生成的配图，也加进去
    4. 让 AI 写报告
    5. 如果第一次失败了，换个方式再试一次
    Args:
        query: 研究查询（大白话：研究的问题）
        context: 上下文（大白话：搜集的素材）
        agent_role_prompt: 代理角色（大白话：用什么专家）
        report_type: 报告类型（大白话：什么格式）
        tone: 语气（大白话：用什么语气）
        report_source: 来源（大白话：从哪找的资料）
        websocket: WebSocket（大白话：实时推送）
        cfg: 配置（大白话：各种设置）
        main_topic: 主话题（大白话：大问题是什么）
        existing_headers: 已有标题（大白话：已经写过的标题）
        relevant_written_contents: 已写内容（大白话：之前写过的段落）
        cost_callback: 费用回调（大白话：算钱的函数）
        custom_prompt: 自定义提示词（大白话：给写手的特别指示）
        headers: 请求头（大白话：额外的请求信息）
        prompt_family: 提示词家族（大白话：提问模板）
        available_images: 预生成图片（大白话：已经画好的配图）
    Returns:
        str: 生成的报告（大白话：写好的报告）
    """
    available_images = available_images or []						# 正经注释：确保 images 不为 None / 大白话注释：没给图片就设为空列表
    generate_prompt = get_prompt_by_report_type(report_type, prompt_family)	# 正经注释：根据报告类型获取对应的提示词生成函数 / 大白话注释：按格式选提问模板
    report = ""														# 正经注释：初始化报告字符串 / 大白话注释：准备装报告

    if report_type == "subtopic_report":							# 正经注释：子课题报告使用特殊模板 / 大白话注释：子课题报告——需要传主话题和已有内容
        content = f"{generate_prompt(query, existing_headers, relevant_written_contents, main_topic, context, report_format=cfg.report_format, tone=tone, total_words=cfg.total_words, language=cfg.language)}"
    elif custom_prompt:												# 正经注释：使用自定义提示词 / 大白话注释：用户给了特别指示就用用户的
        content = f"{custom_prompt}\n\nContext: {context}"			# 正经注释：自定义提示词 + 上下文 / 大白话注释：特别指示 + 素材
    else:															# 正经注释：标准报告生成 / 大白话注释：正常模式
        content = f"{generate_prompt(query, context, report_source, report_format=cfg.report_format, tone=tone, total_words=cfg.total_words, language=cfg.language)}"

    # Add available images instruction if images were pre-generated	# 正经注释：如果有预生成的图片，在提示词中添加图片嵌入指令 / 大白话注释：有配图就告诉 AI 把图插到报告里
    if available_images:
        images_info = "\n".join([									# 正经注释：格式化图片信息列表 / 大白话注释：把图片信息列出来
            f"- Image {i+1}: ![{img.get('title', img.get('alt_text', 'Illustration'))}]({img['url']}) - {img.get('section_hint', 'General')}"
            for i, img in enumerate(available_images)
        ])
        content += f"""

AVAILABLE IMAGES:
You have the following pre-generated images available. Embed them in relevant sections of your report using the exact markdown syntax provided:

{images_info}

Place each image on its own line after the relevant section header or paragraph. Use all available images where they add value to the content."""	# 正经注释：指示 AI 在合适位置嵌入图片 / 大白话注释：告诉 AI "这些图要放到合适的位置"
    try:
        report = await create_chat_completion(						# 正经注释：第一次尝试 - 使用 system+user 双消息格式 / 大白话注释：让 AI 写报告（第一次尝试）
            model=cfg.smart_llm_model,
            messages=[
                {"role": "system", "content": f"{agent_role_prompt}"},	# 正经注释：系统消息设置角色 / 大白话注释：告诉 AI 用什么角色
                {"role": "user", "content": content},				# 正经注释：用户消息包含报告生成提示 / 大白话注释：报告要求
            ],
            temperature=0.35,										# 正经注释：稍高温度增加报告的多样性 / 大白话注释：允许一点创造性，让报告更丰富
            llm_provider=cfg.smart_llm_provider,
            stream=True,											# 正经注释：流式输出 / 大白话注释：边写边推
            websocket=websocket,
            max_tokens=cfg.smart_token_limit,
            llm_kwargs=cfg.llm_kwargs,
            cost_callback=cost_callback,
            **kwargs
        )
    except Exception:												# 正经注释：第一次失败后回退 - 合并为单条 user 消息 / 大白话注释：第一次失败了，换个方式再试
        try:
            report = await create_chat_completion(					# 正经注释：第二次尝试 - system+user 合并为单条 user 消息 / 大白话注释：把角色和要求合成一条消息再试
                model=cfg.smart_llm_model,
                messages=[
                    {"role": "user", "content": f"{agent_role_prompt}\n\n{content}"},	# 正经注释：角色提示和内容合并 / 大白话注释：角色 + 要求合在一起
                ],
                temperature=0.35,
                llm_provider=cfg.smart_llm_provider,
                stream=True,
                websocket=websocket,
                max_tokens=cfg.smart_token_limit,
                llm_kwargs=cfg.llm_kwargs,
                cost_callback=cost_callback,
                **kwargs
            )
        except Exception as e:										# 正经注释：第二次也失败 / 大白话注释：还是不行
            print(f"Error in generate_report: {e}")				# 正经注释：记录错误 / 大白话注释：日志——写报告出错了

    return report													# 正经注释：返回生成的报告 / 大白话注释：交出去（可能是空的如果两次都失败了）
