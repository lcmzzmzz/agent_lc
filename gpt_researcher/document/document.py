"""
document 模块 —— 本地文档加载器

【正经注释】
本模块实现了 DocumentLoader 类，用于从本地文件系统批量加载和解析多种格式的文档。
支持的文件格式包括 PDF、TXT、Word（doc/docx）、PowerPoint（pptx）、
CSV、Excel（xls/xlsx）、Markdown 以及 HTML（html/htm）。
该类通过 LangChain 社区提供的文档加载器实现具体解析，并以异步并发方式提升加载效率。

【大白话注释】
这个文件干的事儿就是：你给它一个文件夹路径或者一堆文件路径，
它就能把里面的 PDF、Word、Excel、PPT、TXT、Markdown、HTML 这些文件全都读出来，
变成程序能用的文本数据。相当于一个"万能文件阅读器"。
"""

import asyncio  # 正经注释：异步并发库，用于并发执行多个文件加载任务 / 大白话注释：让多个文件同时加载，不用一个一个排队等
import os  # 正经注释：操作系统接口模块，用于文件路径操作和目录遍历 / 大白话注释：用来处理文件路径、判断文件存不存在、遍历文件夹
from typing import List, Union  # 正经注释：类型注解工具，提供 List 和 Union 类型提示 / 大白话注释：用来标注参数类型，告诉别人这个变量是什么类型的
from langchain_community.document_loaders import (  # 正经注释：从 LangChain 社区库导入多种文档解析器 / 大白话注释：引入一堆能读不同格式文件的"读取器"
    PyMuPDFLoader,  # 正经注释：PDF 文件解析器，基于 PyMuPDF 库 / 大白话注释：专门读 PDF 的工具
    TextLoader,  # 正经注释：纯文本文件解析器 / 大白话注释：专门读 txt 文件的工具
    UnstructuredCSVLoader,  # 正经注释：CSV 表格文件解析器 / 大白话注释：专门读 CSV 表格文件的工具
    UnstructuredExcelLoader,  # 正经注释：Excel 表格文件解析器 / 大白话注释：专门读 Excel 表格文件的工具
    UnstructuredMarkdownLoader,  # 正经注释：Markdown 文档解析器 / 大白话注释：专门读 md 格式文件的工具
    UnstructuredPowerPointLoader,  # 正经注释：PowerPoint 演示文稿解析器 / 大白话注释：专门读 PPT 的工具
    UnstructuredWordDocumentLoader  # 正经注释：Word 文档解析器 / 大白话注释：专门读 Word 文档的工具
)
from langchain_community.document_loaders import BSHTMLLoader  # 正经注释：HTML 网页文件解析器，基于 BeautifulSoup / 大白话注释：专门读 HTML 网页文件的工具


class DocumentLoader:
    """
    本地文档加载器

    【正经注释】
    DocumentLoader 负责从本地文件系统加载指定路径下的文档文件，
    支持传入单个目录路径（自动递归遍历）或文件路径列表。
    根据文件扩展名自动选择对应的解析器，以异步并发方式完成所有文件的加载，
    最终返回统一格式的文档内容列表。

    【大白话注释】
    这个类就是一个本地文件的"大管家"，你告诉它文件夹在哪或者文件列表，
    它就帮你把所有能读的文件都读出来，变成一个统一格式的数据列表返回给你。
    """

    def __init__(self, path: Union[str, List[str]]):
        """
        初始化文档加载器

        【正经注释】
        接收一个文件路径字符串或路径列表，作为待加载文档的数据源。
        path 可以为目录路径（将递归遍历所有文件）或文件路径列表。

        【大白话注释】
        告诉加载器去哪里找文件。你可以给一个文件夹路径，
        也可以直接给一堆文件路径的列表。
        """
        self.path = path  # 正经注释：保存文档路径参数，供后续加载方法使用 / 大白话注释：记住用户指定的文件路径，后面要用

    async def load(self) -> list:
        """
        异步加载所有文档

        【正经注释】
        根据 self.path 的类型（列表或目录路径），收集所有待加载文件，
        使用 asyncio.gather 并发执行所有文件加载任务，
        然后将结果统一转换为 {"raw_content": ..., "url": ...} 格式的字典列表。
        若最终未成功加载任何文档，则抛出 ValueError 异常。

        【大白话注释】
        这是核心方法，把所有文件一股脑儿全读出来。
        先看看路径是文件列表还是文件夹，然后同时开始读所有文件，
        最后把读到的内容整理成一个列表。要是啥也没读出来就报错。
        """
        tasks = []  # 正经注释：异步任务列表，收集所有待执行的文件加载协程 / 大白话注释：准备一个空篮子，把所有要读的文件任务都放进去
        if isinstance(self.path, list):  # 正经注释：判断路径参数是否为列表类型 / 大白话注释：看看用户给的是不是一个文件列表
            for file_path in self.path:
                if os.path.isfile(file_path):  # Ensure it's a valid file
                    filename = os.path.basename(file_path)  # 正经注释：提取文件名（含扩展名） / 大白话注释：把路径里最后的文件名抠出来
                    file_name, file_extension_with_dot = os.path.splitext(filename)  # 正经注释：分离文件名和扩展名（含点号） / 大白话注释：把"xxx.pdf"拆成"xxx"和".pdf"
                    file_extension = file_extension_with_dot.strip(".").lower()  # 正经注释：去除点号并转为小写，得到纯扩展名 / 大白话注释：把".pdf"变成"pdf"，统一小写好匹配
                    tasks.append(self._load_document(file_path, file_extension))  # 正经注释：将文件加载协程加入任务列表 / 大白话注释：把这个文件读取任务扔进篮子里

        elif isinstance(self.path, (str, bytes, os.PathLike)):  # 正经注释：判断路径参数是否为字符串或路径类型（即目录路径） / 大白话注释：看看用户给的是不是一个文件夹路径
            for root, dirs, files in os.walk(self.path):  # 正经注释：递归遍历目录树 / 大白话注释：一层一层地把文件夹里的文件都翻出来
                for file in files:
                    file_path = os.path.join(root, file)  # 正经注释：拼接完整文件路径 / 大白话注释：把文件夹路径和文件名拼成完整路径
                    file_name, file_extension_with_dot = os.path.splitext(file)  # 正经注释：分离文件名和扩展名 / 大白话注释：拆文件名和后缀
                    file_extension = file_extension_with_dot.strip(".").lower()  # 正经注释：去除点号并转为小写 / 大白话注释：后缀统一成小写
                    tasks.append(self._load_document(file_path, file_extension))  # 正经注释：将文件加载协程加入任务列表 / 大白话注释：把任务扔进篮子

        else:
            raise ValueError("Invalid type for path. Expected str, bytes, os.PathLike, or list thereof.")  # 正经注释：路径类型非法时抛出异常 / 大白话注释：你给的东西我认不出来，报错

        # for root, dirs, files in os.walk(self.path):
        #     for file in files:
        #         file_path = os.path.join(root, file)
        #         file_name, file_extension_with_dot = os.path.splitext(file_path)
        #         file_extension = file_extension_with_dot.strip(".")
        #         tasks.append(self._load_document(file_path, file_extension))

        docs = []  # 正经注释：最终文档结果列表 / 大白话注释：准备一个空列表装最终结果
        for pages in await asyncio.gather(*tasks):  # 正经注释：并发执行所有加载任务，等待全部完成 / 大白话注释：同时开干，等所有文件都读完
            for page in pages:  # 正经注释：遍历每个文件加载结果中的页面 / 大白话注释：一个文件可能有多页，逐页看看
                if page.page_content:  # 正经注释：过滤掉空内容的页面 / 大白话注释：这一页有内容才要，空白页就跳过
                    docs.append({
                        "raw_content": page.page_content,  # 正经注释：页面原始文本内容 / 大白话注释：这一页的文字内容
                        "url": os.path.basename(page.metadata['source'])  # 正经注释：从元数据中提取源文件名作为 url 标识 / 大白话注释：记一下这个内容来自哪个文件
                    })

        if not docs:  # 正经注释：检查是否成功加载了任何文档 / 大白话注释：要是啥也没读出来
            raise ValueError("🤷 Failed to load any documents!")  # 正经注释：抛出加载失败的异常 / 大白话注释：报错——一个文件都没读成功！

        return docs  # 正经注释：返回所有已加载文档的列表 / 大白话注释：把读好的文档列表交出去

    async def _load_document(self, file_path: str, file_extension: str) -> list:
        """
        根据文件扩展名加载单个文档

        【正经注释】
        私有异步方法，根据文件扩展名从预定义的加载器字典中选择对应的解析器，
        调用其 load() 方法完成文档解析并返回结果列表。
        若文件格式不受支持或加载过程中发生异常，将打印错误信息并返回空列表。

        【大白话注释】
        这是真正干活的内部方法，根据文件后缀名选一个合适的"读取器"来读文件。
        读不了的就跳过，出错了也不让程序崩掉，打印个错误信息就行。
        """
        ret_data = []  # 正经注释：初始化返回数据列表 / 大白话注释：准备一个空列表装结果
        try:
            loader_dict = {  # 正经注释：文件扩展名到对应加载器实例的映射字典 / 大白话注释：一个"字典"，告诉程序每种文件该用哪个工具来读
                "pdf": PyMuPDFLoader(file_path),  # 正经注释：PDF 文件使用 PyMuPDF 解析器 / 大白话注释：pdf 文件用 PyMuPDF 读
                "txt": TextLoader(file_path),  # 正经注释：纯文本文件使用 TextLoader / 大白话注释：txt 文件用文本读取器读
                "doc": UnstructuredWordDocumentLoader(file_path),  # 正经注释：旧版 Word 文档使用 Unstructured 解析器 / 大白话注释：.doc 文件用 Word 读取器读
                "docx": UnstructuredWordDocumentLoader(file_path),  # 正经注释：新版 Word 文档使用 Unstructured 解析器 / 大白话注释：.docx 文件也用 Word 读取器读
                "pptx": UnstructuredPowerPointLoader(file_path),  # 正经注释：PowerPoint 文件使用 Unstructured 解析器 / 大白话注释：pptx 文件用 PPT 读取器读
                "csv": UnstructuredCSVLoader(file_path, mode="elements"),  # 正经注释：CSV 文件使用元素模式加载 / 大白话注释：csv 文件用 CSV 读取器读
                "xls": UnstructuredExcelLoader(file_path, mode="elements"),  # 正经注释：旧版 Excel 文件使用元素模式加载 / 大白话注释：.xls 文件用 Excel 读取器读
                "xlsx": UnstructuredExcelLoader(file_path, mode="elements"),  # 正经注释：新版 Excel 文件使用元素模式加载 / 大白话注释：.xlsx 文件也用 Excel 读取器读
                "md": UnstructuredMarkdownLoader(file_path),  # 正经注释：Markdown 文件使用 Unstructured 解析器 / 大白话注释：md 文件用 Markdown 读取器读
                "html": BSHTMLLoader(file_path),  # 正经注释：HTML 文件使用 BeautifulSoup 解析器 / 大白话注释：.html 文件用网页读取器读
                "htm": BSHTMLLoader(file_path)  # 正经注释：HTM 文件同样使用 BeautifulSoup 解析器 / 大白话注释：.htm 文件也用网页读取器读
            }

            loader = loader_dict.get(file_extension, None)  # 正经注释：根据扩展名查找对应的加载器实例 / 大白话注释：去字典里找找有没有适合这个后缀的读取器
            if loader:  # 正经注释：找到对应加载器时执行加载 / 大白话注释：找到了就开始读
                try:
                    ret_data = loader.load()  # 正经注释：调用加载器的 load 方法解析文档 / 大白话注释：让读取器把文件内容读出来
                except Exception as e:  # 正经注释：捕获加载过程中的异常 / 大白话注释：读取出错了
                    print(f"Failed to load HTML document : {file_path}")  # 正经注释：打印加载失败的文件路径 / 大白话注释：告诉你是哪个文件读挂了
                    print(e)  # 正经注释：打印异常详情 / 大白话注释：把错误详情也打出来

        except Exception as e:  # 正经注释：捕获外层异常（如加载器初始化失败） / 大白话注释：万一连读取器都创建失败了
            print(f"Failed to load document : {file_path}")  # 正经注释：打印加载失败的文件路径 / 大白话注释：告诉你是哪个文件出问题了
            print(e)  # 正经注释：打印异常详情 / 大白话注释：把错误信息也打出来

        return ret_data  # 正经注释：返回解析结果，可能为空列表 / 大白话注释：把读到的内容（或空列表）交出去
