from .utils.views import print_agent_output
from .utils.llms import call_model

TEMPLATE = """You are an expert research article reviewer. \
Your goal is to review research drafts and provide feedback to the reviser only based on specific guidelines. \
"""


class ReviewerAgent:
    """
    研究草稿审阅 Agent。

    【正经注释】
    在 DraftState 子工作流中承担 "reviewer" 节点角色，根据任务指定的 guidelines
    审阅 researcher 生成的 draft，决定是接受（返回 None）还是退回修改（返回修改意见）。
    支持多轮审阅循环：reviewer → reviser → reviewer。

    【大白话注释】
    这个角色就是"审稿人"。看看写好的草稿有没有达到要求，
    没问题就放行，有问题就写修改意见退回去改。
    """

    def __init__(self, websocket=None, stream_output=None, headers=None):
        self.websocket = websocket
        self.stream_output = stream_output
        self.headers = headers or {}

    async def review_draft(self, draft_state: dict):
        """
        审阅单篇草稿，返回修改意见或 None。

        【正经注释】
        根据任务配置的 guidelines 构建审阅提示词。如果是第二轮及以后的审阅（有 revision_notes），
        会在 prompt 中追加前一轮的修改记录，并提示只在必要时才提新的修改意见，
        避免无限循环。最终返回 None 表示通过，返回字符串表示修改意见。

        【大白话注释】
        把草稿和审阅标准发给模型，让模型打分。
        如果这是第二次审阅（已经改过一轮了），会提醒模型"别太苛刻，差不多就行了"。

        Args:
            draft_state: 包含 task、draft、revision_notes 等字段的状态字典。
                （大白话：包含原始任务、草稿内容、前一轮修改记录等）

        Returns:
            None: 草稿通过审核。
            str: 修改意见文本。
        """
        # 正经注释：从任务中提取审阅标准（guidelines），多个标准拼接为列表格式。
        # 大白话注释：把审核标准拿出来，整理成模型能看懂的一条一条的格式。
        task = draft_state.get("task")
        guidelines = "- ".join(guideline for guideline in task.get("guidelines"))
        revision_notes = draft_state.get("revision_notes")

        # 正经注释：如果存在前一轮修改记录，构造"二次审阅"提示词，引导模型只在必要时提意见。
        # 大白话注释：如果这是改过一轮后的再次审核，告诉模型"别吹毛求疵，差不多过了就行"。
        revise_prompt = f"""The reviser has already revised the draft based on your previous review notes with the following feedback:
{revision_notes}\n
Please provide additional feedback ONLY if critical since the reviser has already made changes based on your previous feedback.
If you think the article is sufficient or that non critical revisions are required, please aim to return None.
"""

        # 正经注释：构建完整的审阅提示词，包含系统角色要求、guidelines 标准和草稿内容。
        # 如果是首次审阅（无 revision_notes），revise_prompt 为空。
        # 大白话注释：把审阅要求、标准、草稿全部拼成一段文字发给模型，让模型判断。
        review_prompt = f"""You have been tasked with reviewing the draft which was written by a non-expert based on specific guidelines.
Please accept the draft if it is good enough to publish, or send it for revision, along with your notes to guide the revision.
If not all of the guideline criteria are met, you should send appropriate revision notes.
If the draft meets all the guidelines, please return None.
{revise_prompt if revision_notes else ""}

Guidelines: {guidelines}\nDraft: {draft_state.get("draft")}\n
"""
        # 正经注释：组装为 LLM 消息格式（system + user），调用模型。
        # 大白话注释：把系统角色设定和审阅指令发给 AI，等它给回复。
        prompt = [
            {"role": "system", "content": TEMPLATE},
            {"role": "user", "content": review_prompt},
        ]

        response = await call_model(prompt, model=task.get("model"))

        print(f'researcher环节reviewer子环节： {response}')

        # 正经注释：如果开启 verbose 模式，通过 WebSocket 或终端输出审阅意见。
        # 大白话注释：如果设置了详细输出，就把审稿结果打印出来或推送到前端。
        if task.get("verbose"):
            if self.websocket and self.stream_output:
                await self.stream_output(
                    "logs",
                    "review_feedback",
                    f"Review feedback is: {response}...",
                    self.websocket,
                )
            else:
                print_agent_output(
                    f"Review feedback is: {response}...", agent="REVIEWER"
                )

        # 正经注释：如果模型回复包含 "None"，视为审核通过，返回 None。
        # 否则返回完整修改意见文本，由条件边路由到 reviser 或 END。
        # 大白话注释：模型说"None"就代表通过了，直接过；有其他内容就当修改意见退回去改。
        if "None" in response:
            return None
        return response

    async def run(self, draft_state: dict):
        """
        ReviewerAgent 的 LangGraph 工作流节点入口。

        【正经注释】
        判断任务是否配置了 follow_guidelines。如果配置为 True，则执行 draft 审阅；
        否则跳过审阅直接返回 None。返回值会合并到 DraftState["review"] 字段，
        供条件边 route 判断走 accept（结束）还是 revise（退回修改）。

        【大白话注释】
        这是 LangGraph 工作流调用的入口方法。
        如果任务说要"按标准审稿"，就走审阅流程；否则直接跳过。
        返回的 review 会被条件边用来决定是结束还是退回改。

        Args:
            draft_state: 当前 DraftState 的完整字典。
                （大白话：包含草稿、任务配置等）

        Returns:
            dict: {"review": None 或 "修改意见"}
                （大白话：审核结果，None 代表通过，有内容代表要修改）
        """
        task = draft_state.get("task")
        guidelines = task.get("guidelines")
        to_follow_guidelines = task.get("follow_guidelines")
        review = None

        if to_follow_guidelines:
            print_agent_output(f"Reviewing draft...", agent="REVIEWER")

            if task.get("verbose"):
                print_agent_output(
                    f"Following guidelines {guidelines}...", agent="REVIEWER"
                )

            # 正经注释：按 guidelines 执行完整的 draft 审阅流程。
            # 大白话注释：正经走一遍审稿流程。
            review = await self.review_draft(draft_state)
        else:
            # 正经注释：跳过审阅，直接返回 None 表示通过。
            # 大白话注释：不用审了，直接过。
            print_agent_output(f"Ignoring guidelines...", agent="REVIEWER")

        # 正经注释：返回的 review 会合并到 DraftState["review"]，由条件边决定下一步。
        # 大白话注释：不管审没审，最终都把结果返回给工作流。
        return {"review": review}
