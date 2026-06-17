# 导入操作系统模块，用于文件和目录操作
import os
# 导入时间模块，用于生成基于时间的任务ID等
import time
# 导入日期时间模块，用于获取UTC时间戳
import datetime
# 从 langgraph 导入状态图构建器和结束节点常量，用于构建工作流
from langgraph.graph import StateGraph, END
# 从 langgraph 导入内存检查点保存器（当前被注释掉，未启用）
# from langgraph.checkpoint.memory import MemorySaver
# 从当前包的工具类中导入用于打印Agent输出的函数
from .utils.views import print_agent_output
# 从 memory 模块中导入研究状态类，用于定义工作流的状态结构
from ..memory.research import ResearchState
# 从工具类中导入文件名清理函数，用于生成安全的文件路径
from .utils.utils import sanitize_filename
# 从 plan_review 模块中导入默认最大计划修改次数、人工反馈路由函数
from .plan_review import (
    DEFAULT_MAX_PLAN_REVISIONS,
    route_human_feedback,
)

# Import agent classes
from . import \
    WriterAgent, \
    EditorAgent, \
    PublisherAgent, \
    ResearchAgent, \
    HumanAgent


class ChiefEditorAgent:
    """负责管理和协调编辑任务的总编辑Agent类。"""

    # 初始化方法，接收任务信息、WebSocket连接、流式输出回调、语气设置和请求头
    def __init__(self, task: dict, websocket=None, stream_output=None, tone=None, headers=None):
        self.task = task  # 保存传入的任务字典
        self.websocket = websocket  # 保存WebSocket连接对象，用于实时通信
        self.stream_output = stream_output  # 保存流式输出回调函数
        self.headers = headers or {}  # 保存请求头，如果未提供则默认为空字典
        self.tone = tone  # 保存文本生成的语气设置
        self.task_id = self._generate_task_id()  # 调用内部方法生成唯一的任务ID
        self.output_dir = self._create_output_directory()  # 调用内部方法创建输出目录

    # 生成任务ID的私有方法
    def _generate_task_id(self):
        # 当前基于时间戳生成ID，但未来可以替换为任何唯一标识符
        return int(time.time())

    # 创建输出目录的私有方法
    def _create_output_directory(self):
        # 拼接输出目录路径：基础目录 + 清理后的文件名（包含任务ID和查询内容的前40个字符）
        output_dir = "./outputs/" + \
            sanitize_filename(
                f"run_{self.task_id}_{self.task.get('query')[0:40]}")

        # 创建目录，如果目录已存在则不抛出异常
        os.makedirs(output_dir, exist_ok=True)
        # 返回创建好的输出目录路径
        return output_dir

    # 初始化各个Agent实例的私有方法
    def _initialize_agents(self):
        # 返回一个包含所有Agent实例的字典
        return {
            # 初始化写作Agent，传入WebSocket、流式输出和请求头
            "writer": WriterAgent(self.websocket, self.stream_output, self.headers),
            # 初始化编辑Agent，额外传入语气设置
            "editor": EditorAgent(self.websocket, self.stream_output, self.tone, self.headers),
            # 初始化研究Agent，额外传入语气设置
            "research": ResearchAgent(self.websocket, self.stream_output, self.tone, self.headers),
            # 初始化发布Agent，额外传入输出目录路径
            "publisher": PublisherAgent(self.output_dir, self.websocket, self.stream_output, self.headers),
            # 初始化人工审核Agent
            "human": HumanAgent(self.websocket, self.stream_output, self.headers)
        }

    # 创建工作流的私有方法，接收已初始化的Agent字典
    def _create_workflow(self, agents):
        # 使用 ResearchState 作为状态类型初始化一个状态图工作流
        workflow = StateGraph(ResearchState)

        # 为工作流添加各个Agent对应的节点，并绑定它们的执行方法
        workflow.add_node("browser", agents["research"].run_initial_research)  # 浏览器节点：执行初步研究
        workflow.add_node("planner", agents["editor"].plan_research)  # 计划节点：制定研究计划
        workflow.add_node("researcher", agents["editor"].run_parallel_research)  # 研究员节点：并行执行研究
        workflow.add_node("writer", agents["writer"].run)  # 写作节点：执行写作任务
        workflow.add_node("publisher", agents["publisher"].run)  # 发布节点：执行发布任务
        workflow.add_node("human", agents["human"].review_plan)  # 人工节点：审核计划

        # 调用内部方法添加节点之间的边（连接关系）
        self._add_workflow_edges(workflow)

        # 返回构建好的工作流对象
        return workflow

    # 添加工作流边（节点连接和流转逻辑）的私有方法
    def _add_workflow_edges(self, workflow):
        """
        配置顶层 LangGraph 工作流的节点流转关系

        【正经注释】
        为 ResearchState 工作流添加固定边和条件边：固定边定义确定性的节点执行顺序，
        条件边基于 HumanAgent 的反馈结果动态选择后续节点，从而实现人工审核后的接受或重规划分支。

        【大白话注释】
        这个方法不是让 Agent 干活，而是给流程图“画箭头”：
        哪个节点跑完后去哪个节点，哪里需要根据人工反馈走不同路线，都在这里规定。

        Args:
            workflow: LangGraph 的 StateGraph 实例（大白话：还没编译的流程图对象）
        """
        # 正经注释：添加固定边，browser 节点执行完成后必然进入 planner 节点。
        # 大白话注释：先做初步研究，研究完就去规划大纲。
        workflow.add_edge('browser', 'planner')
        # 正经注释：添加固定边，planner 节点生成大纲后必然进入 human 节点。
        # 大白话注释：大纲规划完后，去看看要不要人工审核。
        workflow.add_edge('planner', 'human')
        # 正经注释：添加固定边，researcher 节点完成章节并行研究后进入 writer 节点。
        # 大白话注释：所有章节研究完，就交给写作者汇总成报告。
        workflow.add_edge('researcher', 'writer')
        # 正经注释：添加固定边，writer 节点完成报告内容组织后进入 publisher 节点。
        # 大白话注释：报告写好后，就交给发布者导出文件。
        workflow.add_edge('writer', 'publisher')
        # 正经注释：设置图的入口节点，LangGraph 执行时会从 browser 开始。
        # 大白话注释：整条流程第一步从“初步研究”开始。
        workflow.set_entry_point("browser")
        # 正经注释：添加终止边，publisher 节点执行完成后工作流结束。
        # 大白话注释：文件发布完，这轮多 Agent 任务就结束。
        workflow.add_edge('publisher', END)

        # 【正经注释】
        # 为 human 节点添加条件边。human 节点完成后，LangGraph 会调用 _route_human_feedback
        # 判断路由标签：返回 "accept" 则进入 researcher，返回 "revise" 则回到 planner 重新规划。
        #
        # 【大白话注释】
        # 这里是一个岔路口：
        # 如果人觉得大纲可以，就继续做章节研究；如果人提了修改意见，就回去重新做大纲。
        workflow.add_conditional_edges(
            'human',
            self._route_human_feedback,
            {"accept": "researcher", "revise": "planner"}
        )

    # 路由人工反馈的私有方法，决定人工审核后的下一步操作
    def _route_human_feedback(self, review):
        # 从任务配置中获取最大计划修改次数，如果未配置则使用默认值
        max_plan_revisions = self.task.get(
            "max_plan_revisions", DEFAULT_MAX_PLAN_REVISIONS)
        # 调用外部路由函数，传入审核结果和最大修改次数，返回路由决策
        return route_human_feedback(review, max_plan_revisions)

    # 初始化研究团队的方法，对外暴露
    def init_research_team(self):
        """初始化研究团队并创建工作流。"""
        # 调用内部方法初始化所有Agent
        agents = self._initialize_agents()
        # 使用初始化的Agent创建工作流并返回
        return self._create_workflow(agents)

    # 异步方法：记录研究开始的日志
    async def _log_research_start(self):
        # 格式化研究开始的日志消息
        message = f"Starting the research process for query '{self.task.get('query')}'..."
        # 如果配置了WebSocket和流式输出，则通过流式输出发送日志
        if self.websocket and self.stream_output:
            await self.stream_output("logs", "starting_research", message, self.websocket)
        else:
            # 否则在控制台打印Agent输出日志
            print_agent_output(message, "MASTER")

    # 异步方法：运行研究任务
    async def run_research_task(self, task_id=None):
        """
        执行多 Agent 研究工作流

        【正经注释】
        初始化并编译 LangGraph 工作流，将任务配置作为初始 ResearchState 输入，
        通过 ainvoke 异步触发整条状态图执行。config 中的 thread_id 用于标识
        本次工作流线程，便于 LangGraph 在启用 checkpoint 时区分、保存和恢复状态。

        【大白话注释】
        这个函数就是按下“开始研究”的按钮：
        先把多 Agent 流程图搭好，再给它一个初始任务配置，
        然后 LangGraph 会按照 browser、planner、human、researcher、writer、publisher
        的顺序自己往下跑，最后返回完整结果。

        Args:
            task_id: 工作流线程 ID（大白话：这次研究任务的编号，可用于区分不同任务）

        Returns:
            dict: LangGraph 最终状态（大白话：包含最终报告和中间研究结果的一整包数据）
        """
        # 正经注释：创建顶层 ResearchState 工作流图，包含 browser/planner/human/researcher/writer/publisher 等节点。
        # 大白话注释：先把“多 Agent 团队流程图”搭出来，但这时还没真正开始跑。
        research_team = self.init_research_team()
        # 正经注释：将 StateGraph 编译为可执行链，后续可通过 ainvoke/astream 等方法运行。
        # 大白话注释：把流程图变成一个能执行的对象，类似把图纸变成机器。
        chain = research_team.compile()

        # 正经注释：在工作流执行前输出开始日志，支持 WebSocket 流式日志或本地控制台日志。
        # 大白话注释：正式开跑前先喊一声：“我要开始研究这个问题了”。
        await self._log_research_start()

        # 【正经注释】
        # configurable 是 LangGraph 的运行时配置区域；thread_id 用来标识一次独立的工作流线程。
        # 当前代码未启用 checkpointer，因此 thread_id 主要用于追踪和未来扩展；若接入 MemorySaver/SqliteSaver，
        # LangGraph 可用同一个 thread_id 读取此前保存的状态，从而实现中断恢复。
        #
        # 【大白话注释】
        # 这里是在给这次研究任务贴一个“编号”和“时间戳”。
        # 现在主要是方便识别；以后如果开启保存进度，就能靠这个编号找回上次跑到哪了。
        config = {
            # 正经注释：LangGraph 规定的运行时配置入口，传给图执行器而不是传给业务 Agent。
            # 大白话注释：这是给 LangGraph 自己看的“运行参数”，不是给研究任务正文用的。
            "configurable": {
                # 正经注释：当前工作流线程的唯一标识；启用 checkpoint 后可用于保存/恢复同一轮图状态。
                # 大白话注释：这就是这次研究任务的编号，以后要续跑就靠它认出来。
                "thread_id": task_id,
                # 正经注释：记录本次图执行的 UTC 时间戳，便于追踪运行时间。
                # 大白话注释：给这次任务记个开始时间，方便查日志。
                "thread_ts": datetime.datetime.utcnow()
            }
        }

        # 正经注释：以 {"task": self.task} 作为初始 ResearchState，异步执行整个 LangGraph。
        # 大白话注释：只先塞进去 task，后面的 Agent 会一个接一个把研究结果、章节、报告写进 state。
        result = await chain.ainvoke({"task": self.task}, config=config)
        # 正经注释：返回 LangGraph 执行完成后的最终 state。
        # 大白话注释：把最后那一整包结果交出去，里面最重要的是 report。
        return result