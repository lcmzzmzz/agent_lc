"""
【正经注释】
Pydantic 数据验证模型模块。定义了研究子主题（Subtopic）和子主题集合（Subtopics）
的 Pydantic 数据模型，用于解析和验证 LLM 在研究规划阶段生成的子主题数据。

【大白话注释】
这个文件定义了"子主题"长什么样。大模型帮你拆研究任务的时候，
返回的数据要符合这里定义的格式，不合规的数据会被拦住。
"""

from typing import List  # 正经注释：导入列表类型 / 大白话注释：用来标注"这是一个列表"

from pydantic import BaseModel, Field  # 正经注释：导入 Pydantic 基础模型和字段定义工具 / 大白话注释：Pydantic 的两个核心工具，用来定义数据结构


class Subtopic(BaseModel):
    """
    【正经注释】
    单个研究子主题模型。表示研究任务中的一个子主题，包含任务名称或描述，
    通过 Pydantic 的 Field 约束确保任务名称至少包含一个字符。

    【大白话注释】
    一个子话题的数据结构。里面就一个字段：任务名字。
    名字不能是空的，至少得写一个字。

    Attributes:
        task: 子主题任务的名称或描述。
    """
    task: str = Field(description="Task name", min_length=1)  # 正经注释：任务名称字段，最小长度为1 / 大白话注释：任务名字，至少得有一个字


class Subtopics(BaseModel):
    """
    【正经注释】
    研究子主题集合模型。用于解析和验证 LLM 在研究规划阶段生成的子主题列表，
    确保返回的数据结构符合预期格式。

    【大白话注释】
    一堆子话题的集合。大模型帮你拆完任务后，返回的就是这种格式——
    一个列表，里面装着好几个子话题。默认是空列表。

    Attributes:
        subtopics: Subtopic 对象的列表。
    """
    subtopics: List[Subtopic] = []  # 正经注释：子主题列表，默认为空 / 大白话注释：装子话题的列表，一开始是空的
