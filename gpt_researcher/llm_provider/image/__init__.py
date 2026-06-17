"""GPT Researcher 的图像生成提供者模块。        # 正经注释：图像生成提供者子包初始化模块 / 大白话注释：这个文件把画图相关的类导出去，让别人能用"""

from .image_generator import ImageGeneratorProvider                           # 正经注释：从image_generator模块导入谷歌AI画图提供者 / 大白话注释：把谷歌画图的类导进来
from .modelslab_image_generator import ModelsLabImageGeneratorProvider        # 正经注释：从modelslab_image_generator模块导入ModelsLab画图提供者 / 大白话注释：把ModelsLab画图的类导进来

__all__ = ["ImageGeneratorProvider", "ModelsLabImageGeneratorProvider"]       # 正经注释：模块公开接口列表 / 大白话注释：告诉别人这个包里有什么好东西可以用
