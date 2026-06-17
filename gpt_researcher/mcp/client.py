"""
MCP Client Management Module

Handles MCP client creation, configuration conversion, and connection management.

【正经注释】
本模块负责 MCP（模型上下文协议）客户端的完整生命周期管理，包括：
- 将 GPT Researcher 的 MCP 配置格式转换为 langchain-mcp-adapters 所需格式
- 创建和管理 MultiServerMCPClient 实例，支持多种传输协议（stdio、websocket、http）
- 处理客户端连接清理和资源回收
- 从 MCP 服务器获取可用工具列表

【大白话注释】
这个文件是 MCP 的"客户端管家"。它的活儿就是：把用户配好的 MCP 服务器信息
翻译成 langchain 库能看懂的格式，然后创建连接、管理生命周期、获取工具列表。
说白了就是帮 AI 和外部工具之间"牵线搭桥"。
"""
import asyncio  # 正经注释：导入异步IO库，用于协程调度和异步锁 / 大白话注释：异步编程必备，让代码能同时干多件事
import logging  # 正经注释：导入日志模块，用于记录运行状态和错误信息 / 大白话注释：打日志用的，出了bug好查
from typing import List, Dict, Any, Optional  # 正经注释：导入类型提示，用于函数签名的静态类型标注 / 大白话注释：类型标注，让代码更清晰，编辑器也好提示

try:
    from langchain_mcp_adapters.client import MultiServerMCPClient  # 正经注释：导入多服务器MCP客户端 / 大白话注释：试试能不能导入MCP的核心客户端类
    HAS_MCP_ADAPTERS = True  # 正经注释：标记适配器可用 / 大白话注释：能用！
except ImportError:
    HAS_MCP_ADAPTERS = False  # 正经注释：标记适配器不可用 / 大白话注释：不能用，缺依赖

logger = logging.getLogger(__name__)  # 正经注释：创建当前模块的日志记录器 / 大白话注释：给这个文件搞个专属日志器


class MCPClientManager:
    """
    Manages MCP client lifecycle and configuration.

    Responsible for:
    - Converting GPT Researcher MCP configs to langchain format
    - Creating and managing MultiServerMCPClient instances
    - Handling client cleanup and resource management

    【正经注释】
    MCP 客户端管理器，负责将用户提供的 MCP 服务器配置转换为 langchain-mcp-adapters
    所需的标准格式，并管理客户端实例的创建、复用和销毁。通过异步锁保证并发安全。

    【大白话注释】
    这个类就是 MCP 的"大管家"。你把 MCP 服务器的配置告诉它，它帮你翻译成
    langchain 能识别的格式，然后创建连接、管理连接，最后还能帮你关掉连接。
    用了锁机制，防止多线程同时搞出多个连接。
    """

    def __init__(self, mcp_configs: List[Dict[str, Any]]):
        """
        Initialize the MCP client manager.

        Args:
            mcp_configs: List of MCP server configurations from GPT Researcher

        【正经注释】
        初始化客户端管理器，接收 MCP 服务器配置列表，初始化客户端实例为空，
        并创建异步锁以保证并发场景下的线程安全。

        【大白话注释】
        构造函数，把配置存起来，客户端先设为 None（还没创建连接呢），
        再搞一把"锁"防止多个人同时抢着创建连接。
        """
        self.mcp_configs = mcp_configs or []  # 正经注释：存储MCP配置列表，若为空则使用空列表 / 大白话注释：把配置存下来，没传就当空的
        self._client = None  # 正经注释：客户端实例初始为空，采用懒加载策略 / 大白话注释：客户端还没创建，先设为None
        self._client_lock = asyncio.Lock()  # 正经注释：异步锁，保证客户端创建/关闭操作的原子性 / 大白话注释：一把锁，防止并发时重复创建连接

    def convert_configs_to_langchain_format(self) -> Dict[str, Dict[str, Any]]:
        """
        Convert GPT Researcher MCP configs to langchain-mcp-adapters format.

        Returns:
            Dict[str, Dict[str, Any]]: Server configurations for MultiServerMCPClient

        【正经注释】
        将 GPT Researcher 的 MCP 配置列表转换为 langchain-mcp-adapters 要求的
        MultiServerMCPClient 配置格式。自动检测传输协议类型（websocket、http、stdio），
        并处理命令行参数、环境变量和认证令牌等配置项。

        【大白话注释】
        这个方法就是个"翻译器"，把用户写的配置翻译成 langchain 库能识别的格式。
        它会看 URL 是什么开头来判断用哪种连接方式（ws/wss走websocket，
        http/https走HTTP，没有URL就走命令行方式），还要处理参数、环境变量、
        认证token这些杂七杂八的东西。
        """
        server_configs = {}  # 正经注释：初始化服务器配置字典 / 大白话注释：准备一个空字典装翻译好的配置

        for i, config in enumerate(self.mcp_configs):
            # Generate server name
            # 正经注释：为每个服务器生成唯一标识名，优先使用配置中的name字段
            # 大白话注释：给服务器起个名字，没起名就自动编号
            server_name = config.get("name", f"mcp_server_{i+1}")

            # Build the server config
            # 正经注释：构建单个服务器的配置字典
            # 大白话注释：开始翻译这一条服务器配置
            server_config = {}

            # Auto-detect transport type from URL if provided
            # 正经注释：根据URL前缀自动检测传输协议类型
            # 大白话注释：看看URL是啥开头的，自动猜你用什么协议连
            connection_url = config.get("connection_url")
            if connection_url:
                if connection_url.startswith(("wss://", "ws://")):  # 正经注释：WebSocket协议 / 大白话注释：ws开头的就是WebSocket连接
                    server_config["transport"] = "websocket"
                    server_config["url"] = connection_url
                elif connection_url.startswith(("https://", "http://")):  # 正经注释：HTTP协议 / 大白话注释：http开头的就是HTTP连接
                    server_config["transport"] = "streamable_http"
                    server_config["url"] = connection_url
                else:
                    # Fallback to specified connection_type or stdio
                    # 正经注释：无法自动检测时回退到用户指定的connection_type，默认stdio
                    # 大白话注释：URL看着不像ws也不像http，那就看用户自己指定了啥，默认走命令行
                    connection_type = config.get("connection_type", "stdio")
                    server_config["transport"] = connection_type
                    if connection_type in ["websocket", "streamable_http", "http"]:
                        server_config["url"] = connection_url
            else:
                # No URL provided, use stdio (default) or specified connection_type
                # 正经注释：未提供URL时默认使用stdio传输，或使用用户指定的传输方式
                # 大白话注释：连URL都没给，那就走命令行方式，或者看用户指定了啥
                connection_type = config.get("connection_type", "stdio")
                server_config["transport"] = connection_type

            if server_config.get("connection_type") in ["streamable_http", "http"]:  # 正经注释：HTTP类型连接需处理请求头 / 大白话注释：如果是HTTP连接，看看有没有自定义请求头
                connection_headers = config.get("connection_headers")
                if connection_headers and isinstance(connection_headers, dict):
                    server_config["headers"] = connection_headers

            # Handle stdio transport configuration
            # 正经注释：处理stdio（标准输入输出）传输类型的配置，包括命令、参数和环境变量
            # 大白话注释：如果是命令行方式连接，需要配置要跑什么命令、传啥参数、设啥环境变量
            if server_config.get("transport") == "stdio":
                if config.get("command"):
                    server_config["command"] = config["command"]  # 正经注释：设置要执行的命令 / 大白话注释：要跑的命令是啥

                    # Handle server_args
                    # 正经注释：处理命令行参数，支持字符串和列表两种格式
                    # 大白话注释：命令后面带的参数，如果是字符串就拆成列表
                    server_args = config.get("args", [])
                    if isinstance(server_args, str):
                        server_args = server_args.split()
                    server_config["args"] = server_args

                    # Handle environment variables
                    # 正经注释：处理服务器进程的环境变量配置
                    # 大白话注释：跑命令时要设哪些环境变量（比如API密钥之类的）
                    server_env = config.get("env", {})
                    if server_env:
                        server_config["env"] = server_env

            # Add authentication if provided
            # 正经注释：添加认证令牌（如提供）
            # 大白话注释：如果配了认证token就带上，有些服务器需要验证身份
            if config.get("connection_token"):
                server_config["token"] = config["connection_token"]

            server_configs[server_name] = server_config  # 正经注释：将翻译后的配置存入字典 / 大白话注释：翻译好了，存起来

        return server_configs  # 正经注释：返回所有服务器的langchain格式配置 / 大白话注释：把翻译好的配置全部交出去

    async def get_or_create_client(self) -> Optional[object]:
        """
        Get or create a MultiServerMCPClient with proper lifecycle management.

        Returns:
            MultiServerMCPClient: The client instance or None if creation fails

        【正经注释】
        获取或创建 MCP 客户端实例。采用懒加载模式：首次调用时创建客户端，
        后续调用复用已有实例。通过异步锁确保并发安全。

        【大白话注释】
        这个方法就是"要么拿来用，要么现做一个"。如果客户端已经创建过了就直接复用，
        没创建过就根据配置创建一个。用了锁保证同一时间只有一个人在创建，防止重复创建。
        """
        async with self._client_lock:  # 正经注释：获取异步锁，保证并发安全 / 大白话注释：先锁住，同一时间只能有一个人操作
            if self._client is not None:  # 正经注释：客户端已存在，直接返回复用 / 大白话注释：已经有了？直接拿来用
                return self._client

            if not HAS_MCP_ADAPTERS:  # 正经注释：检查MCP适配器依赖是否已安装 / 大白话注释：看看MCP的依赖包装没装
                logger.error("langchain-mcp-adapters not installed")
                return None

            if not self.mcp_configs:  # 正经注释：检查是否存在有效的服务器配置 / 大白话注释：看看有没有配MCP服务器
                logger.error("No MCP server configurations found")
                return None

            try:
                # Convert configs to langchain format
                # 正经注释：将配置转换为langchain格式并创建客户端
                # 大白话注释：翻译配置，然后用翻译好的配置创建客户端
                server_configs = self.convert_configs_to_langchain_format()
                logger.info(f"Creating MCP client for {len(server_configs)} server(s)")

                # Initialize the MultiServerMCPClient
                # 正经注释：使用翻译后的配置初始化多服务器MCP客户端
                # 大白话注释：正式创建客户端，连上所有配好的MCP服务器
                self._client = MultiServerMCPClient(server_configs)

                return self._client

            except Exception as e:  # 正经注释：捕获客户端创建过程中的异常 / 大白话注释：创建失败了就记录错误，返回None
                logger.error(f"Error creating MCP client: {e}")
                return None

    async def close_client(self):
        """
        Properly close the MCP client and clean up resources.

        【正经注释】
        安全关闭 MCP 客户端并释放资源。由于 MultiServerMCPClient 在当前版本
        不支持显式关闭方法，因此通过清除引用让垃圾回收机制处理资源释放。

        【大白话注释】
        关掉客户端，打扫战场。因为现在这个库还没有正经的"关闭"方法，
        所以就把引用清空，让 Python 自己回收垃圾。
        """
        async with self._client_lock:  # 正经注释：获取异步锁确保操作原子性 / 大白话注释：先锁住
            if self._client is not None:  # 正经注释：仅当客户端存在时执行清理 / 大白话注释：有客户端才需要清理
                try:
                    # Since MultiServerMCPClient doesn't support context manager
                    # or explicit close methods in langchain-mcp-adapters 0.1.0,
                    # we just clear the reference and let garbage collection handle it
                    # 正经注释：当前版本的MultiServerMCPClient不支持上下文管理器或显式关闭方法，仅清除引用
                    # 大白话注释：这个库还没提供正规的关闭方法，只能把引用清掉等Python自己回收
                    logger.debug("Releasing MCP client reference")
                except Exception as e:  # 正经注释：捕获清理过程中的异常 / 大白话注释：出错了就记录一下
                    logger.error(f"Error during MCP client cleanup: {e}")
                finally:
                    # Always clear the reference
                    # 正经注释：无论是否出错都清除客户端引用
                    # 大白话注释：不管怎样都要把引用清掉
                    self._client = None

    async def get_all_tools(self) -> List:
        """
        Get all available tools from MCP servers.

        Returns:
            List: All available MCP tools

        【正经注释】
        从所有已连接的 MCP 服务器获取可用工具列表。先确保客户端已创建，
        然后调用客户端的 get_tools 方法获取全部工具。

        【大白话注释】
        去所有MCP服务器上"扫货"，把能用的工具全部拉回来。
        先确保连接建好了，然后问服务器"你有哪些工具给我用"。
        """
        client = await self.get_or_create_client()  # 正经注释：获取或创建MCP客户端 / 大白话注释：先拿到客户端连接
        if not client:  # 正经注释：客户端创建失败则返回空列表 / 大白话注释：没连上就啥工具也没有
            return []

        try:
            # Get tools from all servers
            # 正经注释：从所有已连接的MCP服务器获取工具列表
            # 大白话注释：问所有服务器要工具清单
            all_tools = await client.get_tools()

            if all_tools:  # 正经注释：成功获取到工具 / 大白话注释：拿到工具了
                logger.info(f"Loaded {len(all_tools)} total tools from MCP servers")
                return all_tools
            else:  # 正经注释：服务器未提供任何工具 / 大白话注释：服务器说没工具可用
                logger.warning("No tools available from MCP servers")
                return []

        except Exception as e:  # 正经注释：捕获获取工具过程中的异常 / 大白话注释：出错了就记录日志，返回空列表
            logger.error(f"Error getting MCP tools: {e}")
            return []
