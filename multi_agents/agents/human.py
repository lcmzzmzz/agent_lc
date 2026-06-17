import json


class HumanAgent:
    """
    人工审核 Agent，负责在规划阶段插入人工反馈环节。

    【正经注释】
    在顶层 LangGraph 工作流中承担 "human" 节点角色，位于 planner 之后、
    researcher 之前。它提供一个可选的"人在回路中"环节：
    如果 task 配置了 include_human_feedback=True，则向用户展示规划好的章节大纲，
    等待用户反馈修改意见，再决定是进入 researcher 还是退回 planner 重新规划。

    【大白话注释】
    这个角色就是"让用户看一眼大纲再放行"。
    如果任务设置说要人工审核，就把 planner 排好的章节列表拿给用户看，
    用户说"没问题"就继续，用户说"这里改一下"就退回 planner 重排。
    """

    def __init__(self, websocket=None, stream_output=None, headers=None):
        self.websocket = websocket
        self.stream_output = stream_output
        self.headers = headers or {}

    async def review_plan(self, research_state: dict):
        """
        审阅研究规划大纲，收集用户反馈。

        【正经注释】
        根据 task 中的 include_human_feedback 配置决定是否等待人工反馈。
        如果开启了人类反馈，优先通过 WebSocket 向前端发送请求，
        否则回退到控制台 input() 交互。
        用户回复 "no" 视为无反馈（审核通过），其他内容视为修改意见。
        同时累计 plan_revision_count，用于条件边判断是否超过最大修订次数。

        【大白话注释】
        把章节大纲拿给用户看，问"你觉得这大纲行不行？"。
        有 WebSocket 就走前端弹窗，没有就在终端等着用户打字。
        用户说 "no" 就是没意见直接过，说了别的就当修改意见退回去改。
        统计这是第几次改大纲了，改太多就强制过。

        Args:
            research_state: 当前 ResearchState 字典，包含 task、sections 等。
                （大白话：包含任务配置和 planner 排好的章节列表）

        Returns:
            dict: {
                "human_feedback": str | None,      # 用户反馈内容，None 表示通过
                "plan_revision_count": int          # 已修订次数
            }
                （大白话：用户的修改意见和已经改了几回了）
        """
        print(f"HumanAgent websocket: {self.websocket}")
        print(f"HumanAgent stream_output: {self.stream_output}")
        task = research_state.get("task")
        layout = research_state.get("sections")

        user_feedback = None

        if task.get("include_human_feedback"):
            # Stream response to the user if a websocket is provided (such as from web app)
            # 【正经注释】通过 WebSocket 向前端发送章节大纲并等待用户回复
            # 大白话注释：有 WebSocket 就走前端交互，把大纲发给用户等回复
            if self.websocket and self.stream_output:
                try:
                    await self.stream_output(
                        "human_feedback",
                        "request",
                        f"Any feedback on this plan of topics to research? {layout}? If not, please reply with 'no'.",
                        self.websocket,
                    )
                    # because websocket is wrapped inside a CustomLogsHandler in websocket_manager
                    # 【正经注释】等待 WebSocket 客户端发回用户反馈 JSON
                    # 大白话注释：等着用户前端点"通过"或写修改意见
                    response = await self.websocket.websocket.receive_text()
                    print(f"Received response: {response}", flush=True)
                    response_data = json.loads(response)
                    if response_data.get("type") == "human_feedback":
                        user_feedback = response_data.get("content")
                    else:
                        print(
                            f"Unexpected response type: {response_data.get('type')}",
                            flush=True,
                        )
                except Exception as e:
                    print(f"Error receiving human feedback: {e}", flush=True)
            # Otherwise, prompt the user for feedback in the console
            # 【正经注释】回退到命令行交互模式
            # 大白话注释：没有 WebSocket 就在终端等着用户打字
            else:
                user_feedback = input(
                    f"Any feedback on this plan? {layout}? If not, please reply with 'no'.\n>> "
                )

        # 【正经注释】如果用户回复包含 "no"，忽略大小写和空格，视为无反馈
        # 大白话注释：用户说 "no" 或 "NO" 或 " no " 都算通过，没意见
        if user_feedback and "no" in user_feedback.strip().lower():
            user_feedback = None

        # 【正经注释】只有真的有反馈内容时才累加修订次数
        # 大白话注释：只有用户确实提了修改意见，才算是改了一次
        plan_revision_count = research_state.get("plan_revision_count", 0)
        if user_feedback:
            plan_revision_count += 1

        print(f"User feedback before return: {user_feedback}")

        # 【正经注释】返回值会合并到 ResearchState["human_feedback"] 和
        # ResearchState["plan_revision_count"]，由条件边决定下一步走向。
        # 大白话注释：把反馈和修订次数返回给工作流，让路由判断是继续还是重排。
        return {
            "human_feedback": user_feedback,
            "plan_revision_count": plan_revision_count,
        }
