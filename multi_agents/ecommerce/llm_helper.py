"""
LLM 调用辅助：注入式 llm_fn + JSON 提取 + 规则 fallback。

【正经注释】
把"调 LLM"抽象成可注入的 LlmFn（system, user -> text），
默认实现 default_llm_fn 复用 GPT Researcher 的 Config + create_chat_completion。
llm_json / llm_text 统一做异常吞掉、JSON 提取，返回 (result, used)，
让 Agent 可以"LLM 优先、规则兜底"，且测试可用 fake_llm 替换、不触网不花钱。

【大白话注释】
跟大模型打交道的统一工具：默认用项目自带的大模型，
也能换成假的（测试用）。调失败就返回"没用到 LLM"，
让上层自动退回原来的规则打分，不会崩。
"""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable

# 注入式 LLM 函数签名：(system_prompt, user_prompt) -> 模型输出文本
LlmFn = Callable[[str, str], Awaitable[str]]


async def default_llm_fn(system: str, user: str) -> str:
    """默认 LLM 调用：复用 GPT Researcher 的 SMART_LLM 配置。"""
    from gpt_researcher.config import Config
    from gpt_researcher.utils.llm import create_chat_completion

    cfg = Config()
    return await create_chat_completion(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        model=cfg.smart_llm_model,
        llm_provider=cfg.smart_llm_provider,
        llm_kwargs=cfg.llm_kwargs,
        max_tokens=1500,
        temperature=0.3,
    )


_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL)


def extract_json(text: str) -> dict | None:
    """从模型输出中提取首个 JSON 对象（兼容 ```json 代码块）。"""
    if not text:
        return None
    match = _JSON_BLOCK_RE.search(text)
    candidate = match.group(1) if match else text
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(candidate[start : end + 1])
    except Exception:
        return None


def clamp(value) -> float:
    """把分数限制在 [0, 10]。"""
    return float(max(0.0, min(10.0, value)))


async def llm_json(llm_fn: LlmFn | None, system: str, user: str):
    """调 LLM 取 JSON dict。返回 (dict | None, used_llm)。"""
    if llm_fn is None:
        return None, False
    try:
        raw = await llm_fn(system, user)
    except Exception:
        return None, False
    data = extract_json(raw)
    return (data, True) if isinstance(data, dict) else (None, False)


async def llm_text(llm_fn: LlmFn | None, system: str, user: str):
    """调 LLM 取纯文本。返回 (text | None, used_llm)。"""
    if llm_fn is None:
        return None, False
    try:
        raw = await llm_fn(system, user)
    except Exception:
        return None, False
    text = (raw or "").strip()
    return (text, True) if text else (None, False)
