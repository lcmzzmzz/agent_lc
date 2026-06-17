"""
【正经注释】
支持工具调用的 LLM 工具模块。基于 LangChain 的统一接口提供提供商无关的工具调用功能，
允许任何支持函数调用的 LLM 提供商无缝使用工具。支持工具绑定、工具调用执行、
成本追踪、搜索工具和自定义工具的创建。

【大白话注释】
这个文件让大模型能"使用工具"。比如大模型需要搜索信息，它就能调用搜索工具。
不管是 OpenAI 还是 Anthropic，只要支持函数调用，都能用。
还提供了创建搜索工具和自定义工具的功能。
"""

import asyncio  # 正经注释：异步 I/O 库 / 大白话注释：异步编程用的
import logging  # 正经注释：标准日志库 / 大白话注释：打日志用的
from typing import Any, Dict, List, Tuple, Callable, Optional  # 正经注释：类型标注工具 / 大白话注释：用来标注变量类型的
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage  # 正经注释：LangChain 消息类型，对应不同的对话角色 / 大白话注释：三种消息类型——人说的、系统指令、AI说的
from langchain_core.tools import tool  # 正经注释：LangChain 的工具装饰器 / 大白话注释：把普通函数变成"工具"的装饰器

from .costs import calculate_llm_cost  # 正经注释：导入 LLM 成本计算函数 / 大白话注释：导入算钱的功能
from .llm import create_chat_completion  # 正经注释：导入基础聊天补全函数 / 大白话注释：导入普通的聊天功能，工具调用失败时用来兜底

logger = logging.getLogger(__name__)  # 正经注释：创建当前模块的日志记录器 / 大白话注释：给自己搞个专属日志器


def _track_response_cost(
    *,
    llm_provider: str | None,
    model: str | None,
    input_payload: Any,
    response_message: Any,
    request_options: Dict[str, Any],
    cost_callback: Callable | None,
) -> None:
    """
    【正经注释】
    追踪工具调用的响应成本。提取响应内容和元数据，调用成本计算函数，
    并通过回调函数上报成本。

    【大白话注释】
    算一算这次工具调用花了多少钱。如果有成本回调函数就算一下然后报上去，
    没有就算了。

    Args:
        llm_provider: LLM 提供商名称。
        model: 模型名称。
        input_payload: 输入的消息负载。
        response_message: 响应消息对象。
        request_options: 请求选项字典。
        cost_callback: 成本回调函数。
    """
    if not cost_callback:  # 正经注释：无回调函数则不追踪 / 大白话注释：没人关心花了多少钱就算了
        return

    response_content = getattr(response_message, "content", "") or ""  # 正经注释：安全地提取响应文本内容 / 大白话注释：拿到模型返回的文字
    llm_costs = calculate_llm_cost(  # 正经注释：计算 LLM 调用成本 / 大白话注释：算一下花了多少钱
        llm_provider=llm_provider,
        model=model,
        input_content=str(input_payload),
        output_content=str(response_content),
        response_metadata=getattr(response_message, "response_metadata", None),  # 正经注释：提取响应元数据 / 大白话注释：拿到响应的附加信息
        usage_metadata=getattr(response_message, "usage_metadata", None),  # 正经注释：提取使用量元数据 / 大白话注释：拿到用了多少 Token 的信息
        request_options=request_options,
    )
    cost_callback(llm_costs)  # 正经注释：通过回调上报成本 / 大白话注释：告诉调用方花了多少钱


async def create_chat_completion_with_tools(
    messages: List[Dict[str, str]],
    tools: List[Callable],
    model: str | None = None,
    temperature: float | None = 0.4,
    max_tokens: int | None = 4000,
    llm_provider: str | None = None,
    llm_kwargs: Dict[str, Any] | None = None,
    cost_callback: Callable = None,
    websocket: Any | None = None,
    **kwargs
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    【正经注释】
    创建支持工具调用的聊天补全。使用 LangChain 的 bind_tools() 方法实现提供商无关的函数调用，
    AI 自主决定何时及如何使用工具。处理完整的工具调用流程，包括工具执行、结果反馈和最终响应生成。

    【大白话注释】
    这是"带工具的聊天"的核心函数。大模型不仅能聊天，还能自己决定要不要用工具。
    比如它觉得需要搜索一下，就调搜索工具；用完工具后，把结果带回来说。
    如果工具调用出了问题，就回退到普通聊天模式。

    Args:
        messages: 对话消息列表。
        tools: LangChain 工具函数列表（用 @tool 装饰的）。
        model: 使用的模型。
        temperature: 生成温度。
        max_tokens: 最大 Token 数。
        llm_provider: LLM 提供商名称。
        llm_kwargs: 额外的 LLM 参数。
        cost_callback: 成本追踪回调函数。
        websocket: 可选的 WebSocket 连接。
        **kwargs: 额外参数。

    Returns:
        (响应内容, 工具调用元数据) 的元组。

    Raises:
        Exception: 工具调用失败时回退到简单补全。
    """
    try:
        from ..llm_provider.generic.base import GenericLLMProvider  # 正经注释：延迟导入 LLM 提供商基类 / 大白话注释：用到的时候才导入

        # Create LLM provider using the config
        provider_kwargs = {  # 正经注释：构建提供商参数 / 大白话注释：准备给模型传的参数
            'model': model,
            **(llm_kwargs or {})
        }

        llm_provider_instance = GenericLLMProvider.from_provider(
            llm_provider,
            **provider_kwargs
        )  # 正经注释：创建 LLM 提供商实例 / 大白话注释：造一个能跟大模型聊天的对象

        # Convert messages to LangChain format
        lc_messages = []  # 正经注释：初始化 LangChain 消息列表 / 大白话注释：准备一个空列表来装格式化后的消息
        for msg in messages:  # 正经注释：遍历原始消息并转换格式 / 大白话注释：把每条消息变成 LangChain 认识的格式
            if msg["role"] == "system":  # 正经注释：系统消息 / 大白话注释：系统指令
                lc_messages.append(SystemMessage(content=msg["content"]))
            elif msg["role"] == "user":  # 正经注释：用户消息 / 大白话注释：人说的
                lc_messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":  # 正经注释：助手消息 / 大白话注释：AI 说的
                lc_messages.append(AIMessage(content=msg["content"]))

        # Bind tools to the LLM - this works across all LangChain providers that support function calling
        llm_with_tools = llm_provider_instance.llm.bind_tools(tools)  # 正经注释：将工具绑定到 LLM，所有支持函数调用的 LangChain 提供商均可使用 / 大白话注释：把工具"给"大模型，让它知道有哪些工具可以用

        # Invoke the LLM with tools - this will handle the full conversation flow
        logger.info(f"Invoking LLM with {len(tools)} available tools")  # 正经注释：记录工具调用日志 / 大白话注释：打个日志说现在要用几个工具

        # For tool calling, we need to handle the full conversation including tool responses
        from langchain_core.messages import ToolMessage  # 正经注释：导入工具消息类型 / 大白话注释：导入"工具执行结果"这种消息类型

        # First call to LLM
        response = await llm_with_tools.ainvoke(lc_messages)  # 正经注释：首次调用 LLM / 大白话注释：把消息发给大模型，等它回答
        _track_response_cost(  # 正经注释：追踪首次调用的成本 / 大白话注释：算一下第一次花了多少钱
            llm_provider=llm_provider,
            model=model,
            input_payload=lc_messages,
            response_message=response,
            request_options=provider_kwargs,
            cost_callback=cost_callback,
        )

        # Process tool calls if any were made
        tool_calls_metadata = []  # 正经注释：工具调用元数据列表 / 大白话注释：用来记录调了哪些工具、参数是什么、结果是什么
        if hasattr(response, 'tool_calls') and response.tool_calls:  # 正经注释：检查 LLM 是否请求了工具调用 / 大白话注释：大模型有没有说要调工具
            logger.info(f"LLM made {len(response.tool_calls)} tool calls")  # 正经注释：记录工具调用次数 / 大白话注释：打个日志说调了几次工具

            # Add the assistant's response with tool calls to the conversation
            lc_messages.append(response)  # 正经注释：将助手响应（含工具调用）添加到对话 / 大白话注释：把 AI 说的话也加到对话历史里

            # Execute each tool call and add results to conversation
            for tool_call in response.tool_calls:  # 正经注释：遍历每个工具调用请求 / 大白话注释：一个一个执行工具
                tool_name = tool_call.get('name', 'unknown')  # 正经注释：获取工具名称 / 大白话注释：看看要调哪个工具
                tool_args = tool_call.get('args', {})  # 正经注释：获取工具参数 / 大白话注释：看看要传什么参数
                tool_id = tool_call.get('id', '')  # 正经注释：获取工具调用 ID / 大白话注释：这次调用的编号

                logger.info(f"Tool called: {tool_name}")  # 正经注释：记录工具调用 / 大白话注释：打个日志说调了什么工具
                if tool_args:  # 正经注释：记录工具参数 / 大白话注释：如果有参数就记一下
                    args_str = ", ".join([f"{k}={v}" for k, v in tool_args.items()])
                    logger.debug(f"Tool arguments: {args_str}")

                # Find and execute the tool
                tool_result = "Tool execution failed"  # 正经注释：默认结果为失败 / 大白话注释：先假设会失败
                for tool in tools:  # 正经注释：在工具列表中查找匹配的工具 / 大白话注释：在可用工具里找到要调的那个
                    if tool.name == tool_name:
                        try:
                            if hasattr(tool, 'ainvoke'):  # 正经注释：优先使用异步调用 / 大白话注释：能异步就异步调
                                tool_result = await tool.ainvoke(tool_args)
                            elif hasattr(tool, 'invoke'):  # 正经注释：其次使用同步调用 / 大白话注释：不能异步就同步调
                                tool_result = tool.invoke(tool_args)
                            else:  # 正经注释：直接调用函数 / 大白话注释：直接当函数调
                                tool_result = await tool(**tool_args) if asyncio.iscoroutinefunction(tool) else tool(**tool_args)
                            break  # 正经注释：找到匹配工具后跳出循环 / 大白话注释：找到了就不用继续找了
                        except Exception as e:  # 正经注释：捕获工具执行异常 / 大白话注释：执行出错了
                            error_type = type(e).__name__
                            error_msg = str(e)
                            logger.error(
                                f"Error executing tool '{tool_name}': {error_type}: {error_msg}",
                                exc_info=True
                            )  # 正经注释：记录错误详情 / 大白话注释：把错误记下来
                            # Provide user-friendly error message
                            if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():  # 正经注释：超时错误 / 大白话注释：太慢了，超时了
                                tool_result = f"Tool '{tool_name}' timed out. The operation took too long to complete. Please try again or check your network connection."
                            elif "connection" in error_msg.lower() or "network" in error_msg.lower():  # 正经注释：网络错误 / 大白话注释：网络有问题
                                tool_result = f"Tool '{tool_name}' failed due to a network issue. Please check your internet connection and try again."
                            elif "permission" in error_msg.lower() or "access" in error_msg.lower():  # 正经注释：权限错误 / 大白话注释：没权限
                                tool_result = f"Tool '{tool_name}' failed due to insufficient permissions. Please check your API keys or access credentials."
                            else:  # 正经注释：其他错误 / 大白话注释：不知道什么问题
                                tool_result = f"Tool '{tool_name}' encountered an error: {error_msg}. Please check the logs for more details."

                # Add tool result to conversation
                tool_message = ToolMessage(content=str(tool_result), tool_call_id=tool_id)  # 正经注释：创建工具结果消息 / 大白话注释：把工具执行结果包装成消息
                lc_messages.append(tool_message)  # 正经注释：添加到对话历史 / 大白话注释：加到对话里

                # Add to metadata
                tool_calls_metadata.append({  # 正经注释：记录工具调用元数据 / 大白话注释：把这次调用的信息记下来
                    "tool": tool_name,
                    "args": tool_args,
                    "call_id": tool_id,
                    "result": str(tool_result)[:200] + "..." if len(str(tool_result)) > 200 else str(tool_result)  # 正经注释：截断过长的结果 / 大白话注释：结果太长就只留前200个字
                })

            # Get final response from LLM after tool execution
            logger.info("Getting final response from LLM after tool execution")  # 正经注释：记录获取最终响应 / 大白话注释：打个日志说开始拿最终回答了
            final_response = await llm_with_tools.ainvoke(lc_messages)  # 正经注释：将工具执行结果发回 LLM 获取最终响应 / 大白话注释：把工具的结果发给大模型，让它总结一下

            # Track costs if callback provided
            _track_response_cost(  # 正经注释：追踪最终响应的成本 / 大白话注释：算一下第二次花了多少钱
                llm_provider=llm_provider,
                model=model,
                input_payload=lc_messages,
                response_message=final_response,
                request_options=provider_kwargs,
                cost_callback=cost_callback,
            )

            return final_response.content, tool_calls_metadata  # 正经注释：返回最终响应和工具调用元数据 / 大白话注释：把最终回答和工具调用记录一起返回

        else:
            # No tool calls, return regular response
            return response.content, []  # 正经注释：无工具调用时直接返回普通响应 / 大白话注释：大模型没说要调工具，直接返回它的回答

    except Exception as e:  # 正经注释：捕获所有异常并回退到简单模式 / 大白话注释：工具调用完全失败了
        error_type = type(e).__name__
        error_msg = str(e)
        logger.error(
            f"Error in tool-enabled chat completion: {error_type}: {error_msg}",
            exc_info=True
        )  # 正经注释：记录错误详情 / 大白话注释：记下出了什么错
        logger.info("Falling back to simple chat completion without tools")  # 正经注释：记录回退信息 / 大白话注释：打个日志说要用普通模式了

        # Fallback to simple chat completion without tools
        response = await create_chat_completion(  # 正经注释：回退到不含工具的普通聊天补全 / 大白话注释：用不带工具的方式再试一次
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            llm_provider=llm_provider,
            llm_kwargs=llm_kwargs,
            cost_callback=cost_callback,
            websocket=websocket,
            **kwargs
        )
        return response, []  # 正经注释：返回普通响应和空的工具调用列表 / 大白话注释：返回普通回答，工具调用记录为空


def create_search_tool(search_function: Callable[[str], Dict]) -> Callable:
    """
    【正经注释】
    创建标准化的搜索工具。将搜索函数封装为 LangChain 工具，格式化搜索结果
    并提供上下文感知的错误处理。

    【大白话注释】
    把一个搜索函数包装成一个"工具"，这样大模型就能用它来搜索信息了。
    它会自动把搜索结果整理成好看的格式，搜索出错了也会给出友好的提示。

    Args:
        search_function: 接受查询字符串并返回搜索结果的函数。

    Returns:
        用 @tool 装饰的 LangChain 工具函数。
    """
    @tool
    def search_tool(query: str) -> str:  # 正经注释：定义搜索工具函数 / 大白话注释：这个就是搜索工具本身
        """Search for current events or online information when you need new knowledge that doesn't exist in the current context"""
        try:
            results = search_function(query)  # 正经注释：调用搜索函数获取结果 / 大白话注释：执行搜索
            if results and 'results' in results:  # 正经注释：检查返回结果格式 / 大白话注释：看看有没有搜索结果
                search_content = f"Search results for '{query}':\n\n"  # 正经注释：构建搜索结果字符串 / 大白话注释：开始拼搜索结果
                for result in results['results'][:5]:  # 正经注释：最多取前5条结果 / 大白话注释：只显示前5条
                    search_content += f"Title: {result.get('title', '')}\n"  # 正经注释：添加标题 / 大白话注释：加上标题
                    search_content += f"Content: {result.get('content', '')[:300]}...\n"  # 正经注释：添加内容摘要（截断） / 大白话注释：加上内容，太长就截掉
                    search_content += f"URL: {result.get('url', '')}\n\n"  # 正经注释：添加 URL / 大白话注释：加上链接
                return search_content  # 正经注释：返回格式化的搜索结果 / 大白话注释：返回整理好的结果
            else:
                return f"No search results found for: {query}"  # 正经注释：无结果时的提示 / 大白话注释：没搜到东西
        except Exception as e:  # 正经注释：捕获搜索异常 / 大白话注释：搜索出错了
            error_type = type(e).__name__
            error_msg = str(e)
            logger.error(
                f"Search tool error: {error_type}: {error_msg}",
                exc_info=True
            )  # 正经注释：记录搜索错误 / 大白话注释：记一下出了什么错
            # Provide context-aware error messages
            if "api" in error_msg.lower() or "key" in error_msg.lower():  # 正经注释：API 密钥相关错误 / 大白话注释：API 密钥有问题
                return f"Search failed: API key issue. Please verify your search API credentials are configured correctly."
            elif "timeout" in error_msg.lower() or "timed out" in error_msg.lower():  # 正经注释：超时错误 / 大白话注释：搜索太慢了
                return f"Search timed out. The search request took too long. Please try again with a different query."
            elif "rate limit" in error_msg.lower() or "quota" in error_msg.lower():  # 正经注释：速率限制错误 / 大白话注释：请求太频繁了
                return f"Search rate limit exceeded. Please wait a moment before trying again."
            else:  # 正经注释：其他错误 / 大白话注释：不知道什么问题
                return f"Search encountered an error: {error_msg}. Please check your search provider configuration."

    return search_tool  # 正经注释：返回搜索工具函数 / 大白话注释：把造好的搜索工具返回出去


def create_custom_tool(
    name: str,
    description: str,
    function: Callable,
    parameter_schema: Optional[Dict] = None
) -> Callable:
    """
    【正经注释】
    创建自定义工具。将任意函数封装为 LangChain 工具，支持设置工具名称、描述
    和参数模式，并提供错误处理和用户友好的错误消息。

    【大白话注释】
    你有一个自己写的函数，想让它变成大模型能调用的"工具"，就用这个。
    给它起个名字、写个描述、传你的函数进去，就搞定了。
    执行出错了也会给出好理解的错误提示。

    Args:
        name: 工具名称。
        description: 工具功能描述。
        function: 实际执行的函数。
        parameter_schema: 可选的函数参数模式。

    Returns:
        用 @tool 装饰的 LangChain 工具函数。
    """
    @tool
    def custom_tool(*args, **kwargs) -> str:  # 正经注释：定义自定义工具函数 / 大白话注释：这个就是包装后的工具
        try:
            result = function(*args, **kwargs)  # 正经注释：调用原始函数 / 大白话注释：执行你的函数
            return str(result) if result is not None else "Tool executed successfully"  # 正经注释：返回结果或成功提示 / 大白话注释：有结果就返回结果，没结果就说成功了
        except Exception as e:  # 正经注释：捕获执行异常 / 大白话注释：出错了
            error_type = type(e).__name__
            error_msg = str(e)
            logger.error(
                f"Custom tool '{name}' error: {error_type}: {error_msg}",
                exc_info=True
            )  # 正经注释：记录工具错误 / 大白话注释：记一下出了什么错
            # Provide informative error message without exposing internal details
            if "validation" in error_msg.lower() or "invalid" in error_msg.lower():  # 正经注释：参数验证错误 / 大白话注释：参数不对
                return f"Tool '{name}' received invalid input. Please check the parameters and try again."
            elif "not found" in error_msg.lower() or "missing" in error_msg.lower():  # 正经注释：资源未找到错误 / 大白话注释：要找的东西不存在
                return f"Tool '{name}' could not find required resources. Please verify the input data is correct."
            else:  # 正经注释：其他错误 / 大白话注释：不知道什么问题
                return f"Tool '{name}' encountered an error: {error_msg}. Please check the tool configuration."

    # Set tool metadata
    custom_tool.name = name  # 正经注释：设置工具名称 / 大白话注释：给工具取个名字
    custom_tool.description = description  # 正经注释：设置工具描述 / 大白话注释：写上这个工具是干什么的

    return custom_tool  # 正经注释：返回自定义工具 / 大白话注释：把造好的工具返回出去


# Utility function for common tool patterns
def get_available_providers_with_tools() -> List[str]:
    """
    【正经注释】
    获取支持工具调用的 LLM 提供商列表。返回已知在 LangChain 中支持函数调用的提供商名称。

    【大白话注释】
    列出哪些大模型提供商支持"工具调用"功能。目前支持的有 OpenAI、Anthropic、Google 等。
    这个列表会随着更多提供商加入而更新。

    Returns:
        支持函数调用的提供商名称列表。
    """
    # These are the providers known to support function calling in LangChain
    return [
        "openai",  # 正经注释：OpenAI / 大白话注释：OpenAI
        "anthropic",  # 正经注释：Anthropic / 大白话注释：Anthropic
        "google_genai",  # 正经注释：Google Generative AI / 大白话注释：Google 的 Gemini
        "azure_openai",  # 正经注释：Azure OpenAI / 大白话注释：微软云上的 OpenAI
        "fireworks",  # 正经注释：Fireworks AI / 大白话注释：Fireworks
        "groq",  # 正经注释：Groq / 大白话注释：Groq
        # Note: This list may expand as more providers add function calling support
    ]


def supports_tools(provider: str) -> bool:
    """
    【正经注释】
    检查指定的 LLM 提供商是否支持工具调用。

    【大白话注释】
    问问某个提供商支不支持工具调用。传个名字进去，
    在列表里就返回 True，不在就返回 False。

    Args:
        provider: LLM 提供商名称。

    Returns:
        支持工具调用返回 True，否则返回 False。
    """
    return provider in get_available_providers_with_tools()  # 正经注释：检查提供商是否在支持列表中 / 大白话注释：在名单里就支持，不在就不支持
