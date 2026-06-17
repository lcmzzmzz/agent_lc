"""
MCP Research Execution Skill

Handles research execution using selected MCP tools as a skill component.

【正经注释】
本模块实现了基于 MCP 工具的研究执行技能，负责：
- 利用大语言模型和绑定的 MCP 工具进行智能研究
- 将工具执行结果转换为标准的搜索结果格式
- 管理工具执行流程和异常处理

【大白话注释】
这个文件是 MCP 研究功能的"执行引擎"。它的工作流程是：
先把 MCP 工具绑定到大语言模型上，让 AI 自己决定调用哪些工具、传什么参数，
然后执行这些工具，把返回的结果整理成统一的格式（标题+链接+内容），
最后把 AI 自己的分析也加进去。
"""
import asyncio  # 正经注释：异步IO库，用于协程调度 / 大白话注释：异步编程工具包
import logging  # 正经注释：日志模块 / 大白话注释：打日志用的
from typing import List, Dict, Any  # 正经注释：类型提示 / 大白话注释：类型标注

logger = logging.getLogger(__name__)  # 正经注释：创建模块级日志记录器 / 大白话注释：给这个文件搞个专属日志器


class MCPResearchSkill:
    """
    Handles research execution using selected MCP tools.

    Responsible for:
    - Executing research with LLM and bound tools
    - Processing tool results into standard format
    - Managing tool execution and error handling

    【正经注释】
    MCP 研究技能类，封装了利用 LLM 与 MCP 工具协作执行研究任务的完整流程。
    支持工具调用结果的结构化处理和 LLM 自身分析的整合。

    【大白话注释】
    这个类就是"研究执行员"。它拿着用户的研究问题，让 AI 调用选好的 MCP 工具
    去查资料，然后把工具返回的各种格式的结果都整理成统一的样子，
    再把 AI 自己的分析总结也加进去，最终交出一份完整的研究结果。
    """

    def __init__(self, cfg, researcher=None):
        """
        Initialize the MCP research skill.

        Args:
            cfg: Configuration object with LLM settings
            researcher: Researcher instance for cost tracking

        【正经注释】
        初始化研究技能实例，存储配置对象和研究者引用。
        配置对象包含 LLM 模型参数，研究者实例用于费用追踪。

        【大白话注释】
        构造函数。把配置信息和研究器实例存下来，后面要用。
        配置里有用哪个AI模型的信息，研究器用来记录花了多少钱。
        """
        self.cfg = cfg  # 正经注释：存储配置对象 / 大白话注释：记住配置
        self.researcher = researcher  # 正经注释：存储研究者实例引用 / 大白话注释：记住是谁在做研究

    async def conduct_research_with_tools(self, query: str, selected_tools: List) -> List[Dict[str, str]]:
        """
        Use LLM with bound tools to conduct intelligent research.

        Args:
            query: Research query
            selected_tools: List of selected MCP tools

        Returns:
            List[Dict[str, str]]: Research results in standard format

        【正经注释】
        使用绑定了 MCP 工具的大语言模型执行智能研究。流程包括：
        1. 创建 LLM 提供者并绑定选定的 MCP 工具
        2. 构建研究提示词并发送给 LLM
        3. 解析 LLM 返回的工具调用请求
        4. 逐一执行工具调用并收集结果
        5. 将 LLM 自身的分析文本也纳入结果集

        【大白话注释】
        这是核心研究方法，整个流程是：
        1. 把选好的工具"绑"到AI身上，让AI能调用这些工具
        2. 给AI写一段提示词，告诉它要研究什么问题、有哪些工具可用
        3. AI会自己决定调哪些工具、传什么参数
        4. 挨个执行AI选的工具，把结果收回来
        5. AI自己的分析总结也算一份结果
        最后把所有结果打包返回。
        """
        if not selected_tools:  # 正经注释：无可用工具时直接返回空结果 / 大白话注释：没工具可用就没法研究
            logger.warning("No tools available for research")
            return []

        logger.info(f"Conducting research using {len(selected_tools)} selected tools")

        try:
            from ..llm_provider.generic.base import GenericLLMProvider  # 正经注释：导入通用LLM提供者，延迟导入避免循环依赖 / 大白话注释：导入AI模型提供者

            # Create LLM provider using the config
            # 正经注释：根据配置创建LLM提供者实例，使用策略模型和额外参数
            # 大白话注释：用配置里的模型信息创建一个AI连接
            provider_kwargs = {
                'model': self.cfg.strategic_llm_model,  # 正经注释：使用策略级LLM模型 / 大白话注释：用哪个AI模型
                **self.cfg.llm_kwargs  # 正经注释：附加的LLM参数 / 大白话注释：其他杂七杂八的参数
            }

            llm_provider = GenericLLMProvider.from_provider(
                self.cfg.strategic_llm_provider,
                **provider_kwargs
            )

            # Bind tools to LLM
            # 正经注释：将选定的MCP工具绑定到LLM实例，使模型能够调用这些工具
            # 大白话注释：把工具"绑"到AI身上，让AI能调用这些工具
            llm_with_tools = llm_provider.llm.bind_tools(selected_tools)

            # Import here to avoid circular imports
            # 正经注释：延迟导入提示词家族，避免循环导入问题
            # 大白话注释：在这里导入提示词模板，放太早会出循环引用的问题
            from ..prompts import PromptFamily

            # Create research prompt
            # 正经注释：生成针对当前查询和工具的研究提示词
            # 大白话注释：给AI写一段指令，告诉它要研究啥、有哪些工具可用
            research_prompt = PromptFamily.generate_mcp_research_prompt(query, selected_tools)

            # Create messages
            # 正经注释：构建消息列表，包含用户角色的研究提示
            # 大白话注释：把提示词包装成消息格式
            messages = [{"role": "user", "content": research_prompt}]

            # Invoke LLM with tools
            # 正经注释：异步调用绑定了工具的LLM，获取响应
            # 大白话注释：让AI开始干活，等它回复
            logger.info("LLM researching with bound tools...")
            response = await llm_with_tools.ainvoke(messages)

            # Process tool calls and results
            # 正经注释：初始化研究结果列表，用于收集工具执行结果
            # 大白话注释：准备一个篮子装研究结果
            research_results = []

            # Check if the LLM made tool calls
            # 正经注释：检查LLM响应中是否包含工具调用请求
            # 大白话注释：看看AI有没有决定调用工具
            if hasattr(response, 'tool_calls') and response.tool_calls:
                logger.info(f"LLM made {len(response.tool_calls)} tool calls")

                # Process each tool call
                # 正经注释：遍历处理每个工具调用请求
                # 大白话注释：挨个处理AI要调用的工具
                for i, tool_call in enumerate(response.tool_calls, 1):
                    tool_name = tool_call.get("name", "unknown")  # 正经注释：获取工具名称 / 大白话注释：这个工具叫啥名
                    tool_args = tool_call.get("args", {})  # 正经注释：获取工具调用参数 / 大白话注释：AI传了什么参数

                    logger.info(f"Executing tool {i}/{len(response.tool_calls)}: {tool_name}")

                    # Log the tool arguments for transparency
                    # 正经注释：记录工具调用参数，便于调试和审计
                    # 大白话注释：把AI传的参数记下来，方便排查问题
                    if tool_args:
                        args_str = ", ".join([f"{k}={v}" for k, v in tool_args.items()])
                        logger.debug(f"Tool arguments: {args_str}")

                    try:
                        # Find the tool by name
                        # 正经注释：在已选工具列表中按名称查找对应的工具实例
                        # 大白话注释：根据名字找到那个工具
                        tool = next((t for t in selected_tools if t.name == tool_name), None)
                        if not tool:
                            logger.warning(f"Tool {tool_name} not found in selected tools")
                            continue

                        # Execute the tool
                        # 正经注释：根据工具支持的调用方式执行：优先异步调用，其次同步调用，最后直接调用
                        # 大白话注释：用不同的方式调用工具，能异步就异步，不行就同步
                        if hasattr(tool, 'ainvoke'):
                            result = await tool.ainvoke(tool_args)  # 正经注释：异步调用 / 大白话注释：异步方式执行
                        elif hasattr(tool, 'invoke'):
                            result = tool.invoke(tool_args)  # 正经注释：同步调用 / 大白话注释：同步方式执行
                        else:
                            result = await tool(tool_args) if asyncio.iscoroutinefunction(tool) else tool(tool_args)  # 正经注释：直接调用，自动判断同步/异步 / 大白话注释：直接当函数调

                        # Log the actual tool response for debugging
                        # 正经注释：记录工具响应的预览内容用于调试
                        # 大白话注释：把工具返回的东西记下来看看
                        if result:
                            result_preview = str(result)[:500] + "..." if len(str(result)) > 500 else str(result)
                            logger.debug(f"Tool {tool_name} response preview: {result_preview}")

                            # Process the result
                            # 正经注释：将工具原始结果转换为标准搜索结果格式
                            # 大白话注释：把工具返回的东西整理成统一格式
                            formatted_results = self._process_tool_result(tool_name, result)
                            research_results.extend(formatted_results)  # 正经注释：将格式化结果追加到总列表 / 大白话注释：把整理好的结果扔进篮子
                            logger.info(f"Tool {tool_name} returned {len(formatted_results)} formatted results")

                            # Log details of each formatted result
                            # 正经注释：逐条记录格式化结果的标题和内容预览
                            # 大白话注释：详细记录每条结果，方便调试
                            for j, formatted_result in enumerate(formatted_results):
                                title = formatted_result.get("title", "No title")
                                content_preview = formatted_result.get("body", "")[:200] + "..." if len(formatted_result.get("body", "")) > 200 else formatted_result.get("body", "")
                                logger.debug(f"Result {j+1}: '{title}' - Content: {content_preview}")
                        else:
                            logger.warning(f"Tool {tool_name} returned empty result")  # 正经注释：工具返回空结果 / 大白话注释：工具啥也没返回

                    except Exception as e:  # 正经注释：捕获单个工具执行异常，继续处理后续工具 / 大白话注释：这个工具执行出错了，跳过它继续下一个
                        logger.error(f"Error executing tool {tool_name}: {e}")
                        continue

            # Also include the LLM's own analysis/response as a result
            # 正经注释：将LLM自身的文本分析也纳入研究结果，作为补充信息
            # 大白话注释：AI自己写的分析总结也算一份研究结果
            if hasattr(response, 'content') and response.content:
                llm_analysis = {
                    "title": f"LLM Analysis: {query}",  # 正经注释：LLM分析结果的标题 / 大白话注释：标题叫"AI分析：你的问题"
                    "href": "mcp://llm_analysis",  # 正经注释：虚拟链接标识 / 大白话注释：假的链接，表示这是AI自己写的
                    "body": response.content  # 正经注释：LLM的原始响应内容 / 大白话注释：AI写的具体分析内容
                }
                research_results.append(llm_analysis)

                # Log LLM analysis content
                # 正经注释：记录LLM分析内容的预览
                # 大白话注释：把AI的分析也记到日志里
                analysis_preview = response.content[:300] + "..." if len(response.content) > 300 else response.content
                logger.debug(f"LLM Analysis: {analysis_preview}")
                logger.info("Added LLM analysis to results")

            logger.info(f"Research completed with {len(research_results)} total results")
            return research_results  # 正经注释：返回全部研究结果 / 大白话注释：把一篮子结果交出去

        except Exception as e:  # 正经注释：捕获整个研究流程的异常，优雅降级返回空列表 / 大白话注释：出大问题了，记录错误后返回空结果，不让程序崩
            logger.error(f"Error in LLM research with tools: {e}")
            return []

    def _process_tool_result(self, tool_name: str, result: Any) -> List[Dict[str, str]]:
        """
        Process tool result into search result format.

        Args:
            tool_name: Name of the tool that produced the result
            result: The tool result

        Returns:
            List[Dict[str, str]]: Formatted search results

        【正经注释】
        将工具执行的原始结果转换为标准搜索结果格式（包含 title、href、body 字段）。
        处理多种可能的返回格式：MCP 标准包装（structured_content/content）、
        列表、字典、以及其他类型。具备完善的异常回退机制。

        【大白话注释】
        这个方法是个"格式转换器"，把工具返回的各种奇奇怪怪的数据
        统一整理成 {标题、链接、内容} 的格式。因为不同工具返回的格式
        千奇百怪，所以这里要处理各种情况，怎么都不能让程序崩。
        """
        search_results = []  # 正经注释：初始化格式化结果列表 / 大白话注释：准备一个篮子装整理好的结果
        
        try:
            # 1) First: handle MCP result wrapper with structured_content/content
            # 正经注释：优先处理MCP标准结果包装格式，包含structured_content或content字段
            # 大白话注释：第一种情况：MCP标准格式，里面有结构化内容或纯文本内容
            if isinstance(result, dict) and ("structured_content" in result or "content" in result):
                search_results = []
                # Prefer structured_content when present
                # 正经注释：优先使用structured_content字段（结构化数据）
                # 大白话注释：有结构化数据就先处理结构化的
                structured = result.get("structured_content")
                if isinstance(structured, dict):
                    items = structured.get("results")  # 正经注释：获取结果列表 / 大白话注释：从结构化数据里拿结果数组
                    if isinstance(items, list):
                        for i, item in enumerate(items):
                            if isinstance(item, dict):
                                search_results.append({
                                    "title": item.get("title", f"Result from {tool_name} #{i+1}"),  # 正经注释：结果标题 / 大白话注释：标题
                                    "href": item.get("href", item.get("url", f"mcp://{tool_name}/{i}")),  # 正经注释：结果链接 / 大白话注释：链接
                                    "body": item.get("body", item.get("content", str(item)))  # 正经注释：结果正文 / 大白话注释：正文内容
                                })
                    # If no items array but structured is dict, treat as single
                    # 正经注释：如果结构化数据中没有results数组，将整个字典作为单条结果处理
                    # 大白话注释：没有结果数组？那就把整个数据当作一条结果
                    elif isinstance(structured, dict):
                        search_results.append({
                            "title": structured.get("title", f"Result from {tool_name}"),
                            "href": structured.get("href", structured.get("url", f"mcp://{tool_name}")),
                            "body": structured.get("body", structured.get("content", str(structured)))
                        })
                # Fallback to content if provided (MCP spec: list of {type: text, text: ...})
                # 正经注释：如果没有structured_content，回退处理content字段（MCP规范格式：{type: text, text: ...}列表）
                # 大白话注释：结构化数据没拿到结果，那就看纯文本内容字段
                if not search_results:
                    content_field = result.get("content")  # 正经注释：获取content字段 / 大白话注释：拿纯文本内容
                    if isinstance(content_field, list):  # 正经注释：content是列表时，逐个提取文本 / 大白话注释：内容是一段一段的文本
                        texts = []
                        for part in content_field:
                            if isinstance(part, dict):
                                if part.get("type") == "text" and isinstance(part.get("text"), str):
                                    texts.append(part["text"])  # 正经注释：提取MCP标准文本片段 / 大白话注释：拿到文本
                                elif "text" in part:
                                    texts.append(str(part.get("text")))  # 正经注释：提取非标准文本字段 / 大白话注释：有text字段就拿
                                else:
                                    # unknown piece; stringify
                                    texts.append(str(part))  # 正经注释：未知格式转为字符串 / 大白话注释：不认识的格式直接转字符串
                            else:
                                texts.append(str(part))  # 正经注释：非字典元素转字符串 / 大白话注释：不是字典就转字符串
                        body_text = "\n\n".join([t for t in texts if t])  # 正经注释：用双换行拼接所有文本片段 / 大白话注释：把所有文本段落拼起来
                    elif isinstance(content_field, str):
                        body_text = content_field  # 正经注释：content本身就是字符串 / 大白话注释：内容就是纯文本
                    else:
                        body_text = str(result)  # 正经注释：其他类型转字符串兜底 / 大白话注释：兜底，转字符串
                    search_results.append({
                        "title": f"Result from {tool_name}",
                        "href": f"mcp://{tool_name}",
                        "body": body_text,
                    })
                return search_results  # 正经注释：MCP包装格式处理完毕直接返回 / 大白话注释：处理好了直接交出去

            # 2) If the result is already a list, process each item normally
            # 正经注释：处理结果为列表的情况，逐项转换为标准格式
            # 大白话注释：第二种情况：结果是列表，一条条处理
            if isinstance(result, list):
                # If the result is already a list, process each item
                for i, item in enumerate(result):
                    if isinstance(item, dict):
                        # Use the item as is if it has required fields
                        # 正经注释：如果列表项已包含标准字段，直接映射
                        # 大白话注释：这条数据有标题和内容字段，直接用
                        if "title" in item and ("content" in item or "body" in item):
                            search_result = {
                                "title": item.get("title", ""),
                                "href": item.get("href", item.get("url", f"mcp://{tool_name}/{i}")),
                                "body": item.get("body", item.get("content", str(item))),
                            }
                            search_results.append(search_result)
                        else:
                            # Create a search result with a generic title
                            # 正经注释：缺少标准字段时创建通用标题的结果
                            # 大白话注释：字段不全，给个默认标题，内容直接转字符串
                            search_result = {
                                "title": f"Result from {tool_name}",
                                "href": f"mcp://{tool_name}/{i}",
                                "body": str(item),
                            }
                            search_results.append(search_result)
            # 3) If the result is a dict (non-MCP wrapper), use it as a single search result
            # 正经注释：处理结果为普通字典（非MCP包装）的情况，作为单条结果
            # 大白话注释：第三种情况：结果是字典但不是MCP标准格式，当一条结果处理
            elif isinstance(result, dict):
                search_result = {
                    "title": result.get("title", f"Result from {tool_name}"),
                    "href": result.get("href", result.get("url", f"mcp://{tool_name}")),
                    "body": result.get("body", result.get("content", str(result))),
                }
                search_results.append(search_result)
            else:
                # For any other type, convert to string and use as a single search result
                # 正经注释：其他类型直接转字符串作为单条结果
                # 大白话注释：第四种情况：啥也不是，直接转字符串凑一条结果
                search_result = {
                    "title": f"Result from {tool_name}",
                    "href": f"mcp://{tool_name}",
                    "body": str(result),
                }
                search_results.append(search_result)
                
        except Exception as e:  # 正经注释：捕获结果处理异常，使用兜底策略确保不返回空结果 / 大白话注释：格式转换出错了也没关系，用兜底方案凑一条结果
            logger.error(f"Error processing tool result from {tool_name}: {e}")
            # Fallback: create a basic result
            # 正经注释：兜底策略：将原始结果转为字符串作为内容
            # 大白话注释：兜底方案：把原始数据直接转字符串当结果
            search_result = {
                "title": f"Result from {tool_name}",
                "href": f"mcp://{tool_name}",
                "body": str(result),
            }
            search_results.append(search_result)

        return search_results  # 正经注释：返回格式化后的搜索结果列表 / 大白话注释：把整理好的结果交出去 