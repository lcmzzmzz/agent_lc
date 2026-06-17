"""
MCP Tool Selection Module

Handles intelligent tool selection using LLM analysis.

【正经注释】
本模块实现了基于大语言模型分析的智能工具选择功能，包括：
- 使用 LLM 分析所有可用工具与研究查询的相关性
- 选择最相关的工具子集用于后续研究
- 提供 LLM 选择失败时的基于模式匹配的兜底选择机制

【大白话注释】
这个文件是 MCP 的"工具挑选员"。MCP 服务器上可能有几十个工具，
不可能全用，所以这个模块就是让 AI 看看哪些工具最适合回答当前问题，
挑出最相关的几个来用。万一 AI 挑选失败了，还有个兜底方案：
按工具名字里的关键词（比如 search、get、find）来选。
"""
import asyncio  # 正经注释：异步IO库 / 大白话注释：异步编程工具包
import json  # 正经注释：JSON解析库，用于解析LLM返回的工具选择结果 / 大白话注释：处理JSON数据用的
import logging  # 正经注释：日志模块 / 大白话注释：打日志用的
from typing import List, Dict, Any, Optional  # 正经注释：类型提示 / 大白话注释：类型标注

logger = logging.getLogger(__name__)  # 正经注释：创建模块级日志记录器 / 大白话注释：给这个文件搞个专属日志器


class MCPToolSelector:
    """
    Handles intelligent selection of MCP tools using LLM analysis.

    Responsible for:
    - Analyzing available tools with LLM
    - Selecting the most relevant tools for a query
    - Providing fallback selection mechanisms

    【正经注释】
    MCP 工具智能选择器，利用大语言模型分析可用工具集合，
    根据研究查询的相关性选出最优工具子集。当 LLM 选择不可用时，
    提供基于关键词模式匹配的兜底选择策略。

    【大白话注释】
    这个类就是"工具挑选专家"。它拿着你的问题和所有可用的工具清单，
    请AI帮忙挑出最适合回答你问题的几个工具。万一AI不给力挑不出来，
    还有个备选方案：看工具名字和描述里有没有"搜索"、"获取"这样的关键词。
    """

    def __init__(self, cfg, researcher=None):
        """
        Initialize the tool selector.

        Args:
            cfg: Configuration object with LLM settings
            researcher: Researcher instance for cost tracking

        【正经注释】
        初始化工具选择器，存储配置对象和研究者实例引用。
        配置对象提供 LLM 参数，研究者实例用于费用追踪。

        【大白话注释】
        构造函数。把配置和研究器存下来，后面要用配置来调AI模型，
        研究器用来记录花了多少钱。
        """
        self.cfg = cfg  # 正经注释：存储配置对象 / 大白话注释：记住配置
        self.researcher = researcher  # 正经注释：存储研究者实例 / 大白话注释：记住研究器

    async def select_relevant_tools(self, query: str, all_tools: List, max_tools: int = 3) -> List:
        """
        Use LLM to select the most relevant tools for the research query.

        Args:
            query: Research query
            all_tools: List of all available tools
            max_tools: Maximum number of tools to select (default: 3)

        Returns:
            List: Selected tools most relevant for the query

        【正经注释】
        利用大语言模型智能选择最相关的研究工具。流程包括：
        1. 为每个工具构建描述信息
        2. 生成工具选择提示词
        3. 调用 LLM 获取选择结果
        4. 解析 JSON 格式的选择结果
        5. 失败时回退到基于模式匹配的兜底方案

        【大白话注释】
        这是工具选择的核心方法。流程是这样的：
        1. 给每个工具写个简介（名字+描述）
        2. 给AI写段提示词，告诉它问题和所有工具的信息
        3. AI返回JSON格式的选择结果
        4. 解析JSON，拿到选中的工具
        5. 如果AI返回的东西解析不了，就用兜底方案选工具
        """
        if not all_tools:  # 正经注释：无可用工具时返回空列表 / 大白话注释：没工具可选就返回空的
            return []

        if len(all_tools) < max_tools:  # 正经注释：工具总数少于上限时调整上限值 / 大白话注释：工具还没上限多，就全选上
            max_tools = len(all_tools)
            
        logger.info(f"Using LLM to select {max_tools} most relevant tools from {len(all_tools)} available")

        # Create tool descriptions for LLM analysis
        # 正经注释：为每个工具构建索引、名称和描述信息，供LLM分析使用
        # 大白话注释：给每个工具写个简介，告诉AI都有啥工具
        tools_info = []
        for i, tool in enumerate(all_tools):
            tool_info = {
                "index": i,  # 正经注释：工具在列表中的索引位置 / 大白话注释：第几个工具
                "name": tool.name,  # 正经注释：工具名称 / 大白话注释：工具叫啥名
                "description": tool.description or "No description available"  # 正经注释：工具描述，无描述时使用默认文本 / 大白话注释：工具是干啥的
            }
            tools_info.append(tool_info)

        # Import here to avoid circular imports
        # 正经注释：延迟导入提示词家族以避免循环依赖
        # 大白话注释：导入提示词模板，放太早会循环引用
        from ..prompts import PromptFamily

        # Create prompt for intelligent tool selection
        # 正经注释：生成工具选择的提示词，包含查询、工具信息和最大选择数
        # 大白话注释：给AI写一段指令，告诉它问题是什么、有哪些工具可选、选几个
        prompt = PromptFamily.generate_mcp_tool_selection_prompt(query, tools_info, max_tools)

        try:
            # Call LLM for tool selection
            # 正经注释：调用LLM获取工具选择结果
            # 大白话注释：让AI帮忙选工具
            response = await self._call_llm_for_tool_selection(prompt)

            if not response:  # 正经注释：LLM无响应时使用兜底方案 / 大白话注释：AI啥也没说，用兜底方案
                logger.warning("No LLM response for tool selection, using fallback")
                return self._fallback_tool_selection(all_tools, max_tools)

            # Log a preview of the LLM response for debugging
            # 正经注释：记录LLM响应预览用于调试
            # 大白话注释：把AI的回复记下来看看
            response_preview = response[:500] + "..." if len(response) > 500 else response
            logger.debug(f"LLM tool selection response: {response_preview}")

            # Parse LLM response
            # 正经注释：解析LLM返回的JSON格式选择结果
            # 大白话注释：把AI返回的JSON字符串解析成字典
            try:
                selection_result = json.loads(response)  # 正经注释：直接解析JSON / 大白话注释：直接解析
            except json.JSONDecodeError:  # 正经注释：JSON解析失败，尝试从响应中提取JSON片段 / 大白话注释：直接解析不了，试试从文本里抠出JSON
                # Try to extract JSON from response
                import re  # 正经注释：导入正则表达式模块 / 大白话注释：用正则从文本里找JSON
                json_match = re.search(r"\{.*\}", response, re.DOTALL)  # 正经注释：用正则匹配花括号包裹的JSON对象 / 大白话注释：从文本里找{...}格式的JSON
                if json_match:
                    try:
                        selection_result = json.loads(json_match.group(0))  # 正经注释：解析提取到的JSON / 大白话注释：抠出来了，再试一次解析
                    except json.JSONDecodeError:  # 正经注释：提取的JSON仍无法解析 / 大白话注释：还是解析不了，算了用兜底
                        logger.warning("Could not parse extracted JSON, using fallback")
                        return self._fallback_tool_selection(all_tools, max_tools)
                else:  # 正经注释：响应中未找到JSON / 大白话注释：文本里根本没JSON，用兜底
                    logger.warning("No JSON found in LLM response, using fallback")
                    return self._fallback_tool_selection(all_tools, max_tools)

            selected_tools = []  # 正经注释：初始化已选工具列表 / 大白话注释：准备一个篮子装选中的工具

            # Process selected tools
            # 正经注释：遍历解析结果中的selected_tools数组，按索引取出对应工具
            # 大白话注释：根据AI选的索引，把工具从列表里挑出来
            for tool_selection in selection_result.get("selected_tools", []):
                tool_index = tool_selection.get("index")  # 正经注释：获取工具索引 / 大白话注释：第几个工具
                tool_name = tool_selection.get("name", "")  # 正经注释：获取工具名称 / 大白话注释：工具叫啥
                reason = tool_selection.get("reason", "")  # 正经注释：获取选择原因 / 大白话注释：AI为什么选它
                relevance_score = tool_selection.get("relevance_score", 0)  # 正经注释：获取相关性评分 / 大白话注释：AI给的相关性打分

                if tool_index is not None and 0 <= tool_index < len(all_tools):  # 正经注释：验证索引有效性 / 大白话注释：索引没越界才要
                    selected_tools.append(all_tools[tool_index])
                    logger.info(f"Selected tool '{tool_name}' (score: {relevance_score}): {reason}")

            if len(selected_tools) == 0:  # 正经注释：LLM未成功选择任何工具时使用兜底方案 / 大白话注释：AI一个工具也没选出来，用兜底
                logger.warning("No tools selected by LLM, using fallback selection")
                return self._fallback_tool_selection(all_tools, max_tools)

            # Log the overall selection reasoning
            # 正经注释：记录LLM的整体选择策略说明
            # 大白话注释：把AI的选择思路记下来
            selection_reasoning = selection_result.get("selection_reasoning", "No reasoning provided")
            logger.info(f"LLM selection strategy: {selection_reasoning}")

            logger.info(f"LLM selected {len(selected_tools)} tools for research")
            return selected_tools  # 正经注释：返回LLM选中的工具列表 / 大白话注释：把选好的工具交出去

        except Exception as e:  # 正经注释：捕获选择流程的所有异常，回退到兜底方案 / 大白话注释：出问题了就用兜底方案，不能让程序崩
            logger.error(f"Error in LLM tool selection: {e}")
            logger.warning("Falling back to pattern-based selection")
            return self._fallback_tool_selection(all_tools, max_tools)

    async def _call_llm_for_tool_selection(self, prompt: str) -> str:
        """
        Call the LLM using the existing create_chat_completion function for tool selection.

        Args:
            prompt (str): The prompt to send to the LLM.

        Returns:
            str: The generated text response.

        【正经注释】
        调用项目统一的 LLM 聊天补全接口进行工具选择。使用策略级模型
        和零温度参数以获得一致的推理结果。支持费用追踪回调。

        【大白话注释】
        这个方法是真正去调AI的地方。用项目自带的聊天接口，选策略级模型
        （因为选工具需要好好想想），温度设为0让AI的输出尽量稳定一致。
        还会把花的钱记到研究者的账上。
        """
        if not self.cfg:  # 正经注释：检查配置是否可用 / 大白话注释：没配置就没法调AI
            logger.warning("No config available for LLM call")
            return ""

        try:
            from ..utils.llm import create_chat_completion  # 正经注释：导入统一的LLM调用工具函数 / 大白话注释：导入调AI的工具

            # Create messages for the LLM
            # 正经注释：构建消息列表
            # 大白话注释：把提示词包装成消息格式
            messages = [{"role": "user", "content": prompt}]

            # Use the strategic LLM for tool selection (as it's more complex reasoning)
            # 正经注释：使用策略级LLM执行工具选择，温度设为0确保结果一致性
            # 大白话注释：用最强模型选工具，温度0让AI每次选的结果尽量一样
            result = await create_chat_completion(
                model=self.cfg.strategic_llm_model,  # 正经注释：策略级LLM模型 / 大白话注释：用哪个AI模型
                messages=messages,  # 正经注释：消息列表 / 大白话注释：发给AI的消息
                temperature=0.0,  # 正经注释：零温度，确保确定性输出 / 大白话注释：温度0，让AI的输出尽量稳定
                llm_provider=self.cfg.strategic_llm_provider,  # 正经注释：LLM服务提供者 / 大白话注释：用哪家的AI服务
                llm_kwargs=self.cfg.llm_kwargs,  # 正经注释：附加LLM参数 / 大白话注释：其他参数
                cost_callback=self.researcher.add_costs if self.researcher and hasattr(self.researcher, 'add_costs') else None,  # 正经注释：费用追踪回调 / 大白话注释：记钱用的回调函数
            )
            return result  # 正经注释：返回LLM生成的文本 / 大白话注释：把AI的回复交出去
        except Exception as e:  # 正经注释：捕获LLM调用异常 / 大白话注释：调AI出错了就返回空字符串
            logger.error(f"Error calling LLM for tool selection: {e}")
            return ""

    def _fallback_tool_selection(self, all_tools: List, max_tools: int) -> List:
        """
        Fallback tool selection using pattern matching if LLM selection fails.

        Args:
            all_tools: List of all available tools
            max_tools: Maximum number of tools to select

        Returns:
            List: Selected tools

        【正经注释】
        兜底工具选择策略，基于关键词模式匹配评分。定义一组研究相关的关键词
        模式，对每个工具的名称和描述进行匹配打分（名称匹配权重3，描述匹配权重1），
        按得分降序取前 N 个工具。

        【大白话注释】
        这是AI选不出来时的"备胎方案"。思路很简单粗暴：
        准备一组研究相关的关键词（search、get、read之类的），
        看工具名字和描述里有没有这些词，有的就加分，
        工具名字里有的加3分，描述里有的加1分，
        最后按分数从高到低选前几个工具。
        """
        # Define patterns for research-relevant tools
        # 正经注释：定义研究相关工具的关键词模式列表
        # 大白话注释：这些关键词用来判断一个工具适不适合做研究
        research_patterns = [
            'search', 'get', 'read', 'fetch', 'find', 'list', 'query',
            'lookup', 'retrieve', 'browse', 'view', 'show', 'describe'
        ]

        scored_tools = []  # 正经注释：带评分的工具列表 / 大白话注释：装"工具+分数"的篮子

        for tool in all_tools:
            tool_name = tool.name.lower()  # 正经注释：工具名称转小写便于匹配 / 大白话注释：名字统一小写
            tool_description = (tool.description or "").lower()  # 正经注释：工具描述转小写 / 大白话注释：描述统一小写

            # Calculate relevance score based on pattern matching
            # 正经注释：基于模式匹配计算相关性评分，名称匹配权重高于描述
            # 大白话注释：算分数：名字里有这个词加3分，描述里有加1分
            score = 0
            for pattern in research_patterns:
                if pattern in tool_name:  # 正经注释：名称中包含关键词，权重3 / 大白话注释：名字里有这个关键词，加分多
                    score += 3
                if pattern in tool_description:  # 正经注释：描述中包含关键词，权重1 / 大白话注释：描述里有这个关键词，加分少
                    score += 1

            if score > 0:  # 正经注释：仅保留得分大于0的工具 / 大白话注释：有分才留
                scored_tools.append((tool, score))

        # Sort by score and take top tools
        # 正经注释：按评分降序排列并取前N个工具
        # 大白话注释：按分数从高到低排，取前几个
        scored_tools.sort(key=lambda x: x[1], reverse=True)  # 正经注释：按分数降序排序 / 大白话注释：分数高的排前面
        selected_tools = [tool for tool, score in scored_tools[:max_tools]]  # 正经注释：提取前max_tools个工具 / 大白话注释：取前N个

        for i, (tool, score) in enumerate(scored_tools[:max_tools]):
            logger.info(f"Fallback selected tool {i+1}: {tool.name} (score: {score})")

        return selected_tools  # 正经注释：返回按评分选出的工具列表 / 大白话注释：把选好的工具交出去 