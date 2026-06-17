"""
【正经注释】
文件格式转换工具模块。
提供研究报告的异步文件写入和格式转换功能，支持以下输出格式：
- Markdown (.md)：纯文本标记格式
- PDF (.pdf)：通过 md2pdf 和 weasyprint 渲染
- Word (.docx)：通过 python-docx 和 htmldocx 转换

核心功能包括 UTF-8 编码处理、图片 URL 预处理（相对路径转绝对路径）、
以及基于 Mistune 的 Markdown 到 HTML 解析。

【大白话注释】
这个文件是"文件导出工具箱"。研究报告写完了要导出吧？
这里提供了三种导出格式：
1. Markdown —— 最简单，直接把文本存成 .md 文件
2. PDF —— 把 Markdown 转成漂亮的 PDF 文档
3. Word —— 把 Markdown 转成 Word 文档

还有一些辅助功能：
- 写文件时处理中文编码（UTF-8）
- PDF 里要插图片的话，把相对路径转成绝对路径
- 用 Mistune 库把 Markdown 解析成 HTML
"""

import aiofiles  # 正经注释：异步文件操作库，提供非阻塞的文件读写能力 / 大白话注释：异步读写文件的工具，不会卡住程序
import urllib  # 正经注释：URL 处理模块，用于对文件路径进行编码 / 大白话注释：处理网址/路径编码的工具，确保路径中的中文和特殊字符不出问题
import mistune  # 正经注释：Markdown 解析器，将 Markdown 文本转换为 HTML / 大白话注释：把 Markdown 格式的文本变成 HTML 的工具
import os  # 正经注释：操作系统接口模块，用于文件路径操作 / 大白话注释：跟文件系统打交道的工具

async def write_to_file(filename: str, text: str) -> None:
    """异步将文本写入指定文件，使用 UTF-8 编码。

    【正经注释】
    以非阻塞方式将文本内容写入文件，自动处理编码转换，
    确保所有字符均以 UTF-8 编码存储，替换无法编码的字符。

    【大白话注释】
    把文字存到文件里，用 UTF-8 编码（支持中文）。
    如果有些奇怪的字编码不了，就用问号替换掉，不会报错。

    Args:
        filename (str): 目标文件名/路径
        text (str): 要写入的文本内容
    """
    # Ensure text is a string
    # 正经注释：确保文本内容为字符串类型 / 大白话注释：万一传进来的不是字符串，先转成字符串
    if not isinstance(text, str):
        text = str(text)

    # Convert text to UTF-8, replacing any problematic characters
    # 正经注释：将文本编码为 UTF-8 并解码，替换无法处理的字符 / 大白话注释：确保文本是 UTF-8 编码，有问题的字符用替换符代替
    text_utf8 = text.encode('utf-8', errors='replace').decode('utf-8')

    async with aiofiles.open(filename, "w", encoding='utf-8') as file:  # 正经注释：以异步方式打开文件用于写入 / 大白话注释：用异步方式打开文件，不会阻塞程序
        await file.write(text_utf8)  # 正经注释：异步写入 UTF-8 编码的文本 / 大白话注释：把处理好的文本写进文件

async def write_text_to_md(text: str, filename: str = "") -> str:
    """将文本写入 Markdown 文件并返回文件路径。

    【正经注释】
    将文本内容以 Markdown 格式写入 outputs 目录下的文件，
    文件名截取前 60 个字符以避免路径过长，返回 URL 编码后的文件路径。

    【大白话注释】
    把文本存成 .md 文件，文件名最多取前 60 个字符（太长了路径会出问题）。
    存完之后返回文件路径，路径里的特殊字符都编码好了。

    Args:
        text (str): 要写入的 Markdown 文本
        filename (str): 文件名前缀，默认为空

    Returns:
        str: URL 编码后的文件路径
    """
    file_path = f"outputs/{filename[:60]}.md"  # 正经注释：构建输出文件路径，文件名截取前 60 字符 / 大白话注释：文件放在 outputs 文件夹，名字最多60个字符
    await write_to_file(file_path, text)  # 正经注释：调用异步写入函数保存文件 / 大白话注释：把文本写进去
    return urllib.parse.quote(file_path)  # 正经注释：对文件路径进行 URL 编码并返回 / 大白话注释：把路径里的中文和特殊字符编码一下再返回

def _preprocess_images_for_pdf(text: str) -> str:
    """将 Web 图片 URL 转换为绝对文件路径，以支持 PDF 生成。

    【正经注释】
    将 Markdown 中以 /outputs/ 开头的相对图片 URL 转换为 file:// 协议的绝对路径，
    使 weasyprint PDF 渲染引擎能够正确解析本地图片资源。

    【大白话注释】
    PDF 生成器不太认相对路径的图片，所以这个函数把类似 "/outputs/images/xxx.png"
    的路径换成完整的绝对路径（比如 "D:/项目/outputs/images/xxx.png"），这样 PDF 里就能正常显示图片了。

    Args:
        text (str): 包含 Markdown 图片语法的文本

    Returns:
        str: 图片路径替换后的文本
    """
    import re  # 正经注释：正则表达式模块，用于匹配和替换图片 URL 模式 / 大白话注释：用正则表达式来找图片路径并替换

    base_path = os.path.abspath(".")  # 正经注释：获取当前工作目录的绝对路径作为基准路径 / 大白话注释：拿到当前目录的完整路径

    # Pattern to find markdown images with /outputs/ URLs
    # 正经注释：定义替换函数，将匹配的相对路径图片 URL 转换为绝对路径 / 大白话注释：定义一个函数，把找到的图片相对路径换成绝对路径
    def replace_image_url(match):
        alt_text = match.group(1)  # 正经注释：提取图片的 alt 替换文本 / 大白话注释：拿到图片的描述文字
        url = match.group(2)  # 正经注释：提取图片 URL / 大白话注释：拿到图片的路径

        # Convert /outputs/... to absolute path
        # 正经注释：将以 /outputs/ 开头的路径转换为绝对路径 / 大白话注释：如果是 outputs 文件夹下的图片，就拼成完整路径
        if url.startswith("/outputs/"):
            abs_path = os.path.join(base_path, url.lstrip("/"))  # 正经注释：拼接基准路径和图片相对路径 / 大白话注释：把当前目录路径和图片路径拼在一起
            return f"![{alt_text}]({abs_path})"  # 正经注释：返回替换后的 Markdown 图片语法 / 大白话注释：返回改好路径的图片标记
        return match.group(0)  # 正经注释：非 outputs 路径的图片保持不变 / 大白话注释：不是 outputs 下的图片，不动它

    # Match ![alt text](/outputs/images/...)
    # 正经注释：正则匹配 Markdown 图片语法中 /outputs/ 开头的 URL / 大白话注释：用正则找所有类似 "![描述](/outputs/xxx)" 的图片标记
    pattern = r'!\[([^\]]*)\]\((/outputs/[^)]+)\)'
    return re.sub(pattern, replace_image_url, text)  # 正经注释：执行全局替换并返回结果 / 大白话注释：把所有匹配到的图片路径都换掉


async def write_md_to_pdf(text: str, filename: str = "") -> str:
    """将 Markdown 文本转换为 PDF 文件并返回文件路径。

    【正经注释】
    使用 md2pdf 库将 Markdown 文本渲染为 PDF 文档，应用自定义 CSS 样式，
    预处理图片 URL 以确保本地图片正确嵌入，返回 URL 编码后的文件路径。

    【大白话注释】
    把 Markdown 变成漂亮的 PDF 文件。步骤：
    1. 先把图片路径处理好（换成绝对路径）
    2. 加上 CSS 样式让 PDF 好看
    3. 用 md2pdf 库生成 PDF
    4. 返回文件路径

    Args:
        text (str): Markdown 文本
        filename (str): 文件名前缀，默认为空

    Returns:
        str: URL 编码后的 PDF 文件路径；转换失败时返回空字符串
    """
    file_path = f"outputs/{filename[:60]}.pdf"  # 正经注释：构建 PDF 输出文件路径 / 大白话注释：PDF 文件放在 outputs 文件夹

    try:
        # Resolve css path relative to this backend module to avoid
        # dependency on the current working directory.
        # 正经注释：解析 CSS 样式文件的路径，相对于当前模块定位，避免依赖工作目录 / 大白话注释：找到 PDF 样式表文件的位置
        current_dir = os.path.dirname(os.path.abspath(__file__))  # 正经注释：获取当前模块所在目录 / 大白话注释：拿到这个 Python 文件所在的文件夹
        css_path = os.path.join(current_dir, "styles", "pdf_styles.css")  # 正经注释：拼接 CSS 样式文件路径 / 大白话注释：样式文件在 styles 文件夹里叫 pdf_styles.css

        # Preprocess image URLs for PDF compatibility
        # 正经注释：预处理图片 URL，确保 PDF 渲染器能正确加载本地图片 / 大白话注释：把图片的相对路径换成绝对路径
        processed_text = _preprocess_images_for_pdf(text)

        # Set base_url to current directory for resolving any remaining relative paths
        # 正经注释：设置 base_url 为当前目录，用于解析剩余的相对路径 / 大白话注释：告诉 PDF 生成器"当前目录是这里"，方便它找文件
        base_url = os.path.abspath(".")
        from md2pdf.core import md2pdf  # 正经注释：延迟导入 md2pdf 核心模块 / 大白话注释：用到的时候才导入 md2pdf 库
        md2pdf(
               file_path,  # 正经注释：PDF 输出文件路径 / 大白话注释：PDF 存到哪里
               raw=processed_text,  # 正经注释：预处理后的 Markdown 文本 / 大白话注释：要转换的内容（已经处理好图片路径的）
               css=css_path,  # 正经注释：CSS 样式文件路径 / 大白话注释：PDF 用什么样式
               base_url=base_url,  # 正经注释：基准 URL，用于解析相对路径 / 大白话注释：告诉它去哪找相对路径引用的文件
            )
        print(f"Report written to {file_path}")  # 正经注释：输出文件写入成功信息 / 大白话注释：打印"报告已写入"
    except Exception as e:
        print(f"Error in converting Markdown to PDF: {e}")  # 正经注释：输出转换异常信息 / 大白话注释：出错了，打印错误信息
        return ""  # 正经注释：返回空字符串表示转换失败 / 大白话注释：失败了就返回空字符串

    encoded_file_path = urllib.parse.quote(file_path)  # 正经注释：对文件路径进行 URL 编码 / 大白话注释：把路径里的特殊字符编码一下
    return encoded_file_path  # 正经注释：返回编码后的文件路径 / 大白话注释：把处理好的路径交出去

async def write_md_to_word(text: str, filename: str = "") -> str:
    """将 Markdown 文本转换为 DOCX 文件并返回文件路径。

    【正经注释】
    使用 Mistune 将 Markdown 解析为 HTML，再通过 HtmlToDocx 将 HTML 转换为
    Word 文档格式，最终保存为 .docx 文件，返回 URL 编码后的文件路径。

    【大白话注释】
    把 Markdown 变成 Word 文档。步骤：
    1. 先用 Mistune 把 Markdown 变成 HTML
    2. 再用 htmldocx 把 HTML 变成 Word 格式
    3. 保存成 .docx 文件
    4. 返回文件路径

    Args:
        text (str): Markdown 文本
        filename (str): 文件名前缀，默认为空

    Returns:
        str: URL 编码后的 DOCX 文件路径；转换失败时返回空字符串
    """
    file_path = f"outputs/{filename[:60]}.docx"  # 正经注释：构建 DOCX 输出文件路径 / 大白话注释：Word 文件放在 outputs 文件夹

    try:
        from docx import Document  # 正经注释：导入 python-docx 的 Document 类 / 大白话注释：导入创建 Word 文档的工具
        from htmldocx import HtmlToDocx  # 正经注释：导入 HTML 转 Word 的工具类 / 大白话注释：导入把 HTML 变成 Word 内容的工具
        # Convert report markdown to HTML
        # 正经注释：使用 Mistune 将 Markdown 转换为 HTML / 大白话注释：先把 Markdown 变成 HTML
        html = mistune.html(text)
        # Create a document object
        # 正经注释：创建空的 Word 文档对象 / 大白话注释：新建一个空白的 Word 文档
        doc = Document()
        # Convert the html generated from the report to document format
        # 正经注释：将 HTML 内容转换为 Word 文档格式并添加到文档中 / 大白话注释：把 HTML 内容塞进 Word 文档里
        HtmlToDocx().add_html_to_document(html, doc)

        # Saving the docx document to file_path
        # 正经注释：将 Word 文档保存到指定路径 / 大白话注释：把 Word 文档存到硬盘上
        doc.save(file_path)

        print(f"Report written to {file_path}")  # 正经注释：输出文件保存成功信息 / 大白话注释：打印"报告已写入"

        encoded_file_path = urllib.parse.quote(file_path)  # 正经注释：对文件路径进行 URL 编码 / 大白话注释：把路径里的特殊字符编码一下
        return encoded_file_path  # 正经注释：返回编码后的文件路径 / 大白话注释：把处理好的路径交出去

    except Exception as e:
        print(f"Error in converting Markdown to DOCX: {e}")  # 正经注释：输出转换异常信息 / 大白话注释：出错了，打印错误信息
        return ""  # 正经注释：返回空字符串表示转换失败 / 大白话注释：失败了就返回空字符串
