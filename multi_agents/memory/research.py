"""
顶层研究工作流状态定义。

【正经注释】
此模块定义了顶层 LangGraph 工作流（由 ChiefEditorAgent 编排）所使用的共享状态类型。
工作流节点依次为 browser → planner → human → researcher → writer → publisher，
各节点通过写入和读取此状态的字段来传递数据。状态字段覆盖从初始研究到最终报告的全流程。

【大白话注释】
这个文件定义了"顶层研究流程"中各个角色之间传递数据的"共享小本本"。
browser 搜到的资料、planner 列的章节、writer 写的报告……全都记在这个小本本上，
后面的角色直接从小本本上读就行。
"""
from typing import TypedDict, List, Annotated
import operator


class ResearchState(TypedDict):
    """
    顶层研究工作流状态。

    【正经注释】
    继承 TypedDict，每个字段对应工作流中某个节点的输出或下游节点的输入。
    字段按生命周期大致分为三组：初始研究与规划（task → sections）、
    人工反馈与修订计数（human_feedback / plan_revision_count）、
    最终报告组件（introduction → report）。

    【大白话注释】
    这就是顶层工作流里大家共用的"记事本"。
    每个节点干完活就往里面写点东西，下一个节点接着读。
    """

    # ── 任务与初始研究 ──
    # 大白话：任务配置和 browser 环节搜到的原始资料
    task: dict                    # 原始任务配置，包含 query、source、model 等（大白话：用户一开始提的要求和设置）
    initial_research: str         # browser 节点的初步搜索结果（大白话：第一步粗略搜索得到的背景资料）

    # ── 规划阶段 ──
    # 大白话：planner 列的章节和 researcher 并行展开的详细资料
    sections: List[str]           # planner 规划的文章章节标题列表（大白话：文章要写哪几个章节）
    research_data: List[dict]     # 各章节的详细研究结果，由 parallel_research 并发产出（大白话：每个章节对应的详细研究资料）

    # ── 人工反馈与修订控制 ──
    # 大白话：用户反馈意见和当前是第几次改大纲了
    human_feedback: str           # 用户对规划大纲的修改意见（大白话：用户说"这里不对，改一下"）
    plan_revision_count: int      # 规划被退回修改的次数，达到上限则强制接受（大白话：大纲改了几回了，改太多就直接过）

    # ── 报告生成阶段 ──
    # 大白话：writer 和 publisher 写报告用的各种组件
    # Report layout
    title: str                    # 报告标题（大白话：文章的标题）
    headers: dict                 # 报告头部信息（大白话：报告的元信息，如作者、版本等）
    date: str                     # 报告日期（大白话：报告生成的日期）
    table_of_contents: str        # 目录（大白话：文章目录）
    introduction: str             # 引言部分（大白话：文章开头的话）
    conclusion: str               # 结论部分（大白话：文章的总结收尾）
    sources: List[str]            # 引用的来源列表（大白话：参考文献列表）
    report: str                   # 最终完整报告（大白话：最终写好的完整报告）

