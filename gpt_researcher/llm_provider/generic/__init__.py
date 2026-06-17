"""通用LLM提供者子包。        # 正经注释：通用LLM提供者子包初始化模块 / 大白话注释：这个文件把通用的AI模型适配器导出去，让别人能用"""
from .base import GenericLLMProvider                                          # 正经注释：从base模块导入GenericLLMProvider类 / 大白话注释：把那个万能AI模型适配器导进来

__all__ = ["GenericLLMProvider"]                                              # 正经注释：模块公开接口列表 / 大白话注释：告诉别人这个包里有什么好东西可以用
