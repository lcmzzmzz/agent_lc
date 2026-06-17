"""
agent_creator.py 的调试测试文件

【正经注释】
针对 gpt_researcher/actions/agent_creator.py 中三个函数的单元测试。
使用 if __name__ == '__main__' 方式，直接 python 运行即可调试。
通过 mock 模拟 LLM 返回，不消耗真实 API 额度。

【大白话注释】
直接 python 这个文件就能跑，不需要装 pytest。
所有测试都是 mock 的，不会真调 AI 接口，不花钱。
每个测试用 print 输出结果，方便你 debug。

用法：
    python tests/test_agent_creator.py
"""

import sys
import os

# 正经注释：将项目根目录加入 sys.path，确保直接运行时能 import gpt_researcher
# 大白话注释：告诉 Python "去这个目录找模块"，不然直接跑会报找不到 gpt_researcher
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from gpt_researcher.actions.agent_creator import (
    choose_agent,
    extract_json_with_regex,
    handle_json_error,
)


# ============================================================
# 辅助工具
# ============================================================

def make_fake_cfg():
    """
    【正经注释】用 SimpleNamespace 模拟 Config 对象，只提供 choose_agent 需要的字段。
    【大白话注释】造一个假配置，不用读真实配置文件。
    """
    return SimpleNamespace(
        smart_llm_model="openai:gpt-4o-mini",
        smart_llm_provider="openai",
        llm_kwargs={},
    )


def run_test(name, coro):
    """
    【正经注释】运行一个 async 测试并打印结果。
    【大白话注释】帮你跑异步测试的小工具，自动打印 通过/失败。
    """
    try:
        result = asyncio.run(coro)
        print(f"  [PASS] {name}")
        return True
    except AssertionError as e:
        print(f"  [FAIL] {name} → 断言失败: {e}")
        return False
    except Exception as e:
        print(f"  [ERR] {name} → 异常: {type(e).__name__}: {e}")
        return False


# ============================================================
# 测试 1：extract_json_with_regex（同步，纯逻辑，最简单）
# ============================================================

def test_extract_json_with_regex():
    """测试正则提取 JSON 的各种情况"""
    print("\n[TEST] extract_json_with_regex (正则提取 JSON)")
    passed = 0
    total = 0

    # --- 测试：正常 JSON ---
    total += 1
    response = '{"server": "科技专家", "agent_role_prompt": "你是一个科技研究员"}'
    result = extract_json_with_regex(response)
    assert result is not None, "应该返回非 None"
    assert '"server"' in result, "应该包含 server 字段"
    passed += 1
    print(f"  [PASS] 正常JSON直接返回 → {result}")

    # --- 测试：从废话中提取 JSON ---
    total += 1
    response = '好的，让我分析一下。{"server": "金融分析师", "agent_role_prompt": "你是金融专家"} 希望对你有帮助！'
    result = extract_json_with_regex(response)
    assert result is not None, "应该能从废话中提取出 JSON"
    assert '"server"' in result
    passed += 1
    print(f"  [PASS] 从废话中提取JSON → {result}")

    # --- 测试：多行 JSON ---
    total += 1
    response = '分析结果：\n{"server": "历史学者",\n "agent_role_prompt": "你是历史专家"}\n完成！'
    result = extract_json_with_regex(response)
    assert result is not None, "多行 JSON 也应该能提取"
    passed += 1
    print(f"  [PASS] 多行JSON也能提取 → {result}")

    # --- 测试：没有 JSON ---
    total += 1
    response = "这个问题我不知道该怎么回答"
    result = extract_json_with_regex(response)
    assert result is None, "没有 JSON 应该返回 None"
    passed += 1
    print(f"  [PASS] 没有JSON返回None → {result}")

    # --- 测试：空字符串 ---
    total += 1
    result = extract_json_with_regex("")
    assert result is None, "空字符串应该返回 None"
    passed += 1
    print(f"  [PASS] 空字符串返回None → {result}")

    # --- 测试：None ---
    total += 1
    result = extract_json_with_regex(None)
    assert result is None, "None 应该返回 None"
    passed += 1
    print(f"  [PASS] None输入返回None → {result}")

    print(f"  结果：{passed}/{total} 通过")
    return passed, total


# ============================================================
# 测试 2：handle_json_error（async，三层容错）
# ============================================================

async def test_handle_json_error():
    """测试 JSON 容错处理的三层抢救机制"""
    print("\n[TEST] handle_json_error (三层容错处理)")
    passed = 0
    total = 0

    # --- 第一层：标准 JSON 直接解析 ---
    total += 1
    response = '{"server": "科技专家", "agent_role_prompt": "你是科技领域研究员"}'
    server, role = await handle_json_error(response)
    assert server == "科技专家", f"server 应该是'科技专家'，实际是'{server}'"
    assert "科技领域研究员" in role
    passed += 1
    print(f"  [PASS] 合法JSON直接解析 → server={server}, role={role[:30]}...")

    # --- 第一层兜底：损坏 JSON 用 json_repair 修复 ---
    total += 1
    response = '{"server": "金融分析师", "agent_role_prompt": "你是金融专家",}'  # 末尾多了逗号
    server, role = await handle_json_error(response)
    assert server == "金融分析师", f"json_repair 应该能修复，实际 server={server}"
    passed += 1
    print(f"  [PASS] 损坏JSON用json_repair修复 → server={server}")

    # --- 第二层：夹杂废话的 JSON 通过正则提取 ---
    total += 1
    response = '我来分析：{"server": "医学专家", "agent_role_prompt": "你是医学研究员"} 希望有帮助！'
    server, role = await handle_json_error(response)
    assert server == "医学专家", f"正则应该能提取，实际 server={server}"
    passed += 1
    print(f"  [PASS] 夹杂废话通过正则提取 → server={server}")

    # --- 第三层：完全无法解析 → 默认角色 ---
    total += 1
    response = "抱歉，我无法处理这个请求"
    server, role = await handle_json_error(response)
    assert server == "Default Agent", f"应该兜底为 Default Agent，实际是'{server}'"
    assert "research assistant" in role
    passed += 1
    print(f"  [PASS] 完全无法解析返回默认角色 → server={server}")

    # --- None 输入 ---
    total += 1
    server, role = await handle_json_error(None)
    assert server == "Default Agent"
    passed += 1
    print(f"  [PASS] None输入返回默认角色 → server={server}")

    # --- 空字符串 ---
    total += 1
    server, role = await handle_json_error("")
    assert server == "Default Agent"
    passed += 1
    print(f"  [PASS] 空字符串返回默认角色 → server={server}")

    print(f"  结果：{passed}/{total} 通过")
    return passed, total


# ============================================================
# 测试 3：choose_agent（async，mock LLM 调用）
# ============================================================

async def test_choose_agent():
    """测试智能体选择的完整流程（mock 掉 LLM）"""
    print("\n[TEST] choose_agent (智能体选择, mock LLM)")
    passed = 0
    total = 0
    fake_cfg = make_fake_cfg()

    # --- 正常路径：LLM 返回合法 JSON ---
    total += 1
    fake_response = '{"server": "科技专家", "agent_role_prompt": "你是资深科技领域研究员"}'
    with patch(
        "gpt_researcher.actions.agent_creator.create_chat_completion",
        new_callable=AsyncMock,
        return_value=fake_response,
    ):
        server, role = await choose_agent(query="量子计算最新进展", cfg=fake_cfg)

    assert server == "科技专家", f"server 应该是'科技专家'，实际是'{server}'"
    assert "科技领域研究员" in role
    passed += 1
    print(f"  [PASS] LLM返回合法JSON → server={server}, role={role[:30]}...")

    # --- 异常路径：LLM 返回夹杂废话的 JSON → 走容错 ---
    total += 1
    fake_response = '分析完成！{"server": "金融分析师", "agent_role_prompt": "你是金融专家"} 祝好运！'
    with patch(
        "gpt_researcher.actions.agent_creator.create_chat_completion",
        new_callable=AsyncMock,
        return_value=fake_response,
    ):
        server, role = await choose_agent(query="A股走势分析", cfg=fake_cfg)

    assert server == "金融分析师", f"容错应该能解析，实际 server={server}"
    passed += 1
    print(f"  [PASS] LLM返回非标准JSON走容错 → server={server}")

    # --- 最差路径：LLM 完全乱说 → 兜底 ---
    total += 1
    fake_response = "对不起，我不太理解你的问题"
    with patch(
        "gpt_researcher.actions.agent_creator.create_chat_completion",
        new_callable=AsyncMock,
        return_value=fake_response,
    ):
        server, role = await choose_agent(query="测试问题", cfg=fake_cfg)

    assert server == "Default Agent", f"应该兜底，实际 server={server}"
    passed += 1
    print(f"  [PASS] LLM完全乱说走兜底 → server={server}")

    # --- 有父查询时正确拼接 ---
    total += 1
    fake_response = '{"server": "AI专家", "agent_role_prompt": "你是AI研究员"}'
    with patch(
        "gpt_researcher.actions.agent_creator.create_chat_completion",
        new_callable=AsyncMock,
        return_value=fake_response,
    ) as mock_llm:
        await choose_agent(
            query="大模型训练技巧",
            cfg=fake_cfg,
            parent_query="AI 发展趋势",
        )
        # 检查传给 LLM 的 user message
        call_args = mock_llm.call_args
        user_message = call_args.kwargs["messages"][1]["content"]
        assert "AI 发展趋势" in user_message, "应该包含父查询"
        assert "大模型训练技巧" in user_message, "应该包含子查询"
    passed += 1
    print(f"  [PASS] 有父查询时正确拼接 → user_message={user_message}")

    # --- 无父查询时不拼接 ---
    total += 1
    fake_response = '{"server": "通用专家", "agent_role_prompt": "你是研究员"}'
    with patch(
        "gpt_researcher.actions.agent_creator.create_chat_completion",
        new_callable=AsyncMock,
        return_value=fake_response,
    ) as mock_llm:
        await choose_agent(query="量子计算", cfg=fake_cfg)
        call_args = mock_llm.call_args
        user_message = call_args.kwargs["messages"][1]["content"]
        assert user_message == "task: 量子计算", f"应该只有子查询，实际是'{user_message}'"
        assert " - " not in user_message, "不应该有分隔符"
    passed += 1
    print(f"  [PASS] 无父查询时不拼接 → user_message={user_message}")

    print(f"  结果：{passed}/{total} 通过")
    return passed, total


# ============================================================
# 主入口：跑全部测试
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("[TEST] agent_creator.py 测试开始")
    print("=" * 60)

    total_passed = 0
    total_count = 0

    # 测试 1：同步函数，直接跑
    p, t = test_extract_json_with_regex()
    total_passed += p
    total_count += t

    # 测试 2：async 函数
    p, t = asyncio.run(test_handle_json_error())
    total_passed += p
    total_count += t

    # 测试 3：async 函数 + mock
    p, t = asyncio.run(test_choose_agent())
    total_passed += p
    total_count += t

    # 汇总
    print("\n" + "=" * 60)
    if total_passed == total_count:
        print(f"[PASS] 全部通过! {total_passed}/{total_count}")
    else:
        print(f"[FAIL] 部分失败: {total_passed}/{total_count} 通过")
    print("=" * 60)
