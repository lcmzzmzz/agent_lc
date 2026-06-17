"""
MCP Streaming Utilities Module

Handles websocket streaming and logging for MCP operations.

【正经注释】
本模块提供 MCP 操作的流式输出能力，包括：
- 通过 WebSocket 实时推送研究进度日志
- 异步和同步两种日志流式输出方式
- 封装了研究阶段、工具选择、工具执行、结果汇总等场景的快捷日志方法

【大白话注释】
这个文件是 MCP 的"广播站"。它负责把研究过程中的各种进度信息
实时推送到前端页面（通过 WebSocket）。比如"正在选择工具"、
"正在执行第2个工具"、"研究完成，获取到5条结果"这些消息，
都是通过这个模块发出去的。如果没连 WebSocket，就只写日志。
"""
import asyncio  # 正经注释：异步IO库，用于协程调度和事件循环操作 / 大白话注释：异步编程工具包
import logging  # 正经注释：日志模块 / 大白话注释：打日志用的
from typing import Any, Optional  # 正经注释：类型提示 / 大白话注释：类型标注

logger = logging.getLogger(__name__)  # 正经注释：创建模块级日志记录器 / 大白话注释：给这个文件搞个专属日志器


class MCPStreamer:
    """
    Handles streaming output for MCP operations.

    Responsible for:
    - Streaming logs to websocket
    - Synchronous/asynchronous logging
    - Error handling in streaming

    【正经注释】
    MCP 流式输出管理器，负责将研究过程中的日志信息实时推送到 WebSocket。
    提供异步和同步两种输出方式，以及针对不同研究阶段的快捷日志方法。

    【大白话注释】
    这个类就是 MCP 的"消息广播员"。前端页面上能看到的研究进度信息，
    都是通过它发出去的。它既能异步发消息（正常情况），也能同步发
    （特殊场景用），还帮你把各种常见消息（开始、完成、出错）都封装好了。
    """

    def __init__(self, websocket=None):
        """
        Initialize the MCP streamer.

        Args:
            websocket: WebSocket for streaming output

        【正经注释】
        初始化流式输出器，接收可选的 WebSocket 连接。
        若未提供 WebSocket，日志仅写入本地日志系统。

        【大白话注释】
        构造函数。把 WebSocket 连接存下来，没有的话也没关系，
        就是发不了实时消息，只能写日志。
        """
        self.websocket = websocket  # 正经注释：存储WebSocket连接引用 / 大白话注释：记住WebSocket连接

    async def stream_log(self, message: str, data: Any = None):
        """
        Stream a log message to the websocket if available.

        【正经注释】
        异步流式日志输出方法。先将消息记录到本地日志，再尝试通过 WebSocket
        推送到前端。WebSocket 推送失败不影响主流程。

        【大白话注释】
        发一条日志消息。先写到本地日志里，再试试能不能通过 WebSocket
        推到前端页面。推不出去也没事，不会影响正常流程。
        """
        logger.info(message)  # 正经注释：将消息记录到本地日志 / 大白话注释：先写日志

        if self.websocket:  # 正经注释：检查WebSocket连接是否可用 / 大白话注释：看看有没有连着WebSocket
            try:
                from ..actions.utils import stream_output  # 正经注释：导入流式输出工具函数 / 大白话注释：导入发消息的工具
                await stream_output(
                    type="logs",  # 正经注释：消息类型为日志 / 大白话注释：告诉前端这是日志消息
                    content="mcp_retriever",  # 正经注释：内容来源标识 / 大白话注释：告诉前端这是MCP检索器发的
                    output=message,  # 正经注释：实际输出内容 / 大白话注释：要发的消息
                    websocket=self.websocket,  # 正经注释：WebSocket连接 / 大白话注释：通过哪个连接发
                    metadata=data  # 正经注释：附加元数据 / 大白话注释：附带的额外信息
                )
            except Exception as e:  # 正经注释：捕获推送异常，避免影响主流程 / 大白话注释：发送失败了也没关系，记个日志就行
                logger.error(f"Error streaming log: {e}")
                
    def stream_log_sync(self, message: str, data: Any = None):
        """
        Synchronous version of stream_log for use in sync contexts.

        【正经注释】
        同步版本的流式日志输出，用于在同步代码上下文中调用。
        自动检测事件循环状态：若循环正在运行则创建异步任务，
        若未运行则直接运行直到完成。事件循环不可用时优雅降级。

        【大白话注释】
        这是异步发消息方法的"同步版"。有些地方不是异步代码，
        不能用 await，就用这个方法。它会自己判断当前有没有在跑的事件循环，
        有的话就创建异步任务去发，没有的话就直接跑。
        """
        logger.info(message)  # 正经注释：先记录到本地日志 / 大白话注释：写日志

        if self.websocket:  # 正经注释：检查WebSocket连接 / 大白话注释：看看有没有WebSocket
            try:
                try:
                    loop = asyncio.get_event_loop()  # 正经注释：获取当前事件循环 / 大白话注释：拿到当前的事件循环
                    if loop.is_running():  # 正经注释：事件循环正在运行，创建异步任务 / 大白话注释：循环正在跑，就创建个任务插队进去
                        asyncio.create_task(self.stream_log(message, data))
                    else:  # 正经注释：事件循环未运行，直接运行直到完成 / 大白话注释：循环没跑，就直接跑完
                        loop.run_until_complete(self.stream_log(message, data))
                except RuntimeError:  # 正经注释：没有可用的事件循环，优雅降级 / 大白话注释：连事件循环都没有，就算了
                    logger.debug("Could not stream log: no running event loop")
            except Exception as e:  # 正经注释：捕获所有异常避免崩溃 / 大白话注释：出啥事都别崩
                logger.error(f"Error in sync log streaming: {e}")

    async def stream_stage_start(self, stage: str, description: str):
        """
        Stream the start of a research stage.

        【正经注释】推送研究阶段开始的消息，包含阶段名称和描述。
        【大白话注释】广播"某个阶段开始了"的消息。
        """
        await self.stream_log(f"🔧 {stage}: {description}")

    async def stream_stage_complete(self, stage: str, result_count: int = None):
        """
        Stream the completion of a research stage.

        【正经注释】推送研究阶段完成的消息，可选包含结果数量统计。
        【大白话注释】广播"某个阶段完成了"的消息，有多少条结果也会带上。
        """
        if result_count is not None:  # 正经注释：有结果数量时包含统计 / 大白话注释：有结果数就显示出来
            await self.stream_log(f"✅ {stage} completed: {result_count} results")
        else:
            await self.stream_log(f"✅ {stage} completed")

    async def stream_tool_selection(self, selected_count: int, total_count: int):
        """
        Stream tool selection information.

        【正经注释】推送工具选择阶段的进度信息，包含选中数量和总数量。
        【大白话注释】广播"正在用AI从XX个工具里挑YY个最合适的"。
        """
        await self.stream_log(f"🧠 Using LLM to select {selected_count} most relevant tools from {total_count} available")

    async def stream_tool_execution(self, tool_name: str, step: int, total: int):
        """
        Stream tool execution progress.

        【正经注释】推送单个工具执行的进度信息，包含工具名称和执行序号。
        【大白话注释】广播"正在执行第X/Y个工具：XXX"。
        """
        await self.stream_log(f"🔍 Executing tool {step}/{total}: {tool_name}")

    async def stream_research_results(self, result_count: int, total_chars: int = None):
        """
        Stream research results summary.

        【正经注释】推送研究结果汇总信息，包含结果数量和可选的字符数统计。
        【大白话注释】广播"研究做完了，拿到了X条结果"。
        """
        if total_chars:  # 正经注释：有字符数统计时包含详细信息 / 大白话注释：有字符数就带上
            await self.stream_log(f"✅ MCP research completed: {result_count} results obtained ({total_chars:,} chars)")
        else:
            await self.stream_log(f"✅ MCP research completed: {result_count} results obtained")

    async def stream_error(self, error_msg: str):
        """
        Stream error messages.

        【正经注释】推送错误消息，前缀带错误标识图标。
        【大白话注释】广播"出错了：XXX"。
        """
        await self.stream_log(f"❌ {error_msg}")

    async def stream_warning(self, warning_msg: str):
        """
        Stream warning messages.

        【正经注释】推送警告消息，前缀带警告标识图标。
        【大白话注释】广播"有个警告：XXX"。
        """
        await self.stream_log(f"⚠️ {warning_msg}")

    async def stream_info(self, info_msg: str):
        """
        Stream informational messages.

        【正经注释】推送信息性消息，前缀带信息标识图标。
        【大白话注释】广播"提示信息：XXX"。
        """
        await self.stream_log(f"ℹ️ {info_msg}") 