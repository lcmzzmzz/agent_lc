"""
子工作流（草稿审阅循环）状态定义。

【正经注释】
此模块定义了 DraftState，用于 EditorAgent 内部的 "researcher → reviewer → reviser"
循环子工作流。与研究大纲规划相关的底层工作流不同（使用 ResearchState），
此状态专注于单个章节的"研究→审阅→修改"迭代过程，
直到 reviewer 返回 None（审核通过）才结束循环。

【大白话注释】
这个文件定义的是"子流程"的共享记事本，专门给"写一个章节→审稿→修改"这个小循环用的。
跟外面那个顶层流程的记事本（ResearchState）是两套，各记各的。
"""
from typing import TypedDict, List, Annotated
import operator


class DraftState(TypedDict):
    """
    单章节草稿的审阅循环状态。

    【正经注释】
    对应 EditorAgent._create_workflow() 中定义的 DraftState 图。
    字段生命周期：researcher 写入 draft → reviewer 读取后写入 review →
    若 review 不为 None 则 reviser 修改后写入 revision_notes 并更新 draft →
    reviewer 重新审阅，直至 review 为 None 时结束。

    【大白话注释】
    每个章节都有自己的"小本本"：
    researcher 先写草稿 → reviewer 看完了写意见 →
    如果有问题 reviser 改完写修改记录 → reviewer 再审 → 直到通过。
    """

    task: dict              # 原始任务配置，包含 query、model、guidelines 等
                            # （大白话：这个章节的研究任务要求）

    topic: str              # 当前正在研究的章节主题
                            # （大白话：这一章要写什么主题）

    draft: dict             # researcher 产出的研究草稿内容
                            # （大白话：这一章写的草稿）

    review: str             # reviewer 的审阅意见，None 代表通过，有内容代表要修改
                            # （大白话：审稿意见，空=通过，有内容=要改）

    revision_notes: str     # reviser 修改时记录的修改说明
                            # （大白话：改了什么内容的记录，下一轮审阅时会参考）