from datetime import datetime
import asyncio
from typing import Dict, List, Optional

from langgraph.graph import StateGraph, END

from .utils.views import print_agent_output
from .utils.llms import call_model
from ..memory.draft import DraftState
from . import ResearchAgent, ReviewerAgent, ReviserAgent


class EditorAgent:
    """Agent responsible for editing and managing code."""

    def __init__(self, websocket=None, stream_output=None, tone=None, headers=None):
        self.websocket = websocket
        self.stream_output = stream_output
        self.tone = tone
        self.headers = headers or {}

    async def plan_research(self, research_state: Dict[str, any]) -> Dict[str, any]:
        """
        规划研究报告大纲。

        【正经注释】
        根据初始研究摘要、任务参数以及可选的人类反馈，构造规划提示词并调用 LLM，
        要求模型返回 JSON 格式的报告标题、日期和章节列表。该方法是 EditorAgent 在
        LangGraph 工作流中负责“planner”节点的核心逻辑。

        【大白话注释】
        这个方法就是“先看一眼前面搜到的资料，然后让模型列个写作提纲”。
        如果用户给了修改意见，它也会把意见带进去，让模型按用户想法重新规划章节。

        Args:
            research_state: 研究流程状态字典（大白话：前面步骤传下来的任务资料包）

        Returns:
            Dict[str, any]: 包含 title、date、sections 的规划结果（大白话：文章标题、日期和章节列表）
        """
        # 正经注释：从共享状态中提取初始研究结果和任务配置，作为规划提示词的输入上下文。
        # 大白话注释：先把“已有资料”和“任务要求”拿出来，后面才能让模型按这些信息列提纲。
        initial_research = research_state.get("initial_research")
        task = research_state.get("task")
        include_human_feedback = task.get("include_human_feedback")
        human_feedback = research_state.get("human_feedback")
        max_sections = task.get("max_sections")

        # 正经注释：生成符合 LLM 对话格式的规划 prompt，包含系统角色和用户指令。
        # 大白话注释：把资料、反馈、章节数量限制包装成模型能听懂的问题。
        prompt = self._create_planning_prompt(
            initial_research, include_human_feedback, human_feedback, max_sections)

        print_agent_output(
            "Planning an outline layout based on initial research...", agent="EDITOR")

        # 正经注释：调用指定模型并要求返回 JSON，便于后续工作流直接读取结构化字段。
        # 大白话注释：让模型吐出规整的 JSON，不然后面程序不好拆标题和章节。
        plan = await call_model(
            prompt=prompt,
            model=task.get("model"),
            response_format="json",
        )
        print(f"planner环节： {plan}")

        # 正经注释：只透传工作流需要的字段，避免把模型返回的额外内容混入状态。
        # 大白话注释：最后只拿标题、日期、章节这三样，其他杂七杂八的不要。
        return {
            "title": plan.get("title"),
            "date": plan.get("date"),
            "sections": plan.get("sections"),
        }

    async def run_parallel_research(self, research_state: Dict[str, any]) -> Dict[str, List[str]]:
        """
        并行执行多个章节的深入研究。

        【正经注释】
        根据规划阶段生成的 sections 列表，为每个章节创建一个独立的 LangGraph 工作流实例，
        使用 asyncio.gather 并发执行所有章节的研究任务。每个工作流依次执行
        researcher → reviewer → reviser（如果审阅不通过）的流程，最终产出各章节的 draft。
        这是 EditorAgent 在 LangGraph 工作流中负责 "researcher" 节点的核心逻辑。

        【大白话注释】
        这个方法就是"把章节分给多个人同时去研究"。
        规划阶段定了哪些章节，这里就同时派任务出去，每个章节都走一遍"查资料→审核→修改"的流程。
        最后把所有章节的研究结果收集起来。

        Args:
            research_state: 研究流程状态字典，包含 sections（章节列表）、title 等。
                （大白话：包含要研究的章节标题和文章总标题等信息的资料包）

        Returns:
            Dict[str, List[str]]: 包含 research_data 键的字典，值为各章节研究结果列表。
                （大白话：{"research_data": [章节1的草稿, 章节2的草稿, ...]}）
        """
        # 正经注释：初始化子 Agent（ResearchAgent、ReviewerAgent、ReviserAgent），
        # 创建带 researcher→reviewer→reviser 循环的 LangGraph 工作流并编译。
        # 大白话注释：准备好"写手"、"审稿人"、"修改员"三个角色，搭好工作流程。
        agents = self._initialize_agents()
        workflow = self._create_workflow()
        chain = workflow.compile()

        # 正经注释：从研究状态中提取规划阶段生成的章节标题列表和文章总标题。
        # 大白话注释：拿出前面规划好的章节列表和文章标题，后面分任务要用。
        queries = research_state.get("sections")
        title = research_state.get("title")

        # 正经注释：通过 WebSocket 或终端输出并行研究开始日志。
        # 大白话注释：通知前端或控制台"开始并行搜索了"。
        self._log_parallel_research(queries)

        # 正经注释：为每个章节创建独立的工作流任务，使用 asyncio.gather 并发执行。
        # 每个任务包含该章节的研究 topic、文章标题以及原始 task 配置。
        # 大白话注释：每个章节都单独开一个"查资料"任务，大家一起同时跑，不排队。
        final_drafts = [
            chain.ainvoke(self._create_task_input(
                research_state, query, title), config={"tags": ["gpt-researcher"]})
            for query in queries
        ]

        # 正经注释：等待所有并行任务完成，从每个任务的返回结果中提取 "draft" 字段。
        # 大白话注释：等所有章节都查完了，挨个把它们的草稿内容拿出来。
        research_results = [
            result["draft"] for result in await asyncio.gather(*final_drafts)
        ]

        # 正经注释：以字典形式返回所有章节的研究结果，供 writer 阶段使用。
        # 大白话注释：把所有章节的搜索结果打包返回，给后面的"写报告"阶段用。
        print(f"researcher环节子查询完成，所有结果打包：{research_results}")
        return {"research_data": research_results}

    def _create_planning_prompt(self, initial_research: str, include_human_feedback: bool,
                                human_feedback: Optional[str], max_sections: int) -> List[Dict[str, str]]:
        """Create the prompt for research planning."""
        return [
            {
                "role": "system",
                "content": "You are a research editor. Your goal is to oversee the research project "
                           "from inception to completion. Your main task is to plan the article section "
                           "layout based on an initial research summary.\n ",
            },
            {
                "role": "user",
                "content": self._format_planning_instructions(initial_research, include_human_feedback,
                                                              human_feedback, max_sections),
            },
        ]

    def _format_planning_instructions(self, initial_research: str, include_human_feedback: bool,
                                      human_feedback: Optional[str], max_sections: int) -> str:
        """Format the instructions for research planning."""
        today = datetime.now().strftime('%d/%m/%Y')
        feedback_instruction = (
            f"Human feedback: {human_feedback}. You must plan the sections based on the human feedback."
            if include_human_feedback and human_feedback and human_feedback != 'no'
            else ''
        )

        return f"""Today's date is {today}
                   Research summary report: '{initial_research}'
                   {feedback_instruction}
                   \nYour task is to generate an outline of sections headers for the research project
                   based on the research summary report above.
                   You must generate a maximum of {max_sections} section headers.
                   You must focus ONLY on related research topics for subheaders and do NOT include introduction, conclusion and references.
                   You must return nothing but a JSON with the fields 'title' (str) and 
                   'sections' (maximum {max_sections} section headers) with the following structure:
                   '{{title: string research title, date: today's date, 
                   sections: ['section header 1', 'section header 2', 'section header 3' ...]}}'."""

    def _initialize_agents(self) -> Dict[str, any]:
        """Initialize the research, reviewer, and reviser skills."""
        return {
            "research": ResearchAgent(self.websocket, self.stream_output, self.tone, self.headers),
            "reviewer": ReviewerAgent(self.websocket, self.stream_output, self.headers),
            "reviser": ReviserAgent(self.websocket, self.stream_output, self.headers),
        }


    def _create_workflow(self) -> StateGraph:
        """Create the workflow for the research process."""
        agents = self._initialize_agents()
        workflow = StateGraph(DraftState)

        workflow.add_node("researcher", agents["research"].run_depth_research)
        workflow.add_node("reviewer", agents["reviewer"].run)
        workflow.add_node("reviser", agents["reviser"].run)

        workflow.set_entry_point("researcher")
        workflow.add_edge("researcher", "reviewer")
        workflow.add_edge("reviser", "reviewer")
        workflow.add_conditional_edges(
            "reviewer",
            lambda draft: "accept" if draft["review"] is None else "revise",
            {"accept": END, "revise": "reviser"},
        )

        return workflow

    def _log_parallel_research(self, queries: List[str]) -> None:
        """Log the start of parallel research tasks."""
        if self.websocket and self.stream_output:
            asyncio.create_task(self.stream_output(
                "logs",
                "parallel_research",
                f"Running parallel research for the following queries: {queries}",
                self.websocket,
            ))
        else:
            print_agent_output(
                f"Running the following research tasks in parallel: {queries}...",
                agent="EDITOR",
            )

    def _create_task_input(self, research_state: Dict[str, any], query: str, title: str) -> Dict[str, any]:
        """Create the input for a single research task."""
        return {
            "task": research_state.get("task"),
            "topic": query,
            "title": title,
            "headers": self.headers,
        }
