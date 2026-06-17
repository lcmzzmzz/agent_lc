"""
【正经注释】
GPT Researcher 核心包初始化模块。
负责导出主要的 GPTResearcher 类，作为外部程序访问该库的统一入口点。

【大白话注释】
这个文件就是整个 gpt_researcher 包的"大门"。
别人想用这个库，只要 import gpt_researcher，就能拿到 GPTResearcher 这个核心类。
"""

from .agent import GPTResearcher  # 正经注释：从 agent 模块导入 GPTResearcher 核心类 / 大白话注释：把真正的"研究员"类引进来

__all__ = ['GPTResearcher']  # 正经注释：定义模块的公开导出列表，限制 from package import * 的范围 / 大白话注释：告诉别人"我这个包只暴露这一个类"