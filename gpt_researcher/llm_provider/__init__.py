"""LLM 提供者顶层包。        # 正经注释：LLM提供者顶层包初始化模块，统一导出通用LLM提供者和图像生成提供者 / 大白话注释：这个文件是AI模型和画图功能的大门，把主要的东西都导出去"""
from .generic import GenericLLMProvider                                      # 正经注释：从generic子包导入通用LLM提供者 / 大白话注释：把万能AI模型适配器导进来
from .image import ImageGeneratorProvider                                    # 正经注释：从image子包导入图像生成提供者 / 大白话注释：把谷歌AI画图工具导进来

__all__ = [                                                                   # 正经注释：模块公开接口列表 / 大白话注释：告诉别人这个包里有什么好东西
    "GenericLLMProvider",                                                     # 正经注释：通用LLM提供者 / 大白话注释：万能AI模型适配器
    "ImageGeneratorProvider",                                                 # 正经注释：图像生成提供者 / 大白话注释：AI画图工具
]                                                                             # 正经注释：公开接口列表结束 / 大白话注释：列表结束
