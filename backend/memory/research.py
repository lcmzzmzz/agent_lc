"""
【正经注释】
研究状态类型定义模块。
使用 TypedDict 定义 ResearchState 类型字典，用于在研究流程中
传递和管理研究的完整状态，包括任务定义、研究数据、报告结构及最终报告文本。

【大白话注释】
这个文件定义了一个叫 ResearchState 的"数据表格模板"。
它用来存研究的所有信息：任务是什么、初步研究结论、分了哪些章节、
最终报告的标题、目录、引言、结论、来源等等。
整个研究过程就是不断往这张表格里填数据的过程。
"""

from typing import TypedDict, List, Annotated  # 正经注释：类型提示相关模块，TypedDict 用于定义带类型约束的字典 / 大白话注释：导入类型工具，用来定义"这个字典里该有哪些字段"
import operator  # 正经注释：运算符模块，在 Annotated 类型中用于指定归约操作 / 大白话注释：导入操作符，配合类型标注使用


class ResearchState(TypedDict):
    """研究状态类型字典，用于在研究流程中传递完整的报告生成状态。

    【正经注释】
    定义研究报告生成流程中的所有状态字段，涵盖从任务定义到最终报告的
    全生命周期数据，包括研究中间结果、章节划分和报告各组成部分。

    【大白话注释】
    这个"表格模板"存的是研究报告的所有信息：
    - task: 研究任务是什么
    - initial_research: 初步研究的结果
    - sections: 报告分了哪些章节
    - research_data: 每个章节的研究数据
    - title, headers, date: 报告的基本信息
    - table_of_contents: 目录
    - introduction, conclusion: 引言和结论
    - sources: 参考来源
    - report: 最终的完整报告文本
    """

    task: dict  # 正经注释：任务定义字典，包含查询、来源类型等配置 / 大白话注释：研究任务的详情
    initial_research: str  # 正经注释：初始研究结论文本 / 大白话注释：刚开始调研得出的初步结论
    sections: List[str]  # 正经注释：报告章节标题列表 / 大白话注释：报告分了哪些章节，每个章节的标题
    research_data: List[dict]  # 正经注释：各章节的研究数据列表 / 大白话注释：每个章节搜集到的资料数据
    # Report layout
    # 正经注释：报告布局相关字段 / 大白话注释：报告的排版和结构信息
    title: str  # 正经注释：报告标题 / 大白话注释：报告的名字
    headers: dict  # 正经注释：报告请求头或元信息字典 / 大白话注释：报告的一些元数据
    date: str  # 正经注释：报告日期字符串 / 大白话注释：报告的日期
    table_of_contents: str  # 正经注释：目录内容文本 / 大白话注释：报告的目录（页）
    introduction: str  # 正经注释：引言部分文本 / 大白话注释：报告的开头介绍部分
    conclusion: str  # 正经注释：结论部分文本 / 大白话注释：报告的结尾总结部分
    sources: List[str]  # 正经注释：参考来源 URL 列表 / 大白话注释：报告参考了哪些网站/资料
    report: str  # 正经注释：最终完整报告文本 / 大白话注释：拼好的完整报告全文


