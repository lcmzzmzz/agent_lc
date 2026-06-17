"""
基于MCP（模型上下文协议）的智能研究检索器。

【正经注释】本模块实现了使用MCP工具进行智能研究的检索器，采用两阶段策略：
1. 工具选择阶段：LLM从所有可用的MCP工具中选择2-3个最相关的工具
2. 研究执行阶段：LLM使用选定的工具执行智能研究
该检索器通过模块化设计将客户端管理、工具选择、研究执行和流式输出解耦。

【大白话注释】这个文件是MCP检索器的核心。MCP是一种让AI调用外部工具的协议。
这个检索器分两步走：先让AI看看有哪些工具可以用、挑最合适的几个，
然后用这些工具去做研究。比如AI可以挑"网页搜索"和"数据库查询"两个工具，
然后用它们去找你要的信息。
"""
import asyncio  # 正经注释：异步编程核心模块 / 大白话注释：异步编程用的，让程序能同时干多件事
import logging  # 正经注释：日志记录模块 / 大白话注释：记日志用的
from typing import List, Dict, Any, Optional  # 正经注释：类型提示相关导入 / 大白话注释：类型标注用的

try:
    from langchain_mcp_adapters.client import MultiServerMCPClient  # 正经注释：尝试导入MCP适配器客户端 / 大白话注释：看看MCP适配器包装了没有
    HAS_MCP_ADAPTERS = True  # 正经注释：标记MCP适配器可用 / 大白话注释：记一下"装了"
except ImportError:  # 正经注释：导入失败时标记为不可用 / 大白话注释：没装就标记"没装"
    HAS_MCP_ADAPTERS = False  # 正经注释：标记MCP适配器不可用 / 大白话注释：记一下"没装"

from ...mcp.client import MCPClientManager  # 正经注释：导入MCP客户端管理器 / 大白话注释：导入管MCP连接的管家
from ...mcp.tool_selector import MCPToolSelector  # 正经注释：导入MCP工具选择器 / 大白话注释：导入挑工具的"选角导演"
from ...mcp.research import MCPResearchSkill  # 正经注释：导入MCP研究执行技能 / 大白话注释：导入真正做研究的"研究员"
from ...mcp.streaming import MCPStreamer  # 正经注释：导入MCP流式输出工具 / 大白话注释：导入给前端实时传消息的"传话筒"

logger = logging.getLogger(__name__)  # 正经注释：创建当前模块的日志记录器 / 大白话注释：给这个文件搞个专属日志记录器


class MCPRetriever:
    """
    基于MCP（模型上下文协议）的智能研究检索器。

    【正经注释】
    该检索器实现了两阶段智能研究策略：
    1. 工具选择：LLM从所有可用的MCP工具中选择2-3个最相关的工具
    2. 研究执行：LLM绑定选定工具后执行智能研究

    这种方法比调用所有工具更高效，能提供更有针对性的研究结果。
    检索器需要researcher实例来访问MCP配置、LLM设置和研究成本追踪。

    【大白话注释】
    这个类是个"AI研究助手"。它会先看看手头有哪些工具（比如搜索、查询数据库等），
    然后让AI挑几个最合适的，再用这些工具去做研究。比把所有工具都用一遍聪明多了。
    它需要你给它一个"上级"（researcher实例），从那里拿配置信息。
    """

    def __init__(
        self,
        query: str,
        headers: Optional[Dict[str, str]] = None,
        query_domains: Optional[List[str]] = None,
        websocket=None,
        researcher=None,
        **kwargs
    ):
        """
        初始化MCP检索器。

        【正经注释】
        从researcher实例中提取MCP配置和LLM设置，初始化客户端管理器、
        工具选择器、研究执行器和流式输出器等模块化组件。

        【大白话注释】
        准备工作——记下要搜什么，从"上级"那里拿配置信息，
        然后把各个组件都准备好（连接管理器、工具选择器、研究员、传话筒）。

        Args:
            query (str): 搜索查询语句
            headers (dict, optional): 包含MCP配置的请求头
            query_domains (list, optional): 要搜索的域名列表（MCP中未使用）
            websocket: 用于流式日志的WebSocket连接
            researcher: 包含mcp_configs和cfg的researcher实例
            **kwargs: 额外参数（用于兼容性）
        """
        self.query = query  # 正经注释：保存搜索查询语句 / 大白话注释：记住要搜啥
        self.headers = headers or {}  # 正经注释：保存请求头字典 / 大白话注释：记住请求头
        self.query_domains = query_domains or []  # 正经注释：保存域名过滤列表 / 大白话注释：记住要限定搜哪些网站
        self.websocket = websocket  # 正经注释：保存WebSocket连接 / 大白话注释：记住跟前端通信的管道
        self.researcher = researcher  # 正经注释：保存researcher实例引用 / 大白话注释：记住"上级"

        # Extract mcp_configs and config from the researcher instance
        self.mcp_configs = self._get_mcp_configs()  # 正经注释：从researcher获取MCP服务器配置 / 大白话注释：从"上级"拿MCP配置
        self.cfg = self._get_config()  # 正经注释：从researcher获取LLM配置 / 大白话注释：从"上级"拿AI配置

        # Initialize modular components
        self.client_manager = MCPClientManager(self.mcp_configs)  # 正经注释：初始化MCP客户端管理器 / 大白话注释：搞一个连接管家
        self.tool_selector = MCPToolSelector(self.cfg, self.researcher)  # 正经注释：初始化工具选择器 / 大白话注释：搞一个"选角导演"
        self.mcp_researcher = MCPResearchSkill(self.cfg, self.researcher)  # 正经注释：初始化研究执行器 / 大白话注释：搞一个"研究员"
        self.streamer = MCPStreamer(self.websocket)  # 正经注释：初始化流式输出器 / 大白话注释：搞一个"传话筒"

        # Initialize caching
        self._all_tools_cache = None  # 正经注释：初始化工具列表缓存 / 大白话注释：缓存一下找到的工具，免得每次都重新找

        # Log initialization
        if self.mcp_configs:  # 正经注释：如果MCP配置存在则输出初始化日志 / 大白话注释：有配置就告诉你准备开始了
            self.streamer.stream_log_sync(f"🔧 Initializing MCP retriever for query: {self.query}")
            self.streamer.stream_log_sync(f"🔧 Found {len(self.mcp_configs)} MCP server configurations")
        else:  # 正经注释：MCP配置缺失时记录严重错误 / 大白话注释：没配置就告诉你"大事不好"
            logger.error("No MCP server configurations found. The retriever will fail during search.")
            self.streamer.stream_log_sync("❌ CRITICAL: No MCP server configurations found. Please check documentation.")

    def _get_mcp_configs(self) -> List[Dict[str, Any]]:
        """
        从researcher实例获取MCP服务器配置。

        【正经注释】
        安全地从researcher实例中提取mcp_configs属性，
        若researcher不存在或属性为空则返回空列表。

        【大白话注释】
        去"上级"那里拿MCP服务器的配置清单。如果"上级"不在或者没给清单，
        就返回空的，后面会报错提示。

        Returns:
            List[Dict[str, Any]]: MCP服务器配置列表
        """
        if self.researcher and hasattr(self.researcher, 'mcp_configs'):  # 正经注释：检查researcher实例和属性是否存在 / 大白话注释：看看"上级"在不在、有没有给配置
            return self.researcher.mcp_configs or []  # 正经注释：返回配置列表或空列表 / 大白话注释：有配置就拿出来，没有就返回空的
        return []  # 正经注释：无配置时返回空列表 / 大白话注释：啥都没有就返回空

    def _get_config(self):
        """
        从researcher实例获取LLM配置对象。

        【正经注释】
        安全地从researcher实例中提取cfg属性（LLM配置对象），
        若不存在则抛出ValueError异常。

        【大白话注释】
        去"上级"那里拿AI的配置。如果"上级"不在或者没给配置，
        就报错说"没有AI配置没法干活"。

        Returns:
            Config: 包含LLM设置的配置对象

        Raises:
            ValueError: researcher实例缺少cfg属性时抛出
        """
        if self.researcher and hasattr(self.researcher, 'cfg'):  # 正经注释：检查researcher实例和cfg属性是否存在 / 大白话注释：看看"上级"在不在、有没有给AI配置
            return self.researcher.cfg  # 正经注释：返回配置对象 / 大白话注释：把配置拿出来

        # If no config available, this is a critical error
        logger.error("No config found in researcher instance. MCPRetriever requires a researcher instance with cfg attribute.")  # 正经注释：记录严重错误日志 / 大白话注释：记一下"没配置不行"
        raise ValueError("MCPRetriever requires a researcher instance with cfg attribute containing LLM configuration")  # 正经注释：抛出配置缺失异常 / 大白话注释：报错——"上级"没给AI配置，干不了活

    async def search_async(self, max_results: int = 10) -> List[Dict[str, str]]:
        """
        使用MCP工具执行异步两阶段智能搜索。

        【正经注释】
        实现完整的三阶段异步搜索流程：
        阶段1：获取所有可用的MCP工具
        阶段2：由LLM选择最相关的2-3个工具
        阶段3：使用选定工具执行研究
        搜索完成后自动清理MCP客户端连接。

        【大白话注释】
        这是异步版本的搜索。分三步走：
        先看看有哪些工具可以用，
        再让AI挑几个最合适的，
        然后用这些工具去做研究。
        干完活还会自动打扫"战场"（关闭连接）。

        Args:
            max_results: 最大返回结果数

        Returns:
            List[Dict[str, str]]: 搜索结果列表
        """
        # Check if we have any server configurations
        if not self.mcp_configs:  # 正经注释：验证MCP配置是否存在 / 大白话注释：没配置就没法干
            error_msg = "No MCP server configurations available. Please provide mcp_configs parameter to GPTResearcher."
            logger.error(error_msg)
            await self.streamer.stream_error("MCP retriever cannot proceed without server configurations.")
            return []  # Return empty instead of raising to allow research to continue  # 正经注释：返回空列表而非抛出异常，确保研究流程不中断 / 大白话注释：返回空的，不崩溃，让其他搜索引擎继续干活

        # Log to help debug the integration flow
        logger.info(f"MCPRetriever.search_async called for query: {self.query}")  # 正经注释：记录搜索调用日志 / 大白话注释：记一下开始搜了

        try:
            # Stage 1: Get all available tools
            await self.streamer.stream_stage_start("Stage 1", "Getting all available MCP tools")  # 正经注释：通知前端阶段1开始 / 大白话注释：告诉前端"第一步开始了"
            all_tools = await self._get_all_tools()  # 正经注释：获取所有可用的MCP工具 / 大白话注释：看看有哪些工具可以用

            if not all_tools:  # 正经注释：无可用工具时跳过MCP研究 / 大白话注释：一个工具都没有就没法干
                await self.streamer.stream_warning("No MCP tools available, skipping MCP research")
                return []

            # Stage 2: Select most relevant tools
            await self.streamer.stream_stage_start("Stage 2", "Selecting most relevant tools")  # 正经注释：通知前端阶段2开始 / 大白话注释：告诉前端"开始挑工具了"
            selected_tools = await self.tool_selector.select_relevant_tools(self.query, all_tools, max_tools=3)  # 正经注释：LLM选择最相关的工具 / 大白话注释：让AI从工具箱里挑3个最合适的

            if not selected_tools:  # 正经注释：无匹配工具时跳过 / 大白话注释：AI觉得一个都不合适
                await self.streamer.stream_warning("No relevant tools selected, skipping MCP research")
                return []

            # Stage 3: Conduct research with selected tools
            await self.streamer.stream_stage_start("Stage 3", "Conducting research with selected tools")  # 正经注释：通知前端阶段3开始 / 大白话注释：告诉前端"开始干活了"
            results = await self.mcp_researcher.conduct_research_with_tools(self.query, selected_tools)  # 正经注释：使用选定工具执行研究 / 大白话注释：用挑好的工具去做研究

            # Limit the number of results
            if len(results) > max_results:  # 正经注释：结果数量超出限制时截断 / 大白话注释：结果太多了就只留要的条数
                logger.info(f"Limiting {len(results)} MCP results to {max_results}")
                results = results[:max_results]

            # Log result summary with actual content samples
            logger.info(f"MCPRetriever returning {len(results)} results")  # 正经注释：记录返回结果数量 / 大白话注释：记一下返回了几条结果

            # Calculate total content length for summary
            total_content_length = sum(len(result.get("body", "")) for result in results)  # 正经注释：计算总内容长度 / 大白话注释：算算结果一共有多少字
            await self.streamer.stream_research_results(len(results), total_content_length)  # 正经注释：向前端推送结果摘要 / 大白话注释：告诉前端搜到了多少东西

            # Log detailed content samples for debugging
            if results:  # 正经注释：有结果时记录详细内容样本 / 大白话注释：有结果就看看长什么样
                # Show samples of the first few results
                for i, result in enumerate(results[:3]):  #  Show first 3 results  # 正经注释：展示前3条结果的样本 / 大白话注释：看看前三条结果
                    title = result.get("title", "No title")
                    url = result.get("href", "No URL")
                    content = result.get("body", "")
                    content_length = len(content)
                    content_sample = content[:400] + "..." if len(content) > 400 else content

                    logger.debug(f"Result {i+1}/{len(results)}: '{title}'")
                    logger.debug(f"URL: {url}")
                    logger.debug(f"Content ({content_length:,} chars): {content_sample}")

                if len(results) > 3:  # 正经注释：超过3条时记录剩余概要 / 大白话注释：还有更多的话就简单说一下
                    remaining_results = len(results) - 3
                    remaining_content = sum(len(result.get("body", "")) for result in results[3:])
                    logger.debug(f"... and {remaining_results} more results ({remaining_content:,} chars)")

            return results  # 正经注释：返回搜索结果 / 大白话注释：把结果交出去

        except Exception as e:  # 正经注释：捕获异常并优雅降级 / 大白话注释：出错了就记一下，不崩溃
            logger.error(f"Error in MCP search: {e}")
            await self.streamer.stream_error(f"Error in MCP search: {str(e)}")
            return []
        finally:
            # Ensure client cleanup after search completes
            try:
                await self.client_manager.close_client()  # 正经注释：确保搜索完成后关闭MCP客户端连接 / 大白话注释：干完活把连接关了，别占着资源
            except Exception as e:  # 正经注释：清理异常时仅记录日志 / 大白话注释：关连接出错了就记一下，不影响主流程
                logger.error(f"Error during client cleanup: {e}")

    def search(self, max_results: int = 10) -> List[Dict[str, str]]:
        """
        使用MCP工具执行同步两阶段智能搜索。

        【正经注释】
        这是GPT Researcher所需的同步接口。内部包装了异步的search_async方法，
        处理了async/sync边界问题——若在异步上下文中调用则在新线程中创建新事件循环，
        否则直接使用asyncio.run执行。

        【大白话注释】
        这是同步版本的搜索，给外面统一用的接口。
        因为MCP搜索本身是异步的，但外面的调用方式是同步的，
        所以这个函数负责把"异步"翻译成"同步"——就像你点外卖（同步调用），
        但送外卖的是骑手（异步执行），这个函数就是中间的调度员。

        Args:
            max_results: 最大返回结果数

        Returns:
            List[Dict[str, str]]: 搜索结果列表
        """
        # Check if we have any server configurations
        if not self.mcp_configs:  # 正经注释：验证MCP配置是否存在 / 大白话注释：没配置就没法干
            error_msg = "No MCP server configurations available. Please provide mcp_configs parameter to GPTResearcher."
            logger.error(error_msg)
            self.streamer.stream_log_sync("❌ MCP retriever cannot proceed without server configurations.")
            return []  # Return empty instead of raising to allow research to continue  # 正经注释：返回空列表确保研究流程不中断 / 大白话注释：返回空的，不崩溃

        # Log to help debug the integration flow
        logger.info(f"MCPRetriever.search called for query: {self.query}")  # 正经注释：记录同步搜索调用日志 / 大白话注释：记一下开始搜了

        try:
            # Handle the async/sync boundary properly
            try:
                # Try to get the current event loop
                loop = asyncio.get_running_loop()  # 正经注释：尝试获取当前运行的事件循环 / 大白话注释：看看现在是不是已经在异步环境里了
                # If we're in an async context, we need to schedule the coroutine
                # This is a bit tricky - we'll create a task and let it run
                import concurrent.futures  # 正经注释：线程池执行器 / 大白话注释：开线程用的
                import threading  # 正经注释：线程模块 / 大白话注释：管线程用的

                # Create a new event loop in a separate thread
                def run_in_thread():  # 正经注释：在新线程中创建独立事件循环执行异步搜索 / 大白话注释：在另一个线程里单独开个异步环境来干活
                    new_loop = asyncio.new_event_loop()  # 正经注释：创建新的事件循环 / 大白话注释：开一个新的异步环境
                    asyncio.set_event_loop(new_loop)  # 正经注释：设置为当前线程的事件循环 / 大白话注释：让新线程认这个环境
                    try:
                        result = new_loop.run_until_complete(self.search_async(max_results))  # 正经注释：在新循环中运行异步搜索 / 大白话注释：在这个新环境里跑异步搜索
                        return result
                    finally:
                        # Enhanced cleanup procedure for MCP connections
                        try:
                            # Cancel all pending tasks with a timeout
                            pending = asyncio.all_tasks(new_loop)  # 正经注释：获取循环中所有待处理任务 / 大白话注释：看看还有什么活没干完
                            for task in pending:  # 正经注释：取消所有待处理任务 / 大白话注释：把没干完的活都取消掉
                                task.cancel()

                            # Wait for cancelled tasks to complete with timeout
                            if pending:  # 正经注释：有待处理任务时等待其完成 / 大白话注释：有活没干完就等一等
                                try:
                                    new_loop.run_until_complete(
                                        asyncio.wait_for(
                                            asyncio.gather(*pending, return_exceptions=True),
                                            timeout=5.0  # 5 second timeout for cleanup  # 正经注释：5秒清理超时 / 大白话注释：最多等5秒
                                        )
                                    )
                                except asyncio.TimeoutError:  # 正经注释：清理超时时继续执行 / 大白话注释：等太久了就算了
                                    logger.debug("Timeout during task cleanup, continuing...")
                                except Exception:  # 正经注释：忽略其他清理错误 / 大白话注释：其他错误也忽略
                                    pass  # Ignore other cleanup errors
                        except Exception:  # 正经注释：忽略清理异常 / 大白话注释：清理出错也忽略
                            pass  # Ignore cleanup errors
                        finally:
                            try:
                                # Give the loop a moment to finish any final cleanup
                                import time  # 正经注释：时间模块 / 大白话注释：等待用的
                                time.sleep(0.1)  # 正经注释：等待100毫秒让循环完成最终清理 / 大白话注释：稍微等一下

                                # Force garbage collection to clean up any remaining references
                                import gc  # 正经注释：垃圾回收模块 / 大白话注释：清理内存用的
                                gc.collect()  # 正经注释：强制执行垃圾回收 / 大白话注释：把不要的内存清一清

                                # Additional time for HTTP clients to finish their cleanup
                                time.sleep(0.2)  # 正经注释：额外等待200毫秒让HTTP客户端完成清理 / 大白话注释：再等一会儿让网络连接关干净

                                # Close the loop
                                if not new_loop.is_closed():  # 正经注释：关闭事件循环 / 大白话注释：把异步环境关了
                                    new_loop.close()
                            except Exception:  # 正经注释：忽略关闭异常 / 大白话注释：关闭出错也忽略
                                pass  # Ignore close errors

                # Run in a thread pool to avoid blocking the main event loop
                with concurrent.futures.ThreadPoolExecutor() as executor:  # 正经注释：使用线程池执行异步搜索 / 大白话注释：开个线程去跑
                    future = executor.submit(run_in_thread)
                    results = future.result(timeout=300)  # 5 minute timeout  # 正经注释：设置5分钟超时等待结果 / 大白话注释：最多等5分钟拿结果

            except RuntimeError:  # 正经注释：没有运行中的事件循环时直接使用asyncio.run / 大白话注释：不在异步环境里就直接跑
                # No event loop is running, we can run directly
                results = asyncio.run(self.search_async(max_results))

            return results  # 正经注释：返回搜索结果 / 大白话注释：把结果交出去

        except Exception as e:  # 正经注释：捕获所有异常并优雅降级 / 大白话注释：出错了就记一下，不崩溃
            logger.error(f"Error in MCP search: {e}")
            self.streamer.stream_log_sync(f"❌ Error in MCP search: {str(e)}")
            # Return empty results instead of raising to allow research to continue
            return []  # 正经注释：返回空结果确保研究流程不中断 / 大白话注释：返回空的，让其他搜索引擎继续干活

    async def _get_all_tools(self) -> List:
        """
        获取所有可用的MCP工具。

        【正经注释】
        从所有配置的MCP服务器获取全部可用工具列表，
        使用缓存机制避免重复查询。首次查询后缓存结果，
        后续调用直接返回缓存。

        【大白话注释】
        去所有MCP服务器那里"点兵"——看看一共有多少工具可以用。
        第一次会真的去问，问完就记住，下次直接用记住的结果，
        不用再跑一趟。

        Returns:
            List: 所有可用的MCP工具列表
        """
        if self._all_tools_cache is not None:  # 正经注释：检查缓存是否存在 / 大白话注释：之前找过了就直接用
            return self._all_tools_cache

        try:
            all_tools = await self.client_manager.get_all_tools()  # 正经注释：从客户端管理器获取所有工具 / 大白话注释：去各个服务器看看有什么工具

            if all_tools:  # 正经注释：有工具时缓存并返回 / 大白话注释：找到工具了就记住
                await self.streamer.stream_log(f"📋 Loaded {len(all_tools)} total tools from MCP servers")
                self._all_tools_cache = all_tools  # 正经注释：缓存工具列表 / 大白话注释：把工具列表记住
                return all_tools
            else:  # 正经注释：无工具时输出警告 / 大白话注释：一个工具都没找到
                await self.streamer.stream_warning("No tools available from MCP servers")
                return []

        except Exception as e:  # 正经注释：捕获异常并记录错误 / 大白话注释：出错了就记一下
            logger.error(f"Error getting MCP tools: {e}")
            await self.streamer.stream_error(f"Error getting MCP tools: {str(e)}")
            return []  # 正经注释：返回空列表 / 大白话注释：返回空的，不崩溃
