"""GPT Researcher 的 ModelsLab 图像生成提供者。        # 正经注释：ModelsLab图像生成提供者模块，通过ModelsLab API支持Flux、SDXL等模型生成图片 / 大白话注释：这个文件负责用ModelsLab的AI来画图，支持Flux、SDXL、Stable Diffusion等5万多个模型

本模块通过 ModelsLab API 提供图像生成能力，支持 Flux、SDXL、Stable Diffusion 及 5万+ 社区模型。        # 正经注释：通过ModelsLab的text-to-image API支持多种扩散模型 / 大白话注释：ModelsLab是个大平台，上面有好多画图模型可以用

API 文档：https://docs.modelslab.com        # 正经注释：ModelsLab API文档地址 / 大白话注释：官方文档在这里，想了解详细用法可以去看
"""

import asyncio                                                                 # 正经注释：异步编程核心库 / 大白话注释：异步编程基础库
import hashlib                                                                 # 正经注释：哈希计算库 / 大白话注释：算哈希值用的，给图片起名字
import logging                                                                 # 正经注释：日志记录库 / 大白话注释：记日志的库
import os                                                                      # 正经注释：操作系统接口 / 大白话注释：跟操作系统打交道的库
from pathlib import Path                                                       # 正经注释：路径操作库 / 大白话注释：处理文件路径的库
from typing import Any, Dict, List, Optional                                   # 正经注释：类型注解工具 / 大白话注释：类型提示用的

logger = logging.getLogger(__name__)                                           # 正经注释：获取当前模块的日志记录器 / 大白话注释：创建日志记录器

TEXT2IMG_URL = "https://modelslab.com/api/v6/images/text2img"                  # 正经注释：ModelsLab文本转图片API端点 / 大白话注释：ModelsLab的文生图接口地址
FETCH_BASE_URL = "https://modelslab.com/api/v6/images/fetch"                  # 正经注释：ModelsLab获取生成结果API端点 / 大白话注释：用来查询画图结果的接口地址
MAX_POLL_ATTEMPTS = 12                                                         # 正经注释：最大轮询尝试次数 / 大白话注释：最多查12次结果
POLL_INTERVAL_SECONDS = 5                                                      # 正经注释：轮询间隔秒数 / 大白话注释：每5秒查一次


class ModelsLabImageGeneratorProvider:                                         # 正经注释：基于ModelsLab API的图像生成提供者类 / 大白话注释：用ModelsLab画图的类
    """基于 ModelsLab API 的图像生成提供者。        # 正经注释：使用ModelsLab的text-to-image API生成图片 / 大白话注释：用ModelsLab来画图的类

    支持 Flux、SDXL、Stable Diffusion 及数千个社区模型。        # 正经注释：支持多种扩散模型 / 大白话注释：支持的画图模型很多很多
    认证方式为在请求体中包含 API 密钥（非 Bearer Token）。        # 正经注释：认证方式是将API密钥放在请求体中，而非HTTP头部 / 大白话注释：密钥不是放请求头里的，是放请求体里的

    属性：        # 正经注释：类属性说明 / 大白话注释：这个类有这些属性
        model_id: 使用的 ModelsLab 模型（默认："flux"）。        # 正经注释：ModelsLab模型标识 / 大白话注释：用哪个模型画图
        api_key: 从 modelslab.com/account/api-key 获取的 ModelsLab API 密钥。        # 正经注释：ModelsLab API密钥 / 大白话注释：你的ModelsLab密钥
        output_dir: 生成图片的保存目录。        # 正经注释：图片输出目录 / 大白话注释：画好的图存哪里
    """

    DEFAULT_MODEL = "flux"                                                     # 正经注释：默认使用的模型为Flux / 大白话注释：默认用Flux模型画图

    def __init__(                                                               # 正经注释：初始化ModelsLab图像生成提供者 / 大白话注释：创建画图对象
        self,                                                                  # 正经注释：自身实例 / 大白话注释：自己
        model_id: Optional[str] = None,                                        # 正经注释：模型ID（可选） / 大白话注释：用哪个模型
        api_key: Optional[str] = None,                                         # 正经注释：API密钥（可选） / 大白话注释：你的密钥
        output_dir: str = "outputs",                                           # 正经注释：输出目录 / 大白话注释：存图的文件夹
    ):                                                                         # 正经注释：参数列表结束 / 大白话注释：参数到这里
        self.model_id = model_id or self.DEFAULT_MODEL                         # 正经注释：设置模型ID，未指定则使用默认值 / 大白话注释：没指定就用Flux
        self.api_key = api_key or os.getenv("MODELSLAB_API_KEY")               # 正经注释：设置API密钥，优先使用参数，其次从环境变量获取 / 大白话注释：密钥从参数找，找不到从环境变量找
        self.output_dir = Path(output_dir)                                     # 正经注释：将输出目录转换为Path对象 / 大白话注释：把路径转成Path对象

        if not self.api_key:                                                   # 正经注释：如果未获取到API密钥 / 大白话注释：如果找不到密钥
            logger.warning(                                                    # 正经注释：记录警告日志 / 大白话注释：打个警告
                "No ModelsLab API key found. Set MODELSLAB_API_KEY "           # 正经注释：提示未找到API密钥 / 大白话注释：告诉你没找到密钥
                "environment variable to enable image generation."              # 正经注释：提示需要设置环境变量 / 大白话注释：让你设环境变量
            )                                                                  # 正经注释：日志记录完成 / 大白话注释：警告完毕

    def _ensure_output_dir(self, research_id: str = "") -> Path:               # 正经注释：确保输出目录存在并返回路径 / 大白话注释：检查存图文件夹有没有，没有就创建
        path = (                                                               # 正经注释：构建输出路径 / 大白话注释：算出存图的路径
            self.output_dir / "images" / research_id                           # 正经注释：带研究ID的路径 / 大白话注释：按研究编号的子文件夹
            if research_id                                                     # 正经注释：如果有研究ID / 大白话注释：如果有编号的话
            else self.output_dir / "images"                                    # 正经注释：否则使用默认路径 / 大白话注释：没有编号就用通用文件夹
        )                                                                      # 正经注释：路径构建完成 / 大白话注释：路径算好了
        path.mkdir(parents=True, exist_ok=True)                                # 正经注释：递归创建目录 / 大白话注释：文件夹不存在就创建
        return path                                                            # 正经注释：返回输出路径 / 大白话注释：把路径返回

    def _generate_filename(self, prompt: str, index: int = 0) -> str:          # 正经注释：根据提示词哈希生成文件名 / 大白话注释：给图片起个不重复的名字
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:8]             # 正经注释：计算提示词MD5哈希取前8位 / 大白话注释：算个哈希值取前8位
        return f"img_{prompt_hash}_{index}.png"                                # 正经注释：返回格式化的文件名 / 大白话注释：返回文件名

    async def _download_image(self, url: str) -> bytes:                        # 正经注释：异步下载图片 / 大白话注释：从网上把画好的图下载下来
        """异步从 URL 下载图片。        # 正经注释：从指定URL异步下载图片数据 / 大白话注释：从网址把图片数据拉过来"""
        try:                                                                   # 正经注释：尝试使用aiohttp下载 / 大白话注释：试试用aiohttp下载
            import aiohttp                                                     # 正经注释：导入aiohttp异步HTTP客户端 / 大白话注释：导入异步下载库

            async with aiohttp.ClientSession() as session:                     # 正经注释：创建aiohttp会话 / 大白话注释：开一个下载会话
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:  # 正经注释：发送GET请求，超时30秒 / 大白话注释：下载，30秒没下完就超时
                    resp.raise_for_status()                                    # 正经注释：检查HTTP状态码 / 大白话注释：看看有没有报错
                    return await resp.read()                                   # 正经注释：读取响应体为字节数据 / 大白话注释：把图片数据读出来
        except ImportError:                                                    # 正经注释：捕获aiohttp未安装异常 / 大白话注释：如果aiohttp没装
            # Fallback to requests in thread if aiohttp not available           # 正经注释：回退到requests库在线程中同步下载 / 大白话注释：那就用requests来下载
            import requests                                                    # 正经注释：导入requests同步HTTP库 / 大白话注释：导入同步下载库

            response = await asyncio.to_thread(requests.get, url, timeout=30)  # 正经注释：在线程池中执行同步请求 / 大白话注释：把同步下载包成异步的
            response.raise_for_status()                                        # 正经注释：检查HTTP状态码 / 大白话注释：看看有没有报错
            return response.content                                            # 正经注释：返回响应体内容 / 大白话注释：把图片数据返回

    async def _poll_for_result(self, request_id: str) -> List[str]:            # 正经注释：轮询获取生成结果 / 大白话注释：一遍遍地问"画好了没？画好了没？"
        """轮询 fetch 端点直到生成完成。        # 正经注释：持续查询ModelsLab的fetch端点直到图片生成完成 / 大白话注释：隔几秒就问一次，直到图画好"""
        try:                                                                   # 正经注释：尝试使用aiohttp轮询 / 大白话注释：试试用aiohttp来问
            import aiohttp                                                     # 正经注释：导入aiohttp异步HTTP客户端 / 大白话注释：导入异步下载库

            for _ in range(MAX_POLL_ATTEMPTS):                                 # 正经注释：最多轮询指定次数 / 大白话注释：最多问12次
                await asyncio.sleep(POLL_INTERVAL_SECONDS)                     # 正经注释：等待指定间隔 / 大白话注释：等5秒再问
                async with aiohttp.ClientSession() as session:                 # 正经注释：创建aiohttp会话 / 大白话注释：开个会话
                    async with session.post(                                   # 正经注释：发送POST请求 / 大白话注释：发个POST请求去问
                        f"{FETCH_BASE_URL}/{request_id}",                      # 正经注释：构建带请求ID的fetch URL / 大白话注释：把请求ID拼到URL里
                        json={"key": self.api_key},                            # 正经注释：在请求体中传入API密钥 / 大白话注释：把密钥带上
                        timeout=aiohttp.ClientTimeout(total=15),               # 正经注释：请求超时15秒 / 大白话注释：15秒没回就超时
                    ) as resp:                                                 # 正经注释：获取响应 / 大白话注释：拿到响应
                        body = await resp.json()                               # 正经注释：解析JSON响应体 / 大白话注释：把返回的JSON解析出来
                        if body.get("status") == "success" and body.get("output"):  # 正经注释：如果状态为成功且有输出 / 大白话注释：画好了！
                            return body["output"]                              # 正经注释：返回输出结果（图片URL列表） / 大白话注释：把图片URL返回
                        if body.get("status") == "error":                      # 正经注释：如果状态为错误 / 大白话注释：出错了
                            raise RuntimeError(                                # 正经注释：抛出运行时异常 / 大白话注释：报错！
                                body.get("messege", "ModelsLab generation error")  # 正经注释：使用API返回的错误信息或默认信息 / 大白话注释：看看API说了什么错
                            )                                                  # 正经注释：异常抛出完成 / 大白话注释：报错完毕
        except ImportError:                                                    # 正经注释：捕获aiohttp未安装异常 / 大白话注释：如果aiohttp没装
            import requests                                                    # 正经注释：导入requests同步HTTP库 / 大白话注释：用requests来问

            for _ in range(MAX_POLL_ATTEMPTS):                                 # 正经注释：最多轮询指定次数 / 大白话注释：最多问12次
                await asyncio.sleep(POLL_INTERVAL_SECONDS)                     # 正经注释：等待指定间隔 / 大白话注释：等5秒再问
                resp = await asyncio.to_thread(                                # 正经注释：在线程池中执行同步请求 / 大白话注释：把同步请求包成异步的
                    requests.post,                                             # 正经注释：使用requests的POST方法 / 大白话注释：发POST请求
                    f"{FETCH_BASE_URL}/{request_id}",                          # 正经注释：构建带请求ID的fetch URL / 大白话注释：把请求ID拼到URL里
                    json={"key": self.api_key},                                # 正经注释：在请求体中传入API密钥 / 大白话注释：把密钥带上
                    timeout=15,                                                # 正经注释：请求超时15秒 / 大白话注释：15秒超时
                )                                                              # 正经注释：请求完成 / 大白话注释：问完了
                body = resp.json()                                             # 正经注释：解析JSON响应体 / 大白话注释：解析返回的JSON
                if body.get("status") == "success" and body.get("output"):     # 正经注释：如果状态为成功且有输出 / 大白话注释：画好了！
                    return body["output"]                                      # 正经注释：返回输出结果 / 大白话注释：把图片URL返回
                if body.get("status") == "error":                              # 正经注释：如果状态为错误 / 大白话注释：出错了
                    raise RuntimeError(body.get("messege", "ModelsLab generation error"))  # 正经注释：抛出运行时异常 / 大白话注释：报错！

        raise TimeoutError("ModelsLab image generation timed out after polling.")  # 正经注释：轮询超时后抛出超时异常 / 大白话注释：问了太多次都没结果，超时报错

    async def generate_image(                                                  # 正经注释：异步生成图片方法 / 大白话注释：主要的画图方法
        self,                                                                  # 正经注释：自身实例 / 大白话注释：自己
        prompt: str,                                                           # 正经注释：图像生成提示词 / 大白话注释：你要画啥
        context: str = "",                                                     # 正经注释：额外上下文 / 大白话注释：背景信息
        research_id: str = "",                                                 # 正经注释：研究任务ID / 大白话注释：研究编号
        aspect_ratio: str = "1:1",                                             # 正经注释：图片宽高比（本提供者忽略此参数） / 大白话注释：比例参数，但这里不用
        num_images: int = 1,                                                   # 正经注释：生成图片数量 / 大白话注释：画几张
        style: str = "dark",                                                   # 正经注释：图片样式（本提供者忽略此参数） / 大白话注释：风格参数，但这里不用
    ) -> List[Dict[str, Any]]:                                                 # 正经注释：返回图片信息字典列表 / 大白话注释：返回图的信息
        """使用 ModelsLab 的文本转图片 API 生成图片。        # 正经注释：通过ModelsLab的text-to-image API生成图片 / 大白话注释：用ModelsLab来画图

        参数：        # 正经注释：参数说明 / 大白话注释：这些参数是
            prompt: 图像生成提示词。        # 正经注释：图像生成提示词 / 大白话注释：你想画什么
            context: 额外上下文（追加到提示词后）。        # 正经注释：附加到提示词后的额外上下文 / 大白话注释：背景信息，会加到提示词后面
            research_id: 用于组织输出目录的研究ID。        # 正经注释：用于组织输出目录的研究ID / 大白话注释：研究编号，用来分文件夹
            aspect_ratio: 忽略（ModelsLab 使用 width/height）。        # 正经注释：忽略（ModelsLab使用width/height参数） / 大白话注释：这个参数没用
            num_images: 生成图片数量（1-4张）。        # 正经注释：生成图片数量 / 大白话注释：画几张，最多4张
            style: 忽略（提示词直接控制风格）。        # 正经注释：忽略（通过提示词直接控制风格） / 大白话注释：这个参数也没用

        返回：        # 正经注释：返回值说明 / 大白话注释：返回的东西是
            包含 path、url、prompt 和 alt_text 键的字典列表。        # 正经注释：包含图片信息的字典列表 / 大白话注释：每张图的信息
        """
        if not self.api_key:                                                   # 正经注释：如果未配置API密钥 / 大白话注释：没有密钥
            logger.warning("No ModelsLab API key set; skipping image generation.")  # 正经注释：记录警告日志 / 大白话注释：打个警告
            return []                                                          # 正经注释：返回空列表 / 大白话注释：画不了

        output_path = self._ensure_output_dir(research_id)                     # 正经注释：确保输出目录存在 / 大白话注释：确保存图文件夹有了
        full_prompt = f"{prompt}. {context}" if context else prompt             # 正经注释：如果有上下文则追加到提示词后 / 大白话注释：把背景信息加到提示词后面
        samples = min(max(1, num_images), 4)                                   # 正经注释：限制生成图片数量在1-4之间 / 大白话注释：最多画4张，最少画1张

        payload = {                                                            # 正经注释：构建API请求负载 / 大白话注释：准备发给API的参数
            "key": self.api_key,                                               # 正经注释：API密钥 / 大白话注释：密钥
            "model_id": self.model_id,                                         # 正经注释：模型ID / 大白话注释：用哪个模型
            "prompt": full_prompt,                                             # 正经注释：完整提示词 / 大白话注释：画什么的描述
            "negative_prompt": "low quality, blurry, watermark, text, nsfw",   # 正经注释：反向提示词，排除低质量内容 / 大白话注释：不要画这些：低质量、模糊、水印、文字、不雅内容
            "width": 768,                                                      # 正经注释：图片宽度768像素 / 大白话注释：图宽768像素
            "height": 512,                                                     # 正经注释：图片高度512像素 / 大白话注释：图高512像素
            "samples": samples,                                                # 正经注释：生成图片数量 / 大白话注释：画几张
            "num_inference_steps": 30,                                         # 正经注释：推理步数30步 / 大白话注释：AI想30步来画，越多越精细但越慢
            "guidance_scale": 7.5,                                             # 正经注释：引导比例7.5 / 大白话注释：AI听不听你的话，越大越听话
            "seed": -1,                                                        # 正经注释：随机种子-1表示随机 / 大白话注释：随机种子，每次画出来不一样
            "safety_checker": "yes",                                           # 正经注释：启用安全检查 / 大白话注释：开安全过滤，不画不合适的东西
        }                                                                      # 正经注释：请求负载构建完成 / 大白话注释：参数准备好了

        try:                                                                   # 正经注释：尝试发送请求生成图片 / 大白话注释：试试画图
            image_urls = await self._request_images(payload)                   # 正经注释：发送请求获取图片URL列表 / 大白话注释：把请求发出去，拿到图片URL
        except Exception as exc:                                               # 正经注释：捕获请求异常 / 大白话注释：出错了
            logger.error(f"ModelsLab image generation failed: {exc}", exc_info=True)  # 正经注释：记录生成失败日志 / 大白话注释：日志记一下失败了
            return []                                                          # 正经注释：返回空列表 / 大白话注释：画不了就返回空的

        results = []                                                           # 正经注释：结果列表 / 大白话注释：存结果的列表
        for i, url in enumerate(image_urls[:num_images]):                      # 正经注释：遍历图片URL列表 / 大白话注释：一张一张下载
            try:                                                               # 正经注释：尝试下载并保存图片 / 大白话注释：试试下载
                image_bytes = await self._download_image(url)                  # 正经注释：异步下载图片数据 / 大白话注释：把图片下载下来
                filename = self._generate_filename(prompt, i)                  # 正经注释：生成文件名 / 大白话注释：给图片起名
                filepath = output_path / filename                              # 正经注释：拼接完整文件路径 / 大白话注释：完整路径
                with open(filepath, "wb") as fh:                               # 正经注释：以二进制写模式打开文件 / 大白话注释：打开文件
                    fh.write(image_bytes)                                      # 正经注释：写入图片数据 / 大白话注释：把图片数据写进去

                absolute_path = filepath.resolve()                             # 正经注释：获取绝对路径 / 大白话注释：完整路径
                web_url = (                                                    # 正经注释：构建Web URL / 大白话注释：网页路径
                    f"/outputs/images/{research_id}/{filename}"                # 正经注释：带研究ID的Web URL / 大白话注释：有研究编号的路径
                    if research_id                                             # 正经注释：如果有研究ID / 大白话注释：如果有编号
                    else f"/outputs/images/{filename}"                         # 正经注释：默认Web URL / 大白话注释：没有编号的路径
                )                                                              # 正经注释：Web URL构建完成 / 大白话注释：路径算好了
                results.append(                                                # 正经注释：将图片信息添加到结果列表 / 大白话注释：把这张图的信息记下来
                    {                                                          # 正经注释：图片信息字典 / 大白话注释：信息字典
                        "path": str(absolute_path),                            # 正经注释：绝对路径 / 大白话注释：完整路径
                        "url": web_url,                                        # 正经注释：Web URL / 大白话注释：网页路径
                        "absolute_url": str(absolute_path),                    # 正经注释：绝对URL / 大白话注释：也是完整路径
                        "prompt": prompt,                                      # 正经注释：原始提示词 / 大白话注释：最初的提示词
                        "alt_text": f"Illustration: {prompt[:120]}",           # 正经注释：无障碍替代文本 / 大白话注释：图片描述
                    }                                                          # 正经注释：图片信息完成 / 大白话注释：信息记好了
                )                                                              # 正经注释：添加到结果列表 / 大白话注释：加到列表里
                logger.info(f"ModelsLab image saved to: {filepath}")           # 正经注释：记录保存成功日志 / 大白话注释：日志记一下图存好了
            except Exception as exc:                                           # 正经注释：捕获下载异常 / 大白话注释：下载出错了
                logger.error(f"Failed to download image {i}: {exc}")           # 正经注释：记录下载失败日志 / 大白话注释：日志记一下下载失败了

        return results                                                         # 正经注释：返回结果列表 / 大白话注释：把结果返回

    async def _request_images(self, payload: Dict[str, Any]) -> List[str]:     # 正经注释：向text2img端点发送POST请求并处理异步处理 / 大白话注释：把画图请求发给ModelsLab，等它画好
        """POST 到 text2img 端点并处理异步处理流程。        # 正经注释：发送POST请求到text2img端点，处理同步和异步两种响应模式 / 大白话注释：发请求画图，如果它说"正在画"就等着"""
        try:                                                                   # 正经注释：尝试使用aiohttp发送请求 / 大白话注释：试试用aiohttp发
            import aiohttp                                                     # 正经注释：导入aiohttp异步HTTP客户端 / 大白话注释：导入异步HTTP库

            async with aiohttp.ClientSession() as session:                     # 正经注释：创建aiohttp会话 / 大白话注释：开个会话
                async with session.post(                                       # 正经注释：发送POST请求 / 大白话注释：发POST请求
                    TEXT2IMG_URL,                                               # 正经注释：text2img API端点 / 大白话注释：画图接口地址
                    json=payload,                                              # 正经注释：请求负载 / 大白话注释：把参数发过去
                    timeout=aiohttp.ClientTimeout(total=30),                   # 正经注释：请求超时30秒 / 大白话注释：30秒超时
                ) as resp:                                                     # 正经注释：获取响应 / 大白话注释：拿到响应
                    body = await resp.json()                                   # 正经注释：解析JSON响应体 / 大白话注释：解析返回的JSON
        except ImportError:                                                    # 正经注释：捕获aiohttp未安装异常 / 大白话注释：如果aiohttp没装
            import requests                                                    # 正经注释：导入requests同步HTTP库 / 大白话注释：用requests发

            body = await asyncio.to_thread(                                    # 正经注释：在线程池中执行同步请求 / 大白话注释：把同步请求包成异步的
                lambda: requests.post(TEXT2IMG_URL, json=payload, timeout=30).json()  # 正经注释：发送POST请求并解析JSON / 大白话注释：发请求拿JSON
            )                                                                  # 正经注释：请求完成 / 大白话注释：请求完了

        if body.get("status") == "error":                                      # 正经注释：如果API返回错误状态 / 大白话注释：如果出错了
            raise RuntimeError(body.get("messege", "ModelsLab API error"))     # 正经注释：抛出运行时异常 / 大白话注释：报错！

        if body.get("status") == "processing" and body.get("id"):              # 正经注释：如果API返回正在处理状态且有请求ID / 大白话注释：如果它在画但还没画好
            return await self._poll_for_result(body["id"])                     # 正经注释：轮询等待生成结果 / 大白话注释：等着它画好

        return body.get("output", [])                                          # 正经注释：返回输出结果，默认为空列表 / 大白话注释：把图片URL列表返回，没有就返回空的

    def is_available(self) -> bool:                                            # 正经注释：检查图像生成功能是否可用 / 大白话注释：看看能不能画图
        """如果已配置 API 密钥则返回 True。        # 正经注释：检查API密钥是否已配置 / 大白话注释：看看有没有密钥"""
        return bool(self.api_key)                                              # 正经注释：返回API密钥是否存在 / 大白话注释：有密钥就能画

    @classmethod                                                               # 正经注释：类方法装饰器 / 大白话注释：不用创建对象就能调用的方法
    def from_config(cls, config) -> Optional["ModelsLabImageGeneratorProvider"]:  # 正经注释：从配置对象创建ModelsLabImageGeneratorProvider实例 / 大白话注释：从配置文件创建画图对象
        """从 Config 对象创建 ModelsLabImageGeneratorProvider。        # 正经注释：根据Config对象配置创建ModelsLab图像生成提供者 / 大白话注释：用配置文件创建ModelsLab画图对象"""
        enabled = getattr(config, "IMAGE_GENERATION_ENABLED", False)           # 正经注释：从配置中获取是否启用图像生成 / 大白话注释：看看配置里有没有开画图
        provider = getattr(config, "IMAGE_GENERATION_PROVIDER", "google")      # 正经注释：从配置中获取图像生成提供者名称 / 大白话注释：看看用哪家来画图
        if not enabled or provider != "modelslab":                             # 正经注释：如果未启用或不是ModelsLab提供者 / 大白话注释：没开或者不是用ModelsLab
            return None                                                        # 正经注释：返回None / 大白话注释：不创建
        model = getattr(config, "IMAGE_GENERATION_MODEL", None)                # 正经注释：从配置中获取图像生成模型 / 大白话注释：看看配置里用的什么模型
        return cls(model_id=model or cls.DEFAULT_MODEL)                        # 正经注释：使用指定模型或默认模型创建实例 / 大白话注释：用配置的模型创建对象
