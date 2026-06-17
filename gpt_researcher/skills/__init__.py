"""Skills 模块
【正经注释】本模块统一导出所有研究技能组件，每个组件封装一种独立的研究能力。
【大白话注释】这个文件把所有"干活的人"的名字列出来，方便外部调用。
"""
from .context_manager import ContextManager						# 正经注释：上下文管理器 / 大白话注释：负责整理素材的"编辑"
from .researcher import ResearchConductor							# 正经注释：研究执行器 / 大白话注释：负责搜资料的"搜索员"
from .writer import ReportGenerator								# 正经注释：报告生成器 / 大白话注释：负责写报告的"写手"
from .browser import BrowserManager								# 正经注释：浏览器管理器 / 大白话注释：负责抓网页的"爬虫"
from .curator import SourceCurator								# 正经注释：来源精选器 / 大白话注释：负责挑好资料的"评审"
from .image_generator import ImageGenerator						# 正经注释：图片生成器 / 大白话注释：负责画配图的"画师"

__all__ = [														# 正经注释：模块公开接口列表 / 大白话注释：对外提供的组件清单
    'ResearchConductor',											# 正经注释：研究执行器 / 大白话注释：搜索员
    'ReportGenerator',											# 正经注释：报告生成器 / 大白话注释：写手
    'ContextManager',												# 正经注释：上下文管理器 / 大白话注释：编辑
    'BrowserManager',												# 正经注释：浏览器管理器 / 大白话注释：爬虫
    'SourceCurator',												# 正经注释：来源精选器 / 大白话注释：评审
    'ImageGenerator',												# 正经注释：图片生成器 / 大白话注释：画师
]
