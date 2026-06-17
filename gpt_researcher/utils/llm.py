"""
【正经注释】
LLM 工具模块，为 GPT Researcher 提供统一的大语言模型交互接口。
封装了 LLM 提供商实例化、聊天补全（含重试机制和成本追踪）、
以及基于 Pydantic 的子主题构建等功能。

【大白话注释】
这个文件是跟大模型聊天的"翻译官"。不管你用的是 OpenAI 还是 Anthropic，
都通过这里来统一调用。它还能自动重试失败的请求、记录花了多少钱、
以及帮你把研究任务拆成小主题。
"""
from __future__ import annotations  # 正经注释：启用延迟注解评估 / 大白话注释：让类型提示更好写

import logging  # 正经注释：标准日志库 / 大白话注释：打日志用的
import os  # 正经注释：操作系统接口，用于读取环境变量 / 大白话注释：用来读系统环境变量的
from typing import Any  # 正经注释：任意类型 / 大白话注释：什么类型都行的兜底
import asyncio  # 正经注释：异步 I/O 库，用于协程调度 / 大白话注释：异步编程用的，让程序不用傻等

from langchain_core.output_parsers import PydanticOutputParser  # 正经注释：LangChain 的 Pydantic 输出解析器，将 LLM 输出解析为 Pydantic 模型 / 大白话注释：把大模型的回答自动转成结构化的 Python 对象
from langchain_core.prompts import PromptTemplate  # 正经注释：LangChain 的提示词模板，支持变量替换 / 大白话注释：提示词模板，往里面填变量用的

from gpt_researcher.llm_provider.generic.base import (  # 正经注释：从 LLM 提供商基类导入模型能力常量 / 大白话注释：导入一些标记哪些模型有什么特殊能力的常量
    NO_SUPPORT_TEMPERATURE_MODELS,
    SUPPORT_REASONING_EFFORT_MODELS,
    ReasoningEfforts,
)

from ..prompts import PromptFamily  # 正经注释：从上级模块导入提示词族枚举 / 大白话注释：导入提示词模板"套餐"
from .costs import calculate_llm_cost  # 正经注释：从成本模块导入 LLM 成本计算函数 / 大白话注释：导入算钱的功能
from .validators import Subtopics  # 正经注释：从验证器模块导入子主题 Pydantic 模型 / 大白话注释：导入子主题的数据结构


def get_llm(llm_provider: str, **kwargs):
    """
    【正经注释】
    获取 LLM 提供商实例的工厂函数。根据指定的提供商名称创建并返回
    对应的 GenericLLMProvider 实例，支持通过关键字参数传递额外配置。

    【大白话注释】
    给它一个模型提供商的名字（比如 'openai'、'anthropic'），它就帮你创建一个
    可以跟那个模型聊天的对象。你还可以通过额外参数来微调配置。

    Args:
        llm_provider: LLM 提供商名称（如 'openai'、'anthropic'）。
        **kwargs: 传递给提供商的额外关键字参数。

    Returns:
        配置好的 GenericLLMProvider 实例。
    """
    from gpt_researcher.llm_provider import GenericLLMProvider  # 正经注释：延迟导入避免循环依赖 / 大白话注释：用到的时候才导入，防止导入的时候出问题
    return GenericLLMProvider.from_provider(llm_provider, **kwargs)  # 正经注释：通过工厂方法创建提供商实例 / 大白话注释：用工厂方法造一个提供商对象出来


async def create_chat_completion(
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = 0.4,
        max_tokens: int | None = 4000,
        llm_provider: str | None = None,
        stream: bool = False,
        websocket: Any | None = None,
        llm_kwargs: dict[str, Any] | None = None,
        cost_callback: callable = None,
        reasoning_effort: str | None = ReasoningEfforts.Medium.value,
        **kwargs
) -> str:
    """
    【正经注释】
    异步创建聊天补全请求。向指定的 LLM 提供商发送消息列表，获取模型的回复。
    内置重试机制（指数退避）、成本追踪、流式输出支持，并根据模型特性自动调整参数配置。

    【大白话注释】
    这是跟大模型聊天的核心函数。你给它一段对话历史，它帮你发给大模型，拿到回答。
    如果请求失败了会自动重试（最多10次），还能实时算花了多少钱，支持流式输出。
    不同模型有不同的"脾气"，这个函数会自动适应。

    Args:
        messages (list[dict[str, str]]): 发送给 LLM 的消息列表。
        model (str, optional): 使用的模型名称。
        temperature (float, optional): 生成温度，控制随机性。默认 0.4。
        max_tokens (int, optional): 最大生成 Token 数。默认 4000。
        llm_provider (str, optional): LLM 提供商名称。
        stream (bool): 是否流式输出。默认 False。
        webocket (WebSocket): 当前请求使用的 WebSocket 连接。
        llm_kwargs (dict[str, Any], optional): 额外的 LLM 关键字参数。
        cost_callback: 用于更新成本的回调函数。
        reasoning_effort (str, optional): 推理模型的推理力度。默认 'medium'。
        **kwargs: 额外关键字参数。
    Returns:
        str: 聊天补全的响应文本。
    """
    # validate input
    if model is None:  # 正经注释：验证模型参数不为空 / 大白话注释：没指定用哪个模型就报错
        raise ValueError("Model cannot be None")
    # Sanity guard against absurd values (e.g., env var typos). The actual
    # per-model output limits are enforced by the upstream provider.
    if max_tokens is not None and max_tokens > 200_000:  # 正经注释：防止 max_tokens 设置过高（如环境变量拼写错误） / 大白话注释：如果 max_tokens 设得太离谱就报错，可能是配置写错了
        raise ValueError(
            f"max_tokens={max_tokens} exceeds the largest output limit of "
            "any currently available model (128k as of late 2025). "
            "Check your FAST_TOKEN_LIMIT / SMART_TOKEN_LIMIT / "
            "STRATEGIC_TOKEN_LIMIT env vars for typos."
        )

    # Get the provider from supported providers
    provider_kwargs = {'model': model}  # 正经注释：初始化提供商参数字典 / 大白话注释：先放进去模型名字

    if llm_kwargs:  # 正经注释：合并额外的 LLM 参数 / 大白话注释：有额外参数就加进去
        provider_kwargs.update(llm_kwargs)

    if model in SUPPORT_REASONING_EFFORT_MODELS:  # 正经注释：推理模型设置推理力度参数 / 大白话注释：如果是推理模型（比如 o1），就设置推理力度
        provider_kwargs['reasoning_effort'] = reasoning_effort

    if model not in NO_SUPPORT_TEMPERATURE_MODELS:  # 正经注释：非推理模型设置温度和最大 Token 数 / 大白话注释：普通模型设置温度和最大输出长度
        provider_kwargs['temperature'] = temperature
        provider_kwargs['max_tokens'] = max_tokens
    else:  # 正经注释：推理模型不支持温度和最大 Token 参数 / 大白话注释：推理模型不支持这些参数，设为 None
        provider_kwargs['temperature'] = None
        provider_kwargs['max_tokens'] = None

    if llm_provider == "openai":  # 正经注释：OpenAI 提供商支持自定义 Base URL / 大白话注释：如果用的是 OpenAI，可以自定义 API 地址（比如用代理）
        base_url = os.environ.get("OPENAI_BASE_URL", None)
        if base_url:
            provider_kwargs['openai_api_base'] = base_url

    provider = get_llm(llm_provider, **provider_kwargs)  # 正经注释：创建 LLM 提供商实例 / 大白话注释：拿到一个能跟大模型聊天的对象
    response = ""
    # create response
    max_attempts = 1 if (stream and websocket is not None) else 10  # 正经注释：流式 WebSocket 模式不重试，普通模式最多重试 10 次 / 大白话注释：流式输出只试一次，普通模式可以试10次
    last_exception: Exception | None = None  # 正经注释：记录最后一次异常用于最终抛出 / 大白话注释：记住最后一次出错的原因
    for attempt in range(1, max_attempts + 1):
        try:
            response = await provider.get_chat_response(
                messages, stream, websocket, **kwargs
            )  # 正经注释：调用提供商获取聊天响应 / 大白话注释：把消息发给大模型，等它回答
        except Exception as exc:  # 正经注释：捕获请求异常 / 大白话注释：出错了
            last_exception = exc
            logging.getLogger(__name__).warning(
                f"LLM request failed (attempt {attempt}/{max_attempts}): {exc}"
            )  # 正经注释：记录失败日志 / 大白话注释：记一下第几次失败了
            if attempt < max_attempts:  # 正经注释：还有重试机会时等待后继续 / 大白话注释：还有机会就等一会再试
                await asyncio.sleep(min(2 ** (attempt - 1), 8))  # 正经注释：指数退避等待，最长 8 秒 / 大白话注释：等的时间越来越长，但最多等8秒
                continue
            break

        if not response:  # 正经注释：处理空响应 / 大白话注释：大模型啥也没返回
            last_exception = RuntimeError("Empty response from LLM provider")
            logging.getLogger(__name__).warning(
                f"LLM returned empty response (attempt {attempt}/{max_attempts})"
            )  # 正经注释：记录空响应警告 / 大白话注释：记一下收到空回答
            if attempt < max_attempts:  # 正经注释：还有重试机会时等待后继续 / 大白话注释：还有机会就等一会再试
                await asyncio.sleep(min(2 ** (attempt - 1), 8))
                continue
            break

        if cost_callback:  # 正经注释：如果提供了成本回调函数，计算并上报成本 / 大白话注释：有算钱函数的话就算一下花了多少钱
            llm_costs = calculate_llm_cost(
                llm_provider=llm_provider,
                model=model,
                input_content=str(messages),
                output_content=response,
                response_metadata=provider.last_response_metadata,
                usage_metadata=provider.last_usage_metadata,
                request_options=provider_kwargs,
            )
            cost_callback(llm_costs)  # 正经注释：调用回调函数报告成本 / 大白话注释：告诉调用方花了多少钱

        return response  # 正经注释：返回成功的响应 / 大白话注释：拿到了回答，返回出去

    logging.error(f"Failed to get response from {llm_provider} API")  # 正经注释：所有重试都失败后记录错误 / 大白话注释：试了好多次都失败了，记个错误日志
    raise RuntimeError(f"Failed to get response from {llm_provider} API") from last_exception  # 正经注释：抛出运行时异常 / 大白话注释：实在不行了，抛出异常告诉调用方


async def construct_subtopics(
    task: str,
    data: str,
    config,
    subtopics: list = [],
    prompt_family: type[PromptFamily] | PromptFamily = PromptFamily,
    **kwargs
) -> list:
    """
    【正经注释】
    基于给定的任务和数据，使用 LLM 构建研究子主题列表。
    通过 LangChain 的 PromptTemplate 和 PydanticOutputParser 构建 Chain，
    确保输出的子主题符合预定义的数据结构。

    【大白话注释】
    让大模型帮你把一个大研究任务拆成几个小话题。它会根据你给的任务和已有资料，
    自动规划出几个子研究方向，返回一个列表。

    Args:
        task (str): 主要任务或主题。
        data (str): 提供上下文的额外数据。
        config: 配置设置。
        subtopics (list, optional): 已有的子主题。默认 []。
        prompt_family (PromptFamily): 提示词族。
        **kwargs: 额外关键字参数。

    Returns:
        list: 构建的子主题列表。
    """
    try:
        parser = PydanticOutputParser(pydantic_object=Subtopics)  # 正经注释：创建 Pydantic 输出解析器，将 LLM 输出解析为 Subtopics 对象 / 大白话注释：准备一个解析器，把大模型的回答自动变成子主题列表

        prompt = PromptTemplate(
            template=prompt_family.generate_subtopics_prompt(),
            input_variables=["task", "data", "subtopics", "max_subtopics"],
            partial_variables={
                "format_instructions": parser.get_format_instructions()},
        )  # 正经注释：创建提示词模板，包含变量和格式化指令 / 大白话注释：把提示词模板拼好，告诉大模型要填什么变量、输出什么格式

        provider_kwargs = {'model': config.smart_llm_model}  # 正经注释：使用智能模型（SMART_LLM）来生成子主题 / 大白话注释：用聪明的大模型来拆子话题

        if config.llm_kwargs:  # 正经注释：合并额外的 LLM 参数 / 大白话注释：有额外参数就加上
            provider_kwargs.update(config.llm_kwargs)

        if config.smart_llm_model in SUPPORT_REASONING_EFFORT_MODELS:  # 正经注释：推理模型设置高推理力度 / 大白话注释：如果是推理模型就用高力度推理
            provider_kwargs['reasoning_effort'] = ReasoningEfforts.High.value
        else:  # 正经注释：普通模型设置温度和 Token 限制 / 大白话注释：普通模型设置温度和最大输出长度
            provider_kwargs['temperature'] = config.temperature
            provider_kwargs['max_tokens'] = config.smart_token_limit

        provider = get_llm(config.smart_llm_provider, **provider_kwargs)  # 正经注释：创建 LLM 提供商实例 / 大白话注释：拿到跟大模型聊天的对象

        model = provider.llm  # 正经注释：获取底层 LLM 实例 / 大白话注释：拿出真正的模型对象

        chain = prompt | model | parser  # 正经注释：构建 LangChain 管道：提示词 -> 模型 -> 解析器 / 大白话注释：把三步串起来——先拼提示词，再发给模型，最后解析结果

        output = await chain.ainvoke({
            "task": task,
            "data": data,
            "subtopics": subtopics,
            "max_subtopics": config.max_subtopics
        }, **kwargs)  # 正经注释：异步执行管道并获取解析后的子主题列表 / 大白话注释：执行整个流程，拿到子主题列表

        return output  # 正经注释：返回子主题列表 / 大白话注释：把结果返回出去

    except Exception as e:  # 正经注释：捕获解析异常，回退到原始子主题列表 / 大白话注释：出错了就打印一下，返回原来那个列表
        print("Exception in parsing subtopics : ", e)
        logging.getLogger(__name__).error("Exception in parsing subtopics : \n {e}")
        return subtopics
