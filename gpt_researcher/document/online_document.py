"""
online_document 模块 —— 在线文档加载器

【正经注释】
本模块实现了 OnlineDocumentLoader 类，用于从给定的 URL 列表中下载远程文档文件，
将其保存为临时文件后调用对应的 LangChain 文档解析器进行内容提取。
支持的格式与 DocumentLoader 基本一致，包括 PDF、TXT、Word、PowerPoint、
CSV、Excel 和 Markdown。下载完成后会自动清理临时文件。

【大白话注释】
这个文件跟 document.py 的区别就是：document.py 读本地文件，
而这个是专门从网上下载文件来读的。流程是：下载 -> 存成临时文件 -> 解析 -> 删临时文件。
"""

import os  # 正经注释：操作系统接口模块，用于文件路径处理和临时文件删除 / 大白话注释：用来处理文件路径和删除临时文件
import aiohttp  # 正经注释：异步 HTTP 客户端库，用于异步下载远程文件 / 大白话注释：用来从网上下载文件的异步工具
import tempfile  # 正经注释：临时文件模块，用于创建下载文件的临时存储 / 大白话注释：创建临时文件用的，下完文件先存到这里
from langchain_community.document_loaders import (  # 正经注释：从 LangChain 社区库导入多种文档解析器 / 大白话注释：引入一堆能读不同格式文件的"读取器"
    PyMuPDFLoader,  # 正经注释：PDF 文件解析器 / 大白话注释：读 PDF 的工具
    TextLoader,  # 正经注释：纯文本文件解析器 / 大白话注释：读 txt 的工具
    UnstructuredCSVLoader,  # 正经注释：CSV 表格文件解析器 / 大白话注释：读 CSV 表格的工具
    UnstructuredExcelLoader,  # 正经注释：Excel 表格文件解析器 / 大白话注释：读 Excel 的工具
    UnstructuredMarkdownLoader,  # 正经注释：Markdown 文档解析器 / 大白话注释：读 Markdown 的工具
    UnstructuredPowerPointLoader,  # 正经注释：PowerPoint 演示文稿解析器 / 大白话注释：读 PPT 的工具
    UnstructuredWordDocumentLoader  # 正经注释：Word 文档解析器 / 大白话注释：读 Word 的工具
)


class OnlineDocumentLoader:
    """
    在线文档加载器

    【正经注释】
    OnlineDocumentLoader 负责从指定的 URL 列表中异步下载远程文档，
    将其保存到临时文件后使用对应的解析器提取文本内容，
    最终返回统一格式的文档内容列表。处理完成后自动删除临时文件。

    【大白话注释】
    你给它一堆网址，它就从网上把这些文件下载下来，读出里面的内容，
    然后把临时文件删掉，干干净净。相当于一个"网上文件阅读器"。
    """

    def __init__(self, urls):
        """
        初始化在线文档加载器

        【正经注释】
        接收一个 URL 列表，作为待下载和解析的远程文档数据源。

        【大白话注释】
        告诉它要从哪些网址下载文件，把这些网址存好。
        """
        self.urls = urls  # 正经注释：保存 URL 列表 / 大白话注释：记住要下载的网址列表

    async def load(self) -> list:
        """
        异步加载所有在线文档

        【正经注释】
        依次遍历所有 URL，调用 _download_and_process 方法下载并解析每个远程文档。
        将所有成功解析的文档内容收集为统一格式列表返回。
        若最终未成功加载任何文档，则抛出 ValueError 异常。

        【大白话注释】
        把所有网址的文件都下载下来读一遍，整理成列表。
        要是一个都没读出来就报错。
        """
        docs = []  # 正经注释：初始化结果列表 / 大白话注释：准备空列表装最终结果
        for url in self.urls:  # 正经注释：遍历所有 URL / 大白话注释：一个网址一个网址来处理
            pages = await self._download_and_process(url)  # 正经注释：异步下载并解析指定 URL 的文档 / 大白话注释：下载这个网址的文件并读出内容
            for page in pages:  # 正经注释：遍历解析结果中的每个页面 / 大白话注释：看看读到了几页内容
                if page.page_content:  # 正经注释：过滤掉空内容的页面 / 大白话注释：有内容的才要，空的跳过
                    docs.append({
                        "raw_content": page.page_content,  # 正经注释：页面原始文本内容 / 大白话注释：这一页的文字
                        "url": page.metadata.get("source")  # 正经注释：从元数据中提取来源 URL / 大白话注释：记下这个内容是从哪个网址来的
                    })

        if not docs:  # 正经注释：检查是否成功加载了任何文档 / 大白话注释：要是啥也没读出来
            raise ValueError("🤷 Failed to load any documents!")  # 正经注释：抛出加载失败的异常 / 大白话注释：报错——一个文件都没读成功！

        return docs  # 正经注释：返回所有已加载文档的列表 / 大白话注释：把读好的文档交出去

    async def _download_and_process(self, url: str) -> list:
        """
        下载并解析单个远程文档

        【正经注释】
        通过 aiohttp 异步 HTTP 客户端下载指定 URL 的文件内容，
        将其保存为临时文件后调用 _load_document 方法进行解析。
        包含完善的异常处理机制，网络错误或解析失败时返回空列表。

        【大白话注释】
        这方法干三件事：从网上下载文件 -> 存成临时文件 -> 解析内容。
        要是下载失败或者出错了，就返回空列表，不会让程序崩掉。
        """
        try:
            headers = {
                "User-Agent": "Mozilla/5.0"  # 正经注释：设置浏览器 User-Agent 头，避免被服务器拒绝 / 大白话注释：假装自己是浏览器，不然有些网站不让下载
            }
            async with aiohttp.ClientSession() as session:  # 正经注释：创建异步 HTTP 会话 / 大白话注释：开一个跟网站对话的通道
                async with session.get(url, headers=headers, timeout=6) as response:  # 正经注释：发起 GET 请求，设置 6 秒超时 / 大白话注释：去下载文件，最多等 6 秒
                    if response.status != 200:  # 正经注释：检查 HTTP 响应状态码是否为成功 / 大白话注释：看看服务器有没有正常返回
                        print(f"Failed to download {url}: HTTP {response.status}")  # 正经注释：打印下载失败信息和状态码 / 大白话注释：告诉你是哪个网址下载失败了
                        return []  # 正经注释：返回空列表表示下载失败 / 大白话注释：下载失败就返回空

                    content = await response.read()  # 正经注释：异步读取响应体的二进制内容 / 大白话注释：把下载的文件内容全部读出来
                    with tempfile.NamedTemporaryFile(delete=False, suffix=self._get_extension(url)) as tmp_file:  # 正经注释：创建带正确扩展名的临时文件 / 大白话注释：建一个临时文件来存下载的内容
                        tmp_file.write(content)  # 正经注释：将下载内容写入临时文件 / 大白话注释：把内容写进去
                        tmp_file_path = tmp_file.name  # 正经注释：获取临时文件的完整路径 / 大白话注释：记住临时文件放在哪了

                    return await self._load_document(tmp_file_path, self._get_extension(url).strip('.'))  # 正经注释：调用解析方法处理临时文件 / 大白话注释：用合适的工具去读这个临时文件
        except aiohttp.ClientError as e:  # 正经注释：捕获 HTTP 客户端相关异常 / 大白话注释：网络出了问题
            print(f"Failed to process {url}")  # 正经注释：打印处理失败的 URL / 大白话注释：告诉你是哪个网址出了问题
            print(e)  # 正经注释：打印异常详情 / 大白话注释：把错误详情打出来
            return []  # 正经注释：返回空列表 / 大白话注释：出错了就返回空
        except Exception as e:  # 正经注释：捕获其他未预期的异常 / 大白话注释：其他意外错误
            print(f"Unexpected error processing {url}")  # 正经注释：打印意外错误信息 / 大白话注释：告诉你是哪个网址出了意外
            print(e)  # 正经注释：打印异常详情 / 大白话注释：把错误信息打出来
            return []  # 正经注释：返回空列表 / 大白话注释：出错了就返回空

    async def _load_document(self, file_path: str, file_extension: str) -> list:
        """
        根据文件扩展名加载临时文档文件

        【正经注释】
        私有异步方法，根据文件扩展名选择对应的 LangChain 解析器加载临时文件。
        无论加载成功与否，都会在 finally 块中删除临时文件以释放磁盘空间。

        【大白话注释】
        根据文件后缀选一个合适的工具来读文件，读完了把临时文件删掉，
        不管成功还是失败都会删，不留垃圾。
        """
        ret_data = []  # 正经注释：初始化返回数据列表 / 大白话注释：准备空列表装结果
        try:
            loader_dict = {  # 正经注释：文件扩展名到对应加载器实例的映射字典 / 大白话注释：告诉程序每种文件该用哪个工具读
                "pdf": PyMuPDFLoader(file_path),  # 正经注释：PDF 文件使用 PyMuPDF 解析器 / 大白话注释：pdf 用这个读
                "txt": TextLoader(file_path),  # 正经注释：纯文本文件使用 TextLoader / 大白话注释：txt 用这个读
                "doc": UnstructuredWordDocumentLoader(file_path),  # 正经注释：旧版 Word 文档 / 大白话注释：.doc 用这个读
                "docx": UnstructuredWordDocumentLoader(file_path),  # 正经注释：新版 Word 文档 / 大白话注释：.docx 用这个读
                "pptx": UnstructuredPowerPointLoader(file_path),  # 正经注释：PowerPoint 文件 / 大白话注释：pptx 用这个读
                "csv": UnstructuredCSVLoader(file_path, mode="elements"),  # 正经注释：CSV 文件使用元素模式 / 大白话注释：csv 用这个读
                "xls": UnstructuredExcelLoader(file_path, mode="elements"),  # 正经注释：旧版 Excel 文件 / 大白话注释：.xls 用这个读
                "xlsx": UnstructuredExcelLoader(file_path, mode="elements"),  # 正经注释：新版 Excel 文件 / 大白话注释：.xlsx 用这个读
                "md": UnstructuredMarkdownLoader(file_path)  # 正经注释：Markdown 文件 / 大白话注释：md 用这个读
            }

            loader = loader_dict.get(file_extension, None)  # 正经注释：根据扩展名查找对应的加载器 / 大白话注释：去字典里找对应的读取器
            if loader:  # 正经注释：找到对应加载器时执行加载 / 大白话注释：找到了就开始读
                ret_data = loader.load()  # 正经注释：调用加载器解析文档 / 大白话注释：让读取器把内容读出来

        except Exception as e:  # 正经注释：捕获加载过程中的所有异常 / 大白话注释：出错了
            print(f"Failed to load document : {file_path}")  # 正经注释：打印加载失败的文件路径 / 大白话注释：告诉你是哪个文件读挂了
            print(e)  # 正经注释：打印异常详情 / 大白话注释：把错误信息打出来
        finally:
            os.remove(file_path)  # 正经注释：删除临时文件以释放磁盘空间（原文已有注释） / 大白话注释：把临时文件删掉，别占地方

        return ret_data  # 正经注释：返回解析结果，可能为空列表 / 大白话注释：把读到的内容（或空列表）交出去

    @staticmethod
    def _get_extension(url: str) -> str:
        """
        从 URL 中提取文件扩展名

        【正经注释】
        静态方法，从给定的 URL 中提取文件扩展名（含点号）。
        先去除 URL 中的查询参数（? 之后的部分），再通过 os.path.splitext 提取扩展名。

        【大白话注释】
        从网址里把文件后缀名抠出来。比如 "xxx.com/file.pdf?v=1" 就提取出 ".pdf"。
        """
        return os.path.splitext(url.split("?")[0])[1]  # 正经注释：先去除查询参数，再提取扩展名部分 / 大白话注释：把问号后面的参数去掉，只留后缀名
