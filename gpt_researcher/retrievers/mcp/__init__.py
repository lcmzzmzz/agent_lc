"""
MCP（模型上下文协议）检索器子模块入口。

【正经注释】本模块为MCP检索器的子包初始化文件，负责在langchain-mcp-adapters包可用时
导入MCPRetriever类，否则提供None占位符，确保主程序不会因缺少可选依赖而崩溃。

【大白话注释】这个文件是个"安全门"——如果系统里装了MCP相关的包，
就把MCPRetriever导出来用；没装的话也不报错，只是告诉你"没这个功能"。
就像你家没装空调，也不会导致房子塌了，只是没有冷气而已。
"""
import logging  # 正经注释：日志记录模块 / 大白话注释：记日志用的

logger = logging.getLogger(__name__)  # 正经注释：创建当前模块的日志记录器 / 大白话注释：给这个文件搞个专属日志记录器

try:
    # Check if langchain-mcp-adapters is available
    from langchain_mcp_adapters.client import MultiServerMCPClient  # 正经注释：尝试导入MCP适配器客户端 / 大白话注释：看看MCP适配器包装了没有
    HAS_MCP_ADAPTERS = True  # 正经注释：标记MCP适配器可用 / 大白话注释：记一下"装了"
    logger.debug("langchain-mcp-adapters is available")

    # Import the retriever
    from .retriever import MCPRetriever  # 正经注释：导入MCP检索器实现类 / 大白话注释：把MCPRetriever拿进来
    __all__ = ["MCPRetriever"]  # 正经注释：导出MCPRetriever / 大白话注释：告诉外面这个模块卖什么
    logger.debug("MCPRetriever imported successfully")

except ImportError as e:
    # Log the specific import error for debugging
    logger.warning(f"Failed to import MCPRetriever: {e}")  # 正经注释：记录导入失败的警告 / 大白话注释：记一下"没装成功"
    # MCP package not installed or other import error, provide a placeholder
    MCPRetriever = None  # 正经注释：设置为None占位符 / 大白话注释：没装就设成空的，不影响其他功能
    __all__ = []  # 正经注释：不导出任何内容 / 大白话注释：告诉外面"暂时没货"
except Exception as e:
    # Catch any other exception that might occur
    logger.error(f"Unexpected error importing MCPRetriever: {e}")  # 正经注释：记录意外错误 / 大白话注释：记一下出了什么岔子
    MCPRetriever = None  # 正经注释：设置为None占位符 / 大白话注释：出错了也设成空的
    __all__ = []  # 正经注释：不导出任何内容 / 大白话注释：告诉外面"暂时没货"
