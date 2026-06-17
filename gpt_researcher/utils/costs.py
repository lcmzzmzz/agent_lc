"""
【正经注释】
LLM API 使用成本估算工具模块。提供基于 Token 计数的 OpenAI 定价成本估算、
Anthropic 模型的精确成本计算、以及文档嵌入成本估算功能。

【大白话注释】
这个文件就是用来算钱的——你调了大模型的 API，这里帮你算到底花了多少美元。
支持 OpenAI 和 Anthropic 两家的计价方式，还能算嵌入（Embedding）的费用。
"""

from __future__ import annotations  # 正经注释：启用延迟注解评估，支持新式类型语法 / 大白话注释：让类型提示更好写，不用担心前后引用问题

import logging  # 正经注释：标准日志库，用于记录运行时信息 / 大白话注释：打日志用的，出问题了方便排查
from collections.abc import Mapping  # 正经注释：导入 Mapping 抽象基类，用于类型检查映射类型 / 大白话注释：用来判断某个东西是不是字典-like的对象
from typing import Any  # 正经注释：导入 Any 类型，表示任意类型 / 大白话注释：什么类型都行的兜底类型

import tiktoken  # 正经注释：OpenAI 的 Token 计数库，用于精确计算文本的 Token 数量 / 大白话注释：OpenAI 官方的数词工具，帮你算一段文字有多少个 Token

# Per OpenAI Pricing Page: https://openai.com/api/pricing/
ENCODING_MODEL = "o200k_base"  # 正经注释：指定用于 Token 计数的编码模型 / 大白话注释：用哪个编码器来数 Token
INPUT_COST_PER_TOKEN = 0.000005  # 正经注释：每输入 Token 的成本（美元） / 大白话注释：每输入一个 Token 收多少钱
OUTPUT_COST_PER_TOKEN = 0.000015  # 正经注释：每输出 Token 的成本（美元） / 大白话注释：每输出一个 Token 收多少钱
IMAGE_INFERENCE_COST = 0.003825  # 正经注释：图像推理的单次成本（美元） / 大白话注释：每次让模型看图收多少钱
EMBEDDING_COST = 0.02 / 1000000  # Assumes new ada-3-small  # 正经注释：每 Token 的嵌入成本，基于 ada-3-small 定价 / 大白话注释：做文本嵌入时每个 Token 多少钱

logger = logging.getLogger(__name__)  # 正经注释：创建当前模块的日志记录器 / 大白话注释：给自己搞个专属日志器

ANTHROPIC_MODEL_PRICING = (  # 正经注释：Anthropic 各模型的定价表，元组格式为 (模型名模式, 输入价格/百万Token, 输出价格/百万Token) / 大白话注释：Anthropic 家模型的价目表
    (("claude-opus-4-7",), 5.0, 25.0),
    (("claude-opus-4-6",), 5.0, 25.0),
    (("claude-opus-4-5", "claude-4-opus"), 5.0, 25.0),
    (("claude-opus-4-1",), 15.0, 75.0),
    (("claude-opus-4",), 15.0, 75.0),
    (("claude-sonnet-4-6",), 3.0, 15.0),
    (("claude-sonnet-4-5", "claude-4-sonnet"), 3.0, 15.0),
    (("claude-sonnet-4",), 3.0, 15.0),
    (("claude-haiku-4-5",), 1.0, 5.0),
    (("claude-3-5-haiku",), 0.8, 4.0),
)

ANTHROPIC_US_INFERENCE_GEO_MODELS = (  # 正经注释：需要按美国区域定价加成的 Anthropic 模型列表 / 大白话注释：这些模型如果指定在美国跑，价格要贵10%
    "claude-opus-4-7",
    "claude-opus-4-6",
    "claude-sonnet-4-6",
)


def estimate_llm_cost(input_content: str, output_content: str) -> float:
    """
    【正经注释】
    基于 OpenAI 定价估算 LLM API 调用成本。通过 tiktoken 编码器计算输入和输出的 Token 数量，
    再乘以对应的单价得到总成本估算值。

    【大白话注释】
    算一算这次调 API 大概花了多少钱。把输入和输出的文字都数一下 Token，
    然后乘以单价，加在一起就是总花费。

    Args:
        input_content: 发送给 LLM 的输入文本。
        output_content: 从 LLM 接收的输出文本。

    Returns:
        估算的美元成本。
    """
    encoding = tiktoken.get_encoding(ENCODING_MODEL)  # 正经注释：获取指定编码器的实例 / 大白话注释：拿一个数 Token 的工具
    input_tokens = encoding.encode(input_content)  # 正经注释：将输入文本编码为 Token 列表 / 大白话注释：把输入文字变成 Token
    output_tokens = encoding.encode(output_content)  # 正经注释：将输出文本编码为 Token 列表 / 大白话注释：把输出文字变成 Token
    input_costs = len(input_tokens) * INPUT_COST_PER_TOKEN  # 正经注释：计算输入成本 / 大白话注释：输入花了多少钱
    output_costs = len(output_tokens) * OUTPUT_COST_PER_TOKEN  # 正经注释：计算输出成本 / 大白话注释：输出花了多少钱
    return input_costs + output_costs  # 正经注释：返回总成本 / 大白话注释：加一起就是总共花的钱


def _mapping_to_dict(value: Mapping[str, Any] | Any | None) -> dict[str, Any]:
    """
    【正经注释】
    将各种映射类型安全地转换为标准字典。支持 Mapping 对象、带有 model_dump 方法的对象（如 Pydantic 模型），
    以及 None 值的转换。

    【大白话注释】
    不管你给它什么奇奇怪怪的对象，它都试着给你变成一个普通字典。
    如果是 None 就给你空字典，是字典-like 就转成真字典，有 model_dump 就调那个方法。
    """
    if value is None:  # 正经注释：处理 None 输入 / 大白话注释：啥也没有就返回空字典
        return {}
    if isinstance(value, Mapping):  # 正经注释：处理 Mapping 类型输入 / 大白话注释：是字典-like 的就转成真字典
        return dict(value)
    if hasattr(value, "model_dump"):  # 正经注释：处理 Pydantic 模型等带有 model_dump 方法的对象 / 大白话注释：有 model_dump 方法的就调它
        return dict(value.model_dump())
    return {}  # 正经注释：无法识别的类型返回空字典 / 大白话注释：都不认识就返回空字典


def _resolve_anthropic_model_name(
    model: str | None,
    response_metadata: Mapping[str, Any] | None = None,
) -> str:
    """
    【正经注释】
    解析 Anthropic 模型名称。优先从响应元数据中提取模型名称，依次尝试 'model' 和 'model_name' 字段，
    最后回退到传入的 model 参数。

    【大白话注释】
    搞清楚到底用的是哪个 Anthropic 模型。先从返回的元数据里找，找不到就用你传进来的那个名字。

    Args:
        model: 传入的模型名称（可能为 None）。
        response_metadata: API 响应的元数据映射。

    Returns:
        小写的模型名称字符串。
    """
    metadata = _mapping_to_dict(response_metadata)  # 正经注释：将响应元数据转换为字典 / 大白话注释：先把元数据变成字典
    return str(
        metadata.get("model")
        or metadata.get("model_name")
        or model
        or ""
    ).lower()  # 正经注释：按优先级获取模型名称并转为小写 / 大白话注释：一个一个试，找到了就变成小写返回


def _extract_anthropic_usage(
    response_metadata: Mapping[str, Any] | None = None,
    usage_metadata: Mapping[str, Any] | Any | None = None,
) -> dict[str, int] | None:
    """
    【正经注释】
    从响应元数据和使用量元数据中提取 Anthropic API 的 Token 使用量信息。
    优先从 response_metadata 中的 usage 字段提取，其次从独立的 usage_metadata 提取。

    【大白话注释】
    从各种地方找 Anthropic 告诉你用了多少 Token 的信息。
    先在一个地方找，找不到就去另一个地方找，都找不到就返回 None。

    Args:
        response_metadata: API 响应的元数据。
        usage_metadata: 独立的使用量元数据。

    Returns:
        包含 input_tokens 和 output_tokens 的字典，或 None。
    """
    metadata = _mapping_to_dict(response_metadata)  # 正经注释：转换响应元数据为字典 / 大白话注释：先把响应元数据变成字典
    usage = _mapping_to_dict(metadata.get("usage"))  # 正经注释：从元数据中提取 usage 字段 / 大白话注释：从里面再找 usage 信息

    if usage:  # 正经注释：如果从 response_metadata 中找到了 usage 信息 / 大白话注释：找到了就用
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        if input_tokens is not None and output_tokens is not None:  # 正经注释：确保两个值都存在 / 大白话注释：输入输出 Token 数都有才算数
            return {
                "input_tokens": int(input_tokens),
                "output_tokens": int(output_tokens),
            }

    usage = _mapping_to_dict(usage_metadata)  # 正经注释：尝试从独立的 usage_metadata 提取 / 大白话注释：前面没找到，换一个地方找
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    if input_tokens is None or output_tokens is None:  # 正经注释：缺少任一值则返回 None / 大白话注释：缺了哪个都不行，返回空
        return None

    return {
        "input_tokens": int(input_tokens),
        "output_tokens": int(output_tokens),
    }


def _get_anthropic_pricing(model_name: str) -> tuple[float, float] | None:
    """
    【正经注释】
    根据模型名称查找对应的 Anthropic 定价。遍历 ANTHROPIC_MODEL_PRICING 表，
    返回匹配的（输入价格, 输出价格）元组。

    【大白话注释】
    给它一个模型名字，它帮你查出这个模型输入和输出分别多少钱。
    去价目表里一个一个比对，找到了就告诉你价格，找不到就返回 None。

    Args:
        model_name: 模型名称（小写）。

    Returns:
        (输入每百万Token价格, 输出每百万Token价格) 或 None。
    """
    normalized_model_name = model_name.lower()  # 正经注释：统一转为小写以进行匹配 / 大白话注释：名字都变小写再比较
    for patterns, input_price_per_mtok, output_price_per_mtok in ANTHROPIC_MODEL_PRICING:
        if any(pattern in normalized_model_name for pattern in patterns):  # 正经注释：检查模型名是否匹配任一模式 / 大白话注释：看看名字里有没有包含这个关键词
            return input_price_per_mtok, output_price_per_mtok
    return None  # 正经注释：未找到匹配的定价 / 大白话注释：价目表里没找到，返回空


def _get_anthropic_pricing_multiplier(
    model_name: str,
    request_options: Mapping[str, Any] | None = None,
) -> float:
    """
    【正经注释】
    获取 Anthropic 定价的地域乘数。对于特定模型在美国区域推理时，应用 1.1 倍的价格加成。

    【大白话注释】
    有些 Anthropic 模型在美国区域跑要加价 10%，这个函数就是算这个加价的。
    如果不是美国区域或者不是那几个特殊模型，乘数就是 1.0，不加价。

    Args:
        model_name: 模型名称。
        request_options: 请求选项，包含 inference_geo 等信息。

    Returns:
        价格乘数。
    """
    if not request_options:  # 正经注释：无请求选项时使用默认乘数 / 大白话注释：没有额外选项就不加价
        return 1.0

    inference_geo = str(request_options.get("inference_geo", "")).lower()  # 正经注释：获取推理地域设置 / 大白话注释：看看是不是指定了美国区域
    if inference_geo != "us":  # 正经注释：非美国区域不加价 / 大白话注释：不是美国就不加价
        return 1.0

    if any(pattern in model_name for pattern in ANTHROPIC_US_INFERENCE_GEO_MODELS):  # 正经注释：检查是否为需要加价的模型 / 大白话注释：看看是不是那几个要加价的模型
        return 1.1  # 正经注释：美国区域加价 10% / 大白话注释：加价 10%

    return 1.0


def calculate_anthropic_cost(
    model: str | None,
    response_metadata: Mapping[str, Any] | None = None,
    usage_metadata: Mapping[str, Any] | Any | None = None,
    request_options: Mapping[str, Any] | None = None,
) -> float | None:
    """
    【正经注释】
    计算 Anthropic API 调用的精确成本。提取 Token 使用量、匹配模型定价、应用地域乘数，
    综合计算最终费用。

    【大白话注释】
    精确计算调用 Anthropic 模型花了多少钱。先看你用了多少 Token，再查价格表，
    如果是美国区域还要加价，最后算出一个精确数字。

    Args:
        model: 模型名称。
        response_metadata: API 响应元数据。
        usage_metadata: 使用量元数据。
        request_options: 请求选项。

    Returns:
        精确的美元成本，或 None（无法计算时）。
    """
    usage = _extract_anthropic_usage(response_metadata=response_metadata, usage_metadata=usage_metadata)  # 正经注释：提取 Token 使用量 / 大白话注释：先看用了多少 Token
    if not usage:  # 正经注释：无法提取使用量时返回 None / 大白话注释：找不到用了多少 Token 就算不了，返回空
        return None

    model_name = _resolve_anthropic_model_name(model=model, response_metadata=response_metadata)  # 正经注释：解析模型名称 / 大白话注释：搞清楚是哪个模型
    pricing = _get_anthropic_pricing(model_name)  # 正经注释：获取模型定价 / 大白话注释：查价格表
    if pricing is None:  # 正经注释：未找到定价时记录警告并回退 / 大白话注释：价目表里没有这个模型，记个警告
        logger.warning(
            "Missing Anthropic pricing rule for model '%s'; falling back to token estimator.",
            model_name or model,
        )
        return None

    input_price_per_mtok, output_price_per_mtok = pricing  # 正经注释：解包定价元组 / 大白话注释：拿到输入和输出的单价
    multiplier = _get_anthropic_pricing_multiplier(model_name, request_options=request_options)  # 正经注释：获取地域价格乘数 / 大白话注释：算算要不要加价
    input_cost = usage["input_tokens"] * input_price_per_mtok / 1_000_000  # 正经注释：计算输入成本 / 大白话注释：输入花了多少钱
    output_cost = usage["output_tokens"] * output_price_per_mtok / 1_000_000  # 正经注释：计算输出成本 / 大白话注释：输出花了多少钱
    return (input_cost + output_cost) * multiplier  # 正经注释：返回含乘数的总成本 / 大白话注释：加一起再乘以加价倍数，就是最终花费


def calculate_llm_cost(
    llm_provider: str | None,
    model: str | None,
    input_content: str,
    output_content: str,
    response_metadata: Mapping[str, Any] | None = None,
    usage_metadata: Mapping[str, Any] | Any | None = None,
    request_options: Mapping[str, Any] | None = None,
) -> float:
    """
    【正经注释】
    通用 LLM 成本计算入口函数。根据 LLM 提供商选择对应的成本计算方式：
    Anthropic 使用精确计价，其他提供商使用基于 Token 计数的估算方式。

    【大白话注释】
    这是算钱的总入口。先看你是哪家的模型，Anthropic 就用精确算法，
    其他家就用估算算法（数 Token 乘以单价）。

    Args:
        llm_provider: LLM 提供商名称。
        model: 模型名称。
        input_content: 输入文本内容。
        output_content: 输出文本内容。
        response_metadata: API 响应元数据。
        usage_metadata: 使用量元数据。
        request_options: 请求选项。

    Returns:
        估算的美元成本。
    """
    if llm_provider == "anthropic":  # 正经注释：Anthropic 提供商使用精确成本计算 / 大白话注释：如果是 Anthropic 的模型
        anthropic_cost = calculate_anthropic_cost(
            model=model,
            response_metadata=response_metadata,
            usage_metadata=usage_metadata,
            request_options=request_options,
        )
        if anthropic_cost is not None:  # 正经注释：精确计算成功时直接返回 / 大白话注释：精确算出来了就用这个数
            return anthropic_cost

    return estimate_llm_cost(input_content, output_content)  # 正经注释：回退到基于 Token 的估算方式 / 大白话注释：其他家或者算不出来的，就用估算


def estimate_embedding_cost(model: str, docs: list) -> float:
    """
    【正经注释】
    估算文档嵌入成本。使用指定模型对应的编码器计算所有文档的总 Token 数，
    再乘以嵌入单价得到总成本。

    【大白话注释】
    算一算把这些文档做成向量嵌入要花多少钱。把所有文档的 Token 都数一遍，
    乘以单价就是总花费。

    Args:
        model: 嵌入模型名称。
        docs: 待嵌入的文档列表。

    Returns:
        估算的嵌入成本（美元）。
    """
    encoding = tiktoken.encoding_for_model(model)  # 正经注释：获取指定模型对应的编码器 / 大白话注释：拿一个跟模型配套的数 Token 工具
    total_tokens = sum(len(encoding.encode(str(doc))) for doc in docs)  # 正经注释：计算所有文档的总 Token 数 / 大白话注释：把所有文档的 Token 都加起来
    return total_tokens * EMBEDDING_COST  # 正经注释：返回总嵌入成本 / 大白话注释：Token 总数乘以单价就是总花费
