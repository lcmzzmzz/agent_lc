"""
MCP (Model Context Protocol) Integration for GPT Researcher

【正经注释】
本模块为 GPT Researcher 提供 MCP（模型上下文协议）的完整集成支持，包含以下核心功能：
- MCP 服务器客户端的生命周期管理
- 基于大语言模型的智能工具选择与执行
- 利用 MCP 工具执行研究任务
- 基于 WebSocket 的实时流式输出支持

【大白话注释】
这个文件是 MCP 功能的"总入口"。MCP 就是让 AI 能调用外部工具的协议。
这里负责把所有 MCP 相关的模块（客户端管理、工具选择、研究执行、流式输出）
打包在一起，统一导出。如果用户的电脑上没装 langchain-mcp-adapters 这个包，
也不会报错崩溃，只是 MCP 功能不可用而已。
"""

import logging  # 正经注释：导入日志模块用于记录模块运行信息 / 大白话注释：拿来打日志的，出了问题好排查

logger = logging.getLogger(__name__)  # 正经注释：创建以当前模块名命名的日志记录器 / 大白话注释：给这个模块单独搞一个日志记录器

try:
    # Check if langchain-mcp-adapters is available
    # 正经注释：尝试导入 langchain-mcp-adapters 库中的多服务器客户端类，检测 MCP 依赖是否可用
    # 大白话注释：先试试能不能导入 MCP 的核心库，能导入说明环境装好了
    from langchain_mcp_adapters.client import MultiServerMCPClient
    HAS_MCP_ADAPTERS = True  # 正经注释：标记 MCP 适配器已安装可用 / 大白话注释：插个旗子，说明 MCP 功能能用了
    logger.debug("langchain-mcp-adapters is available")

    # Import core MCP components
    # 正经注释：导入 MCP 子模块的核心组件：客户端管理器、工具选择器、研究技能、流式输出器
    # 大白话注释：把 MCP 的四大金刚（客户端管理、工具选择、研究执行、流式输出）都引进来
    from .client import MCPClientManager
    from .tool_selector import MCPToolSelector
    from .research import MCPResearchSkill
    from .streaming import MCPStreamer

    __all__ = [  # 正经注释：定义模块的公开导出列表，控制 from mcp import * 时的导出范围 / 大白话注释：声明哪些东西是对外公开的
        "MCPClientManager",
        "MCPToolSelector",
        "MCPResearchSkill",
        "MCPStreamer",
        "HAS_MCP_ADAPTERS"
    ]
    
except ImportError as e:  # 正经注释：捕获导入错误，当 MCP 依赖库未安装时进入此分支 / 大白话注释：没装 MCP 相关的包就会走到这里，不会让程序崩掉
    logger.warning(f"MCP dependencies not available: {e}")
    HAS_MCP_ADAPTERS = False  # 正经注释：标记 MCP 适配器不可用 / 大白话注释：插个旗子，说明 MCP 功能用不了
    __all__ = ["HAS_MCP_ADAPTERS"]  # 正经注释：仅导出可用性标志 / 大白话注释：只导出一个"能不能用"的标志

except Exception as e:  # 正经注释：捕获其他意外异常，确保模块导入不会导致整个应用崩溃 / 大白话注释：兜底处理，万一出了什么幺蛾子也不会让程序炸
    logger.error(f"Unexpected error importing MCP components: {e}")
    HAS_MCP_ADAPTERS = False
    __all__ = ["HAS_MCP_ADAPTERS"] 