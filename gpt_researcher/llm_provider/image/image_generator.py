"""GPT Researcher 的图像生成提供者。        # 正经注释：图像生成提供者模块，基于Google的Gemini/Imagen模型提供图片生成能力 / 大白话注释：这个文件负责用谷歌的AI来画图，支持免费的Gemini和收费的Imagen两种模型

本模块通过 google.genai SDK 使用 Google 的 Gemini/Imagen 模型提供图像生成能力。        # 正经注释：通过google.genai SDK调用Gemini/Imagen模型生成图片 / 大白话注释：就是调用谷歌的画图接口来生成图片

支持的模型：        # 正经注释：支持的模型列表如下 / 大白话注释：能用这些模型来画图
- Gemini 图像模型（免费层）：models/gemini-2.5-flash-image        # 正经注释：Gemini图像模型（免费） / 大白话注释：免费的Gemini画图模型
- Imagen 模型（需要付费）：imagen-4.0-generate-001        # 正经注释：Imagen模型（需付费） / 大白话注释：要花钱的Imagen画图模型
"""

import asyncio                                                                 # 正经注释：异步编程核心库 / 大白话注释：异步编程基础库
import base64                                                                  # 正经注释：Base64编解码库 / 大白话注释：用来处理Base64编码的图片数据
import hashlib                                                                 # 正经注释：哈希计算库 / 大白话注释：用来算哈希值，给图片生成唯一文件名
import os                                                                      # 正经注释：操作系统接口 / 大白话注释：跟操作系统打交道的库
import logging                                                                 # 正经注释：日志记录库 / 大白话注释：记录程序运行日志的库
from pathlib import Path                                                       # 正经注释：路径操作库 / 大白话注释：处理文件路径的库
from typing import Any, Dict, List, Optional                                   # 正经注释：类型注解工具 / 大白话注释：类型提示用的

logger = logging.getLogger(__name__)                                           # 正经注释：获取当前模块的日志记录器 / 大白话注释：创建一个日志记录器，用来记日志


class ImageGeneratorProvider:                                                  # 正经注释：基于Google Gemini/Imagen的图像生成提供者类 / 大白话注释：用谷歌AI画图的类，封装了所有画图相关的功能
    """基于 Google 的 Gemini/Imagen 模型的图像生成提供者。        # 正经注释：提供使用Google Gemini/Imagen模型生成图像的能力 / 大白话注释：这个类就是专门用谷歌AI来画图的

    属性：        # 正经注释：类的属性说明 / 大白话注释：这个类有这些重要属性
        model_name: 用于图像生成的模型名称。        # 正经注释：模型名称 / 大白话注释：用哪个AI模型来画图
        api_key: Google API 认证密钥。        # 正经注释：Google API密钥 / 大白话注释：谷歌的钥匙，证明你有权限用
        output_dir: 生成图片的保存目录。        # 正经注释：输出目录 / 大白话注释：画好的图存到哪个文件夹
    """

    # Gemini models use generate_content with inline_data response              # 正经注释：Gemini模型使用generate_content方法，响应中包含inline_data / 大白话注释：Gemini模型画图的方式是把图片直接塞在回复里
    GEMINI_IMAGE_MODELS = [                                                    # 正经注释：Gemini图像模型列表 / 大白话注释：所有Gemini画图模型的名字都在这里
        "models/gemini-2.5-flash-image",                                       # 正经注释：Gemini 2.5 Flash图像模型 / 大白话注释：Gemini 2.5的快速画图模型
        "gemini-2.5-flash-image",                                              # 正经注释：同上，不带前缀的写法 / 大白话注释：同上，另一种写法
        "gemini-2.0-flash-exp-image-generation",                               # 正经注释：Gemini 2.0 Flash实验性图像生成模型 / 大白话注释：Gemini 2.0的实验版画图模型
        "gemini-3-pro-image-preview",                                          # 正经注释：Gemini 3 Pro图像预览版 / 大白话注释：Gemini 3 Pro的画图预览版
    ]

    # Imagen models use generate_images (requires billing)                     # 正经注释：Imagen模型使用generate_images方法，需要付费 / 大白话注释：Imagen模型画图要花钱
    IMAGEN_MODELS = [                                                          # 正经注释：Imagen图像模型列表 / 大白话注释：所有Imagen画图模型的名字
        "imagen-4.0-generate-001",                                             # 正经注释：Imagen 4.0标准版 / 大白话注释：Imagen 4.0普通版
        "imagen-4.0-fast-generate-001",                                        # 正经注释：Imagen 4.0快速版 / 大白话注释：Imagen 4.0快速版，出图快但可能质量差点
        "imagen-4.0-ultra-generate-001",                                       # 正经注释：Imagen 4.0超高质量版 / 大白话注释：Imagen 4.0超清版，质量最好
    ]

    DEFAULT_MODEL = "models/gemini-2.5-flash-image"                            # 正经注释：默认使用的图像生成模型 / 大白话注释：默认用这个免费的Gemini模型画图

    def __init__(                                                               # 正经注释：初始化图像生成提供者 / 大白话注释：创建画图对象
        self,                                                                  # 正经注释：自身实例 / 大白话注释：自己
        model_name: Optional[str] = None,                                      # 正经注释：模型名称参数（可选） / 大白话注释：你要用哪个模型画图
        api_key: Optional[str] = None,                                         # 正经注释：Google API密钥（可选） / 大白话注释：你的谷歌密钥
        output_dir: str = "outputs",                                           # 正经注释：输出目录，默认为"outputs" / 大白话注释：图存到哪，默认是outputs文件夹
    ):                                                                         # 正经注释：参数列表结束 / 大白话注释：参数到这里
        """初始化 ImageGeneratorProvider。        # 正经注释：初始化图像生成提供者实例 / 大白话注释：创建画图对象时要做的事

        参数：        # 正经注释：参数说明 / 大白话注释：这些参数的意思是
            model_name: 使用的模型，默认为 models/gemini-2.5-flash-image。        # 正经注释：模型名称，默认使用Gemini 2.5 Flash / 大白话注释：用哪个模型画，默认用免费的那个
            api_key: Google API 密钥，未提供时从 GOOGLE_API_KEY 环境变量读取。        # 正经注释：API密钥，优先使用参数，其次从环境变量获取 / 大白话注释：谷歌密钥，不传的话就从环境变量里找
            output_dir: 输出基础目录（图片将保存到 output_dir/images/）。        # 正经注释：输出基础目录路径 / 大白话注释：图片存在哪个大文件夹下
        """
        self.model_name = model_name or self.DEFAULT_MODEL                     # 正经注释：设置模型名称，未指定则使用默认值 / 大白话注释：没指定模型就用默认的
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")  # 正经注释：设置API密钥，依次从参数和环境变量获取 / 大白话注释：密钥从参数里找，找不到就从环境变量找
        self.output_dir = Path(output_dir)                                     # 正经注释：将输出目录转换为Path对象 / 大白话注释：把目录路径转成Path对象，方便操作
        self._client = None                                                    # 正经注释：Google GenAI客户端实例（延迟初始化） / 大白话注释：跟谷歌通信的客户端，先不创建，等用的时候再说

        # Determine model type                                                 # 正经注释：判断模型类型 / 大白话注释：看看用的是Gemini还是Imagen
        self._is_imagen = any(m in self.model_name.lower() for m in ['imagen'])  # 正经注释：检查模型名称中是否包含"imagen" / 大白话注释：名字里有imagen的就是Imagen模型

        if not self.api_key:                                                   # 正经注释：如果未获取到API密钥 / 大白话注释：如果找不到密钥
            logger.warning(                                                    # 正经注释：记录警告日志 / 大白话注释：打个警告日志
                "No Google API key found. Set GOOGLE_API_KEY or GEMINI_API_KEY "  # 正经注释：提示未找到API密钥 / 大白话注释：告诉你没找到密钥
                "environment variable to enable image generation."              # 正经注释：提示需要设置环境变量来启用图像生成 / 大白话注释：让你设环境变量才能画图
            )                                                                  # 正经注释：日志记录完成 / 大白话注释：警告完毕

    def _ensure_client(self):                                                  # 正经注释：确保Google GenAI客户端已初始化 / 大白话注释：确保跟谷歌的连接建好了
        """确保 Google GenAI 客户端已初始化。        # 正经注释：延迟初始化Google GenAI客户端 / 大白话注释：第一次画图的时候才去连谷歌，不浪费资源"""
        if self._client is None:                                               # 正经注释：如果客户端尚未初始化 / 大白话注释：如果还没连上谷歌
            try:                                                               # 正经注释：尝试初始化客户端 / 大白话注释：试试连
                from google import genai                                       # 正经注释：导入Google GenAI库 / 大白话注释：导入谷歌的AI库
                self._client = genai.Client(api_key=self.api_key)              # 正经注释：使用API密钥创建GenAI客户端 / 大白话注释：用密钥创建跟谷歌的连接
                logger.info(f"Initialized image generation with model: {self.model_name}")  # 正经注释：记录初始化成功的日志 / 大白话注释：日志里记一下初始化成功了
            except ImportError:                                                # 正经注释：捕获导入失败异常 / 大白话注释：如果谷歌的包装不了
                raise ImportError(                                             # 正经注释：抛出导入错误 / 大白话注释：报错！
                    "google-genai package is required for image generation. "   # 正经注释：提示需要安装google-genai包 / 大白话注释：告诉你需要先装谷歌的包
                    "Install with: pip install google-genai"                    # 正经注释：提供安装命令 / 大白话注释：告诉你怎么装
                )                                                              # 正经注释：异常抛出完成 / 大白话注释：报错完毕
            except Exception as e:                                             # 正经注释：捕获其他异常 / 大白话注释：如果出其他错了
                logger.error(f"Failed to initialize image generation client: {e}")  # 正经注释：记录初始化失败日志 / 大白话注释：日志里记一下初始化失败了
                raise                                                          # 正经注释：重新抛出异常 / 大白话注释：把错误继续往上抛

    def _ensure_output_dir(self, research_id: str = "") -> Path:               # 正经注释：确保输出目录存在并返回路径 / 大白话注释：检查存图的文件夹有没有，没有就创建一个
        """确保输出目录存在并返回路径。        # 正经注释：创建图片输出目录（如果不存在）并返回路径 / 大白话注释：确保图有地方存"""
        # Use same structure as PDF/DOCX: outputs/images/{research_id}/        # 正经注释：使用与PDF/DOCX相同的目录结构 / 大白话注释：跟PDF那些用一样的目录结构
        if research_id:                                                        # 正经注释：如果指定了研究ID / 大白话注释：如果有研究任务编号的话
            output_path = self.output_dir / "images" / research_id             # 正经注释：构建带研究ID的输出路径 / 大白话注释：按研究编号建子文件夹
        else:                                                                  # 正经注释：否则 / 大白话注释：如果没有编号
            output_path = self.output_dir / "images"                           # 正经注释：使用默认输出路径 / 大白话注释：就用通用的图片文件夹
        output_path.mkdir(parents=True, exist_ok=True)                         # 正经注释：递归创建目录（如已存在不报错） / 大白话注释：文件夹不存在就创建，存在就不管
        return output_path                                                     # 正经注释：返回输出路径 / 大白话注释：把路径返回

    def _generate_image_filename(self, prompt: str, index: int = 0) -> str:    # 正经注释：根据提示词哈希生成唯一文件名 / 大白话注释：给图片起个不重复的文件名
        """根据提示词哈希值生成唯一的图片文件名。        # 正经注释：基于提示词的MD5哈希前8位生成文件名 / 大白话注释：把提示词算个哈希，取前几位当文件名，保证不重复"""
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:8]             # 正经注释：计算提示词MD5哈希并取前8位 / 大白话注释：算个哈希值取前8位
        return f"img_{prompt_hash}_{index}.png"                                # 正经注释：返回格式化的文件名 / 大白话注释：返回类似img_a1b2c3d4_0.png的文件名

    def _crop_to_landscape(self, image_bytes: bytes, target_ratio: float = 16/9) -> bytes:  # 正经注释：将图片裁剪为横版格式（默认16:9） / 大白话注释：把方形的图切成宽屏的，适合报告排版
        """将方形图片裁剪为横版格式（默认 16:9）。        # 正经注释：将图片裁剪为指定的宽高比，确保适配文章/报告布局 / 大白话注释：把方图切成宽屏的，塞到报告里好看

        确保图片适配文章/报告排版。        # 正经注释：保证图片在报告中的显示效果 / 大白话注释：让图在报告里不突兀

        参数：        # 正经注释：参数说明 / 大白话注释：这些参数是
            image_bytes: 原始图片字节数据。        # 正经注释：原始图片字节数据 / 大白话注释：图片的原始数据
            target_ratio: 目标宽高比（默认 16:9 ≈ 1.78）。        # 正经注释：目标宽高比 / 大白话注释：切成多宽的，默认是16:9宽屏

        返回：        # 正经注释：返回值说明 / 大白话注释：返回的东西是
            裁剪后的 PNG 格式图片字节数据。        # 正经注释：裁剪后的PNG格式图片字节数据 / 大白话注释：切好的图片数据
        """
        try:                                                                   # 正经注释：尝试裁剪图片 / 大白话注释：试试切图
            from PIL import Image                                              # 正经注释：导入PIL图像处理库 / 大白话注释：导入PIL图片处理库
            import io                                                          # 正经注释：导入字节流操作库 / 大白话注释：导入io库

            # Open the image                                                   # 正经注释：打开图片 / 大白话注释：把图片打开
            img = Image.open(io.BytesIO(image_bytes))                          # 正经注释：从字节数据加载图片 / 大白话注释：把字节数据变成图片对象
            width, height = img.size                                           # 正经注释：获取图片宽高 / 大白话注释：看看图片多宽多高

            # If already landscape or wider, return as-is                      # 正经注释：如果已经是横版或更宽，直接返回原数据 / 大白话注释：如果图已经够宽了就不用切
            if width / height >= target_ratio:                                 # 正经注释：检查宽高比是否已达目标 / 大白话注释：够宽了
                return image_bytes                                             # 正经注释：返回原始图片数据 / 大白话注释：原图直接返回

            # Calculate new dimensions for landscape crop                      # 正经注释：计算横版裁剪的新尺寸 / 大白话注释：算算要切多大
            # Keep full width, reduce height                                   # 正经注释：保持全宽，减少高度 / 大白话注释：宽度不变，把高度缩小
            new_height = int(width / target_ratio)                             # 正经注释：根据目标比例计算新高度 / 大白话注释：按比例算新高度

            # Center crop vertically                                           # 正经注释：垂直居中裁剪 / 大白话注释：从中间切，上下各砍掉一点
            top = (height - new_height) // 2                                   # 正经注释：计算裁剪顶部位置 / 大白话注释：算上面切掉多少
            bottom = top + new_height                                          # 正经注释：计算裁剪底部位置 / 大白话注释：算下面切到哪里

            # Crop the image                                                   # 正经注释：执行裁剪 / 大白话注释：下刀切图
            cropped = img.crop((0, top, width, bottom))                        # 正经注释：按计算的区域裁剪图片 / 大白话注释：把图切成宽屏的

            # Save to bytes                                                    # 正经注释：将裁剪结果保存为字节数据 / 大白话注释：把切好的图变成数据
            output = io.BytesIO()                                              # 正经注释：创建字节流缓冲区 / 大白话注释：开个内存空间存图
            cropped.save(output, format='PNG', optimize=True)                  # 正经注释：以PNG格式优化保存 / 大白话注释：存成PNG格式
            output.seek(0)                                                     # 正经注释：将缓冲区指针重置到开头 / 大白话注释：把指针挪回开头

            logger.info(f"Cropped image from {width}x{height} to {width}x{new_height} (landscape)")  # 正经注释：记录裁剪信息日志 / 大白话注释：日志记一下切了多少
            return output.getvalue()                                           # 正经注释：返回裁剪后的字节数据 / 大白话注释：把切好的图数据返回

        except ImportError:                                                    # 正经注释：捕获PIL未安装异常 / 大白话注释：如果PIL包装不了
            logger.warning("PIL not available for image cropping, returning original")  # 正经注释：记录警告，返回原始图片 / 大白话注释：切不了就算了，返回原图
            return image_bytes                                                 # 正经注释：返回原始图片数据 / 大白话注释：原图给你
        except Exception as e:                                                 # 正经注释：捕获其他异常 / 大白话注释：如果出其他错了
            logger.warning(f"Failed to crop image to landscape: {e}")          # 正经注释：记录裁剪失败警告 / 大白话注释：日志记一下切图失败了
            return image_bytes                                                 # 正经注释：返回原始图片数据 / 大白话注释：出错了就返回原图

    def _build_enhanced_prompt(self, prompt: str, context: str = "", style: str = "dark") -> str:  # 正经注释：构建增强版提示词，添加明确的样式指令 / 大白话注释：把简单的提示词加工一下，告诉AI要画成什么样
        """构建带有明确样式指令的增强提示词。        # 正经注释：根据基础提示词、研究上下文和样式风格生成增强版提示词 / 大白话注释：给提示词加点料，让AI画得更好看

        参数：        # 正经注释：参数说明 / 大白话注释：这些参数是
            prompt: 基础图像提示词。        # 正经注释：基础图像生成提示词 / 大白话注释：你想要画啥
            context: 研究相关的额外上下文信息。        # 正经注释：来自研究的额外上下文 / 大白话注释：研究内容的背景信息
            style: 图像风格 - "dark"（匹配应用主题）、"light" 或 "auto"。        # 正经注释：图像样式风格 / 大白话注释：要什么风格，暗色/亮色/自动

        返回：        # 正经注释：返回值说明 / 大白话注释：返回的东西是
            带有样式指令的增强提示词字符串。        # 正经注释：包含样式指令的增强提示词 / 大白话注释：加工好的提示词
        """
        # Style-specific color palettes                                        # 正经注释：根据样式选择对应的色彩方案 / 大白话注释：根据你要的风格选颜色
        if style == "dark":                                                    # 正经注释：暗色模式 / 大白话注释：如果是暗色风格
            # Dark mode matching the GPT Researcher app theme                  # 正经注释：暗色模式匹配GPT Researcher应用主题 / 大白话注释：暗色模式跟应用界面一个风格
            style_instructions = """                                           # 正经注释：暗色模式样式指令 / 大白话注释：暗色模式的具体要求
STYLE REQUIREMENTS - DARK MODE THEME:                                          # 正经注释：暗色模式主题样式要求 / 大白话注释：暗色模式的要求如下
- Dark background (#0d1117 or similar deep charcoal/navy)                      # 正经注释：深色背景 / 大白话注释：深色背景，像深灰或深蓝那种
- Primary accent color: Teal/Cyan (#14b8a6, #0d9488)                          # 正经注释：主色调为青色 / 大白话注释：主要的颜色是青色
- Secondary colors: Slate grays (#374151, #4b5563), subtle purple accents      # 正经注释：辅助色为灰蓝色，点缀紫色 / 大白话注释：次要颜色是灰色，再加点紫色
- Glowing, neon-like effects for highlights and important elements             # 正经注释：高亮元素使用发光霓虹效果 / 大白话注释：重要的东西要发光
- Modern, tech-forward, futuristic aesthetic                                   # 正经注释：现代科技感美学 / 大白话注释：要有未来科技感
- Clean lines with subtle gradients                                            # 正经注释：简洁线条配合微妙渐变 / 大白话注释：线条干净，颜色过渡自然
- High contrast elements that pop against dark background                      # 正经注释：高对比度元素突出于暗色背景 / 大白话注释：该显眼的地方要显眼
- Sleek, minimalist design with visual depth                                   # 正经注释：简约设计但有视觉深度 / 大白话注释：简约但不简单
- Icons and diagrams with luminous teal outlines                               # 正经注释：图标和图表使用发光青色轮廓 / 大白话注释：图标要用发光的青色边框
- Professional infographic style suitable for tech/research context"""         # 正经注释：适合技术/研究场景的专业信息图表风格 / 大白话注释：要像专业的研究图表
        elif style == "light":                                                 # 正经注释：亮色模式 / 大白话注释：如果是亮色风格
            style_instructions = """                                           # 正经注释：亮色模式样式指令 / 大白话注释：亮色模式的具体要求
STYLE REQUIREMENTS - LIGHT MODE:                                               # 正经注释：亮色模式样式要求 / 大白话注释：亮色模式的要求如下
- Clean white or light gray background                                         # 正经注释：干净的白色或浅灰色背景 / 大白话注释：白底或浅灰底
- Primary colors: Deep blue (#1e40af), teal (#0d9488)                          # 正经注释：主色调为深蓝色和青色 / 大白话注释：主要颜色是深蓝和青色
- Professional, corporate aesthetic                                            # 正经注释：专业企业美学 / 大白话注释：商务风
- Subtle shadows for depth                                                     # 正经注释：使用细微阴影增加深度 / 大白话注释：加点阴影显得有层次
- High readability with dark text elements                                     # 正经注释：深色文字确保高可读性 / 大白话注释：文字要清楚好认
- Modern flat design with occasional gradients"""                              # 正经注释：现代扁平化设计，偶有渐变 / 大白话注释：扁平化设计，偶尔加点渐变
        else:                                                                  # 正经注释：自动/默认模式 / 大白话注释：其他情况就用通用风格
            style_instructions = """                                           # 正经注释：通用样式指令 / 大白话注释：通用风格的要求
STYLE REQUIREMENTS - PROFESSIONAL:                                             # 正经注释：专业模式样式要求 / 大白话注释：专业风格要求如下
- Sophisticated color palette (teals, blues, grays)                            # 正经注释：精致的配色方案 / 大白话注释：用青色蓝色灰色这种高级配色
- Clean, modern design                                                         # 正经注释：简洁现代的设计 / 大白话注释：简洁大方
- High contrast for readability                                                # 正经注释：高对比度确保可读性 / 大白话注释：对比要强，看得清楚
- Professional infographic style"""                                            # 正经注释：专业信息图表风格 / 大白话注释：像专业图表那样

        styled_prompt = f"""Create a professional, high-quality illustration for a research report.  # 正经注释：构建带有样式要求的完整提示词 / 大白话注释：把所有要求拼在一起，告诉AI要画啥

SUBJECT: {prompt}                                                              # 正经注释：图片主题 / 大白话注释：你要画的主题

{style_instructions}                                                           # 正经注释：样式指令 / 大白话注释：上面选的风格要求

TECHNICAL REQUIREMENTS:                                                        # 正经注释：技术要求 / 大白话注释：技术上的要求
- No text, labels, or watermarks in the image                                  # 正经注释：图片中不含文字、标签或水印 / 大白话注释：图里不要有字
- Clear visual hierarchy                                                       # 正经注释：清晰的视觉层级 / 大白话注释：要有主次分明
- Well-balanced composition                                                     # 正经注释：均衡的构图 / 大白话注释：构图要匀称
- Suitable for both digital viewing and printing                               # 正经注释：适合数字浏览和打印 / 大白话注释：屏幕上看和打印出来都要好看
- Vector-style or clean photorealistic rendering                               # 正经注释：矢量风格或干净的照片级渲染 / 大白话注释：画得要精致
- Resolution and detail appropriate for report embedding                       # 正经注释：分辨率和细节适合嵌入报告 / 大白话注释：画质要够塞进报告里

AVOID:                                                                         # 正经注释：避免的内容 / 大白话注释：不要画这些
- Cartoonish or childish styles                                                # 正经注释：避免卡通或幼稚风格 / 大白话注释：不要画成卡通
- Cluttered or busy designs                                                    # 正经注释：避免杂乱或过于复杂的设计 / 大白话注释：不要太花哨
- Bright white backgrounds (for dark mode)                                     # 正经注释：避免亮白背景（暗色模式下） / 大白话注释：暗色模式不要白底
- Low quality or pixelated elements                                            # 正经注释：避免低质量或像素化元素 / 大白话注释：不要画糊了
- Generic stock photo aesthetics"""                                            # 正经注释：避免通用素材照风格 / 大白话注释：不要像网上找的通用素材图

        if context:                                                            # 正经注释：如果提供了研究上下文 / 大白话注释：如果有背景信息的话
            styled_prompt += f"\n\nRESEARCH CONTEXT: {context[:300]}"          # 正经注释：附加研究上下文（最多300字符） / 大白话注释：把背景信息也加上，但不要太长

        return styled_prompt                                                   # 正经注释：返回增强后的提示词 / 大白话注释：把加工好的提示词返回

    async def generate_image(                                                  # 正经注释：异步生成图片方法 / 大白话注释：异步画图，这是主要的画图方法
        self,                                                                  # 正经注释：自身实例 / 大白话注释：自己
        prompt: str,                                                           # 正经注释：图像生成提示词 / 大白话注释：你要画啥
        context: str = "",                                                     # 正经注释：研究上下文（可选） / 大白话注释：背景信息
        research_id: str = "",                                                 # 正经注释：研究任务ID（可选） / 大白话注释：研究任务编号
        aspect_ratio: str = "1:1",                                             # 正经注释：图片宽高比（仅Imagen支持） / 大白话注释：图的比例，只有Imagen能用
        num_images: int = 1,                                                   # 正经注释：生成图片数量 / 大白话注释：画几张
        style: str = "dark",                                                   # 正经注释：图片样式风格 / 大白话注释：什么风格
    ) -> List[Dict[str, Any]]:                                                 # 正经注释：返回图片信息字典列表 / 大白话注释：返回每张图的信息
        """根据提示词和可选上下文生成图片。        # 正经注释：基于提示词和可选上下文生成图片，返回图片信息列表 / 大白话注释：根据你的描述来画图，返回图的信息

        参数：        # 正经注释：参数说明 / 大白话注释：这些参数是
            prompt: 图像生成提示词。        # 正经注释：图像生成提示词 / 大白话注释：你想画什么
            context: 用于提高图片相关性的额外上下文。        # 正经注释：改善图片相关性的额外上下文 / 大白话注释：背景信息，帮助AI画得更贴切
            research_id: 用于组织输出的研究ID。        # 正经注释：用于组织输出目录的研究ID / 大白话注释：研究编号，用来分文件夹存图
            aspect_ratio: 图片宽高比（仅Imagen模型支持）。        # 正经注释：图片宽高比 / 大白话注释：图片长宽比例
            num_images: 生成图片的数量。        # 正经注释：生成图片数量 / 大白话注释：画几张
            style: 图像风格 - "dark"、"light" 或 "auto"。        # 正经注释：图像样式风格 / 大白话注释：什么风格

        返回：        # 正经注释：返回值说明 / 大白话注释：返回的东西是
            包含图片信息（含绝对路径）的字典列表。        # 正经注释：包含图片信息的字典列表 / 大白话注释：每张图的信息列表
        """
        if not self.api_key:                                                   # 正经注释：如果未配置API密钥 / 大白话注释：如果没有密钥
            logger.warning("No API key configured for image generation")       # 正经注释：记录警告日志 / 大白话注释：打个警告
            return []                                                          # 正经注释：返回空列表 / 大白话注释：画不了，返回空的

        self._ensure_client()                                                  # 正经注释：确保客户端已初始化 / 大白话注释：确保跟谷歌连上了
        output_path = self._ensure_output_dir(research_id)                     # 正经注释：确保输出目录存在 / 大白话注释：确保存图的文件夹有了

        # Build enhanced prompt with styling                                   # 正经注释：构建带样式的增强提示词 / 大白话注释：加工提示词
        logger.info(f"Building image prompt with style: {style}")              # 正经注释：记录提示词构建日志 / 大白话注释：日志记一下在构建提示词
        full_prompt = self._build_enhanced_prompt(prompt, context, style)      # 正经注释：生成增强版提示词 / 大白话注释：把提示词加工一下
        logger.debug(f"Full prompt (first 500 chars): {full_prompt[:500]}")    # 正经注释：记录提示词前500字符的调试日志 / 大白话注释：调试用的，看看提示词长啥样

        try:                                                                   # 正经注释：尝试生成图片 / 大白话注释：试试画图
            if self._is_imagen:                                                # 正经注释：如果使用Imagen模型 / 大白话注释：如果是Imagen模型
                return await self._generate_with_imagen(full_prompt, output_path, num_images, aspect_ratio, research_id)  # 正经注释：使用Imagen方式生成 / 大白话注释：用Imagen画法画
            else:                                                              # 正经注释：否则使用Gemini模型 / 大白话注释：如果是Gemini模型
                return await self._generate_with_gemini(full_prompt, output_path, num_images, research_id, prompt)  # 正经注释：使用Gemini方式生成 / 大白话注释：用Gemini画法画
        except Exception as e:                                                 # 正经注释：捕获生成过程中的异常 / 大白话注释：如果画图出错了
            logger.error(f"Image generation failed: {e}", exc_info=True)       # 正经注释：记录生成失败日志 / 大白话注释：日志记一下画图失败了
            return []                                                          # 正经注释：返回空列表 / 大白话注释：画不了就返回空的

    async def _generate_with_gemini(                                           # 正经注释：使用Gemini模型生成图片的内部方法 / 大白话注释：用Gemini模型画图的内部方法
        self,                                                                  # 正经注释：自身实例 / 大白话注释：自己
        full_prompt: str,                                                      # 正经注释：增强版提示词 / 大白话注释：加工过的提示词
        output_path: Path,                                                     # 正经注释：输出目录路径 / 大白话注释：存图的文件夹
        num_images: int,                                                       # 正经注释：图片数量 / 大白话注释：画几张
        research_id: str,                                                      # 正经注释：研究任务ID / 大白话注释：研究编号
        original_prompt: str,                                                  # 正经注释：原始提示词 / 大白话注释：最初的提示词
    ) -> List[Dict[str, Any]]:                                                 # 正经注释：返回图片信息字典列表 / 大白话注释：返回图片信息
        """使用 Gemini 模型通过 generate_content 生成图片。        # 正经注释：通过Gemini的generate_content接口生成图片 / 大白话注释：用Gemini的方式画图"""
        generated_images = []                                                  # 正经注释：已生成图片列表 / 大白话注释：存画好的图的信息

        for i in range(num_images):                                            # 正经注释：循环生成指定数量的图片 / 大白话注释：一张一张地画
            try:                                                               # 正经注释：尝试生成单张图片 / 大白话注释：试试画这张
                # Gemini image models use generate_content                     # 正经注释：Gemini图像模型使用generate_content方法 / 大白话注释：Gemini用这个方法来画图
                response = await asyncio.to_thread(                            # 正经注释：在线程池中异步调用同步方法 / 大白话注释：把同步调用变成异步的
                    self._client.models.generate_content,                       # 正经注释：调用generate_content生成内容 / 大白话注释：调用谷歌的画图接口
                    model=self.model_name,                                     # 正经注释：指定模型名称 / 大白话注释：用哪个模型
                    contents=full_prompt,                                      # 正经注释：传入增强版提示词 / 大白话注释：把提示词发过去
                )                                                              # 正经注释：generate_content调用完成 / 大白话注释：画完了

                # Debug: Log response structure                                # 正经注释：调试：记录响应结构 / 大白话注释：调试用的，看看返回的数据长啥样
                if response.candidates:                                        # 正经注释：如果响应中有候选结果 / 大白话注释：如果有返回结果的话
                    candidate = response.candidates[0]                         # 正经注释：获取第一个候选结果 / 大白话注释：取第一个结果
                    if candidate.content and candidate.content.parts:          # 正经注释：如果候选结果有内容和部件 / 大白话注释：如果结果里有东西
                        logger.debug(f"Response has {len(candidate.content.parts)} parts")  # 正经注释：记录部件数量 / 大白话注释：日志记一下有几个部件
                        for idx, part in enumerate(candidate.content.parts):   # 正经注释：遍历所有部件 / 大白话注释：一个一个看
                            has_inline = hasattr(part, 'inline_data') and part.inline_data  # 正经注释：检查是否有内联图片数据 / 大白话注释：看看有没有图片数据
                            has_text = hasattr(part, 'text') and part.text     # 正经注释：检查是否有文本数据 / 大白话注释：看看有没有文字
                            logger.debug(f"Part {idx}: inline_data={has_inline}, text={has_text}")  # 正经注释：记录部件类型调试信息 / 大白话注释：日志记一下每个部件是什么

                # Extract image from response parts                            # 正经注释：从响应部件中提取图片 / 大白话注释：从返回结果里把图片数据扒出来
                if response.candidates and response.candidates[0].content.parts:  # 正经注释：如果响应中有候选结果和部件 / 大白话注释：如果有返回结果
                    for part in response.candidates[0].content.parts:          # 正经注释：遍历所有部件 / 大白话注释：一个一个看
                        if hasattr(part, 'inline_data') and part.inline_data:  # 正经注释：如果部件包含内联图片数据 / 大白话注释：如果这个部件是图片
                            # Found image data                                 # 正经注释：找到图片数据 / 大白话注释：找到图片了！
                            image_data = part.inline_data.data                 # 正经注释：获取图片原始数据 / 大白话注释：把图片数据拿出来
                            mime_type = getattr(part.inline_data, 'mime_type', 'image/png')  # 正经注释：获取MIME类型，默认为PNG / 大白话注释：看看图片是什么格式

                            # Determine file extension                         # 正经注释：确定文件扩展名 / 大白话注释：决定文件后缀名
                            ext = 'png' if 'png' in mime_type else 'jpg'       # 正经注释：根据MIME类型判断扩展名 / 大白话注释：是png就png，否则jpg
                            filename = self._generate_image_filename(original_prompt, i)  # 正经注释：生成文件名 / 大白话注释：给图片起个名字
                            filepath = output_path / filename                  # 正经注释：拼接完整文件路径 / 大白话注释：完整路径

                            # Write image data (may be base64 encoded)         # 正经注释：写入图片数据（可能是Base64编码的） / 大白话注释：把图片数据存到文件里
                            if isinstance(image_data, str):                    # 正经注释：如果数据是字符串类型 / 大白话注释：如果是文本格式
                                image_bytes = base64.b64decode(image_data)     # 正经注释：进行Base64解码 / 大白话注释：先解码成真正的图片数据
                            else:                                              # 正经注释：否则 / 大白话注释：如果已经是二进制了
                                image_bytes = image_data                       # 正经注释：直接使用原始数据 / 大白话注释：直接用

                            # Note: Keeping original square format from Gemini  # 正经注释：保留Gemini原始方形格式 / 大白话注释：保留原图不裁剪
                            # To enable landscape cropping, uncomment:          # 正经注释：如需启用横版裁剪，取消注释 / 大白话注释：想切宽屏就把下面这行取消注释
                            # image_bytes = self._crop_to_landscape(image_bytes)  # 正经注释：裁剪为横版 / 大白话注释：切图

                            with open(filepath, 'wb') as f:                    # 正经注释：以二进制写模式打开文件 / 大白话注释：打开文件准备写
                                f.write(image_bytes)                           # 正经注释：写入图片字节数据 / 大白话注释：把图片数据写进去

                            # Use both absolute path (for PDF) and web URL (for frontend)  # 正经注释：同时使用绝对路径（供PDF使用）和Web URL（供前端使用） / 大白话注释：两种路径都存，PDF用绝对路径，网页用相对路径
                            absolute_path = filepath.resolve()                 # 正经注释：获取绝对路径 / 大白话注释：完整路径
                            web_url = f"/outputs/images/{research_id}/{filename}" if research_id else f"/outputs/images/{filename}"  # 正经注释：构建Web URL / 大白话注释：网页上访问的路径

                            generated_images.append({                          # 正经注释：将图片信息添加到列表 / 大白话注释：把这张图的信息记下来
                                "path": str(absolute_path),  # Absolute path for PDF generation  # 正经注释：绝对路径（用于PDF生成） / 大白话注释：给PDF用的完整路径
                                "url": web_url,  # Web URL for frontend display  # 正经注释：Web URL（用于前端显示） / 大白话注释：给网页用的路径
                                "absolute_url": str(absolute_path),  # For PDF compatibility  # 正经注释：绝对URL（用于PDF兼容） / 大白话注释：也是给PDF用的
                                "prompt": original_prompt,                     # 正经注释：原始提示词 / 大白话注释：最初的提示词
                                "alt_text": self._generate_alt_text(original_prompt),  # 正经注释：无障碍替代文本 / 大白话注释：图片描述文字
                            })                                                 # 正经注释：图片信息添加完成 / 大白话注释：记好了

                            logger.info(f"Generated image saved to: {filepath}")  # 正经注释：记录图片保存成功日志 / 大白话注释：日志记一下图存好了
                            break  # Only take first image per iteration        # 正经注释：每次迭代只取第一张图 / 大白话注释：只要一张图就够了
                    else:                                                      # 正经注释：如果没有找到内联图片数据 / 大白话注释：没找到图片数据
                        # No inline_data found - check if there's text (model refused)  # 正经注释：检查是否返回了文本（模型可能拒绝了生成） / 大白话注释：看看模型是不是拒绝画了，只给了文字
                        for part in response.candidates[0].content.parts:      # 正经注释：遍历部件查找文本 / 大白话注释：看看有没有文字内容
                            if hasattr(part, 'text') and part.text:            # 正经注释：如果部件包含文本 / 大白话注释：如果有文字
                                logger.warning(f"Model returned text instead of image: {part.text[:200]}")  # 正经注释：记录模型返回文本而非图片的警告 / 大白话注释：模型不画图只给了文字，打个警告
                                break                                          # 正经注释：跳出循环 / 大白话注释：不用再找了

            except Exception as e:                                             # 正经注释：捕获生成单张图片的异常 / 大白话注释：画这张图出错了
                logger.error(f"Error generating image {i}: {e}", exc_info=True)  # 正经注释：记录错误日志 / 大白话注释：日志记一下出错了
                continue                                                       # 正经注释：继续生成下一张 / 大白话注释：这张画不了就算了，画下一张

        return generated_images                                                # 正经注释：返回生成的图片列表 / 大白话注释：把画好的图的信息返回

    async def _generate_with_imagen(                                           # 正经注释：使用Imagen模型生成图片的内部方法 / 大白话注释：用Imagen模型画图的内部方法
        self,                                                                  # 正经注释：自身实例 / 大白话注释：自己
        full_prompt: str,                                                      # 正经注释：增强版提示词 / 大白话注释：加工过的提示词
        output_path: Path,                                                     # 正经注释：输出目录路径 / 大白话注释：存图的文件夹
        num_images: int,                                                       # 正经注释：图片数量 / 大白话注释：画几张
        aspect_ratio: str,                                                     # 正经注释：图片宽高比 / 大白话注释：图片长宽比例
        research_id: str,                                                      # 正经注释：研究任务ID / 大白话注释：研究编号
    ) -> List[Dict[str, Any]]:                                                 # 正经注释：返回图片信息字典列表 / 大白话注释：返回图片信息
        """使用 Imagen 模型通过 generate_images 生成图片。        # 正经注释：通过Imagen的generate_images接口生成图片 / 大白话注释：用Imagen的方式画图"""
        from google.genai import types                                         # 正经注释：导入Google GenAI类型定义 / 大白话注释：导入谷歌AI的类型定义

        generated_images = []                                                  # 正经注释：已生成图片列表 / 大白话注释：存画好的图的信息

        try:                                                                   # 正经注释：尝试生成图片 / 大白话注释：试试画图
            response = await asyncio.to_thread(                                # 正经注释：在线程池中异步调用同步方法 / 大白话注释：把同步调用变成异步的
                self._client.models.generate_images,                           # 正经注释：调用generate_images生成图片 / 大白话注释：调用Imagen的画图接口
                model=self.model_name,                                         # 正经注释：指定模型名称 / 大白话注释：用哪个模型
                prompt=full_prompt,                                            # 正经注释：传入增强版提示词 / 大白话注释：把提示词发过去
                config=types.GenerateImagesConfig(                             # 正经注释：配置生成参数 / 大白话注释：画图的配置
                    number_of_images=num_images,                               # 正经注释：生成图片数量 / 大白话注释：画几张
                    aspect_ratio=aspect_ratio,                                 # 正经注释：图片宽高比 / 大白话注释：图片比例
                ),                                                             # 正经注释：配置完成 / 大白话注释：配置好了
            )                                                                  # 正经注释：generate_images调用完成 / 大白话注释：画完了

            if response and response.generated_images:                         # 正经注释：如果响应中包含生成的图片 / 大白话注释：如果画出来了
                for i, gen_image in enumerate(response.generated_images):      # 正经注释：遍历所有生成的图片 / 大白话注释：一张一张处理
                    filename = self._generate_image_filename(full_prompt, i)   # 正经注释：生成文件名 / 大白话注释：给图片起个名字
                    filepath = output_path / filename                          # 正经注释：拼接完整文件路径 / 大白话注释：完整路径

                    # Extract image bytes                                      # 正经注释：提取图片字节数据 / 大白话注释：把图片数据拿出来
                    if hasattr(gen_image, 'image') and hasattr(gen_image.image, 'image_bytes'):  # 正经注释：从嵌套结构中提取 / 大白话注释：从嵌套的结构里取
                        image_bytes = gen_image.image.image_bytes              # 正经注释：获取image_bytes属性 / 大白话注释：把图片数据拿出来
                    elif hasattr(gen_image, 'image_bytes'):                    # 正经注释：从直接属性中提取 / 大白话注释：直接取image_bytes属性
                        image_bytes = gen_image.image_bytes                    # 正经注释：获取image_bytes属性 / 大白话注释：拿到了
                    else:                                                      # 正经注释：无法提取图片数据 / 大白话注释：取不出来
                        logger.warning("Could not extract image bytes")        # 正经注释：记录警告 / 大白话注释：打个警告
                        continue                                               # 正经注释：跳过此图片 / 大白话注释：跳过，处理下一张

                    with open(filepath, 'wb') as f:                            # 正经注释：以二进制写模式打开文件 / 大白话注释：打开文件准备写
                        f.write(image_bytes)                                   # 正经注释：写入图片字节数据 / 大白话注释：把图片数据写进去

                    # Use both absolute path (for PDF) and web URL (for frontend)  # 正经注释：同时保存绝对路径和Web URL / 大白话注释：两种路径都存
                    absolute_path = filepath.resolve()                         # 正经注释：获取绝对路径 / 大白话注释：完整路径
                    web_url = f"/outputs/images/{research_id}/{filename}" if research_id else f"/outputs/images/{filename}"  # 正经注释：构建Web URL / 大白话注释：网页路径

                    generated_images.append({                                  # 正经注释：将图片信息添加到列表 / 大白话注释：把图的信息记下来
                        "path": str(absolute_path),                            # 正经注释：绝对路径 / 大白话注释：完整路径
                        "url": web_url,                                        # 正经注释：Web URL / 大白话注释：网页路径
                        "absolute_url": str(absolute_path),                    # 正经注释：绝对URL / 大白话注释：也是完整路径
                        "prompt": full_prompt,                                 # 正经注释：增强版提示词 / 大白话注释：用过的提示词
                        "alt_text": self._generate_alt_text(full_prompt),      # 正经注释：无障碍替代文本 / 大白话注释：图片描述
                    })                                                         # 正经注释：图片信息添加完成 / 大白话注释：记好了

                    logger.info(f"Generated image saved to: {filepath}")       # 正经注释：记录图片保存成功日志 / 大白话注释：日志记一下图存好了

        except Exception as e:                                                 # 正经注释：捕获Imagen生成异常 / 大白话注释：画图出错了
            logger.error(f"Imagen generation failed: {e}", exc_info=True)      # 正经注释：记录生成失败日志 / 大白话注释：日志记一下失败了

        return generated_images                                                # 正经注释：返回生成的图片列表 / 大白话注释：把图的信息返回

    def _generate_alt_text(self, prompt: str) -> str:                          # 正经注释：根据提示词生成无障碍替代文本 / 大白话注释：给图片写个简短描述
        """根据提示词生成无障碍替代文本。        # 正经注释：从提示词生成简洁的无障碍图片描述 / 大白话注释：给图片写个一句话描述，方便视障用户"""
        # Clean and truncate for alt text                                      # 正经注释：清理并截断用于替代文本 / 大白话注释：把提示词清理一下，太长就截断
        clean_prompt = prompt.replace('\n', ' ').strip()                       # 正经注释：去除换行并清理空白 / 大白话注释：去掉换行和多余空格
        # Extract just the core subject                                        # 正经注释：仅提取核心主题 / 大白话注释：只保留核心内容
        if len(clean_prompt) > 120:                                            # 正经注释：如果超过120个字符 / 大白话注释：太长了
            clean_prompt = clean_prompt[:117] + "..."                          # 正经注释：截断并添加省略号 / 大白话注释：截短加省略号
        return f"Illustration: {clean_prompt}"                                 # 正经注释：返回带前缀的替代文本 / 大白话注释：返回"插图：xxx"格式的描述

    def is_available(self) -> bool:                                            # 正经注释：检查图像生成功能是否可用 / 大白话注释：看看能不能画图
        """检查图像生成功能是否可用。        # 正经注释：验证API密钥和客户端是否就绪 / 大白话注释：检查一下密钥有没有、能不能连上谷歌"""
        if not self.api_key:                                                   # 正经注释：如果没有API密钥 / 大白话注释：没有密钥
            return False                                                       # 正经注释：不可用 / 大白话注释：画不了
        try:                                                                   # 正经注释：尝试初始化客户端 / 大白话注释：试试能不能连上
            self._ensure_client()                                              # 正经注释：确保客户端初始化 / 大白话注释：连接一下试试
            return True                                                        # 正经注释：可用 / 大白话注释：可以画图
        except Exception as e:                                                 # 正经注释：捕获初始化异常 / 大白话注释：连不上
            logger.warning(f"Image generation not available: {e}")             # 正经注释：记录不可用警告 / 大白话注释：打个警告
            return False                                                       # 正经注释：不可用 / 大白话注释：画不了

    @classmethod                                                               # 正经注释：类方法装饰器 / 大白话注释：不用创建对象就能调用的方法
    def from_config(cls, config) -> Optional["ImageGeneratorProvider"]:        # 正经注释：从配置对象创建ImageGeneratorProvider实例 / 大白话注释：从配置文件里读参数来创建画图对象
        """从 Config 对象创建 ImageGeneratorProvider。        # 正经注释：根据Config对象的配置创建图像生成提供者实例 / 大白话注释：用配置文件创建画图对象"""
        model = getattr(config, 'image_generation_model', None)                # 正经注释：从配置中获取图像生成模型名称 / 大白话注释：读配置里用的是哪个模型
        enabled = getattr(config, 'image_generation_enabled', False)           # 正经注释：从配置中获取是否启用图像生成 / 大白话注释：读配置里有没有开画图功能

        if not enabled:                                                        # 正经注释：如果未启用 / 大白话注释：如果没开
            return None                                                        # 正经注释：返回None / 大白话注释：不创建，返回空

        return cls(model_name=model or cls.DEFAULT_MODEL)                      # 正经注释：使用指定模型或默认模型创建实例 / 大白话注释：用配置的模型创建画图对象，没配置就用默认的
