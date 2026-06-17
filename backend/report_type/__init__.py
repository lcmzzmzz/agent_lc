"""
报告类型模块（report_type）

【正经注释】
本模块是 report_type 包的初始化入口，负责导入并导出所有可用的报告类型处理器。
当前支持两种报告类型：BasicReport（基础报告）和 DetailedReport（详细报告）。
通过 __all__ 列表显式定义公共 API，方便外部模块按需导入。

【大白话注释】
这个文件就是"报告类型"这个文件夹的门口招牌，告诉外面的人：我这儿有两种报告可以选——
一种叫"基础报告"（简单粗暴搞一份），一种叫"详细报告"（拆成子话题慢慢搞）。
别的代码想用报告功能的时候，从这里 import 就行了。
"""

from .basic_report.basic_report import BasicReport  # 正经注释：从基础报告子模块导入 BasicReport 类 / 大白话注释：把"基础报告"这个工具拿过来用
from .detailed_report.detailed_report import DetailedReport  # 正经注释：从详细报告子模块导入 DetailedReport 类 / 大白话注释：把"详细报告"这个工具拿过来用

__all__ = [  # 正经注释：定义模块的公共导出列表，控制 from report_type import * 的行为 / 大白话注释：告诉外面我这儿卖啥，别乱翻
    "BasicReport",  # 正经注释：基础报告类型，用于生成单次研究的标准报告 / 大白话注释：简单版报告，一次研究出一份结果
    "DetailedReport"  # 正经注释：详细报告类型，支持子话题拆分与多步骤深度研究 / 大白话注释：豪华版报告，把大问题拆成小问题一个个研究
]