"""
【正经注释】基于 PyMuPDF 的 PDF 文档爬虫模块，支持从 URL 下载或读取本地 PDF 文件，
使用 PyMuPDFLoader 解析提取所有页面的文本内容和元数据（标题等），
包含 SSL 错误重试和超时处理机制。

【大白话注释】这个文件专门用来解析 PDF 文件。不管是网上的 PDF 还是本地的 PDF 都能处理：
如果是网上的就先下载到临时文件再解析，解析完删掉临时文件；
如果是本地的就直接读取。还考虑了 SSL 证书问题——如果证书不对就跳过验证再试一次。
"""
import os  # 正经注释：操作系统接口，用于删除临时文件 / 大白话注释：删临时文件用的
import requests  # 正经注释：HTTP 请求库，用于下载 PDF 文件 / 大白话注释：从网上下载 PDF 用的
import tempfile  # 正经注释：临时文件模块，用于创建安全的临时 PDF 文件 / 大白话注释：创建临时文件存下载的 PDF
from urllib.parse import urlparse  # 正经注释：URL 解析工具，用于判断链接是否为有效 URL / 大白话注释：判断给的是网址还是本地文件路径
from langchain_community.document_loaders import PyMuPDFLoader  # 正经注释：LangChain 提供的 PyMuPDF 文档加载器 / 大白话注释：LangChain 里用来解析 PDF 的工具


class PyMuPDFScraper:
    """
    【正经注释】PyMuPDF 爬虫类，从 PDF URL 或本地文件路径中提取文本内容、图片和标题，
    支持 SSL 错误自动重试和下载超时处理。

    【大白话注释】专门解析 PDF 文件的爬虫。给它一个 PDF 网址或本地文件路径，
    它就能把 PDF 里所有页面的文字都抠出来，还会告诉你 PDF 的标题。
    """

    def __init__(self, link, session=None):
        """
        初始化 PyMuPDFScraper。

        Args:
          link (str): PDF 文件的 URL 或本地文件路径
          session (requests.Session, optional): HTTP 会话对象
        """
        self.link = link  # 正经注释：存储 PDF 的 URL 或本地路径 / 大白话注释：记住 PDF 在哪（网址或本地路径）
        self.session = session  # 正经注释：存储 HTTP 会话对象 / 大白话注释：HTTP 会话

    def is_url(self) -> bool:
        """
        【正经注释】判断 self.link 是否为有效的 URL（包含 scheme 和 netloc 两部分）。

        Returns:
          bool: 有效 URL 返回 True，否则返回 False

        【大白话注释】看看给的是不是网址（有 http:// 之类的协议头和域名），
        不是网址的话就认为是本地文件路径。
        """
        try:
            result = urlparse(self.link)
            return all([result.scheme, result.netloc])  # Check for valid scheme and network location
            # 正经注释：同时检查协议头（scheme）和域名（netloc）是否存在 / 大白话注释：得有协议（http/https）和域名才算网址
        except Exception:
            return False

    def scrape(self) -> tuple[str, list[str], str]:
        """
        【正经注释】执行 PDF 内容提取。如果是 URL 则先下载到临时文件再解析，
        如果是本地路径则直接加载。SSL 错误时自动跳过验证重试。
        提取所有页面的文本内容拼接返回，同时提取文档标题。

        Returns:
          tuple[str, list[str], str]: (所有页面拼接的文本内容, 空图片列表, 文档标题)

        【大白话注释】开始解析 PDF！如果是网址就先下载，下载失败（SSL 问题）就跳过证书验证再试；
        如果是本地文件就直接读。把所有页面的文字拼在一起返回，图片列表是空的（PDF 不好提取图片 URL）。
        """
        try:
            if self.is_url():  # 正经注释：如果是 URL 则下载 PDF 文件 / 大白话注释：是网址就先下载
                try:
                    response = requests.get(self.link, timeout=(5, 30), stream=True)  # 正经注释：流式下载 PDF，连接超时 5 秒，读取超时 30 秒 / 大白话注释：下载 PDF，连服务器最多等 5 秒，下载最多等 30 秒
                    response.raise_for_status()  # 正经注释：检查 HTTP 状态码，非 2xx 抛异常 / 大白话注释：下载不成功就报错
                except requests.exceptions.SSLError:  # 正经注释：SSL 证书验证失败时跳过验证重试 / 大白话注释：证书有问题？那就不管证书再试一次
                    import logging
                    logging.getLogger(__name__).warning(
                        f"SSL verification failed for {self.link}, retrying without verification"
                    )
                    response = requests.get(self.link, timeout=(5, 30), stream=True, verify=False)  # 正经注释：跳过 SSL 验证重新下载 / 大白话注释：不验证证书直接下载
                    response.raise_for_status()

                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:  # 正经注释：创建临时 PDF 文件 / 大白话注释：创建一个临时文件来存下载的 PDF
                    temp_filename = temp_file.name  # Get the temporary file name / 正经注释：获取临时文件路径 / 大白话注释：记住临时文件在哪
                    for chunk in response.iter_content(chunk_size=8192):  # 正经注释：分块写入下载内容 / 大白话注释：一块一块地写进去
                        temp_file.write(chunk)  # Write the downloaded content to the temporary file

                loader = PyMuPDFLoader(temp_filename)  # 正经注释：用临时文件路径创建加载器 / 大白话注释：用下载好的文件来解析
                doc = loader.load()  # 正经注释：加载 PDF 文档 / 大白话注释：读 PDF 内容

                os.remove(temp_filename)  # 正经注释：删除临时文件 / 大白话注释：删掉临时文件，别占地方
            else:  # 正经注释：本地文件路径直接加载 / 大白话注释：是本地文件就直接读
                loader = PyMuPDFLoader(self.link)
                doc = loader.load()

            # Extract the content, image (if any), and title from the document.
            # 正经注释：提取文档内容、图片和标题 / 大白话注释：把 PDF 里的好东西拿出来
            image = []  # 正经注释：PDF 文档不提取图片 URL / 大白话注释：图片列表是空的
            # Retrieve content from ALL pages to ensure PDFs with cover pages pass validation.
            # 正经注释：拼接所有页面的文本内容，确保带封面页的 PDF 也能通过长度验证 / 大白话注释：把每一页的文字都拼在一起，免得只有封面内容太少
            content = "\n".join(page.page_content for page in doc)
            title = doc[0].metadata.get("title", "") if doc else ""  # 正经注释：从第一页的元数据中提取标题 / 大白话注释：拿 PDF 的标题，没有就是空的
            return content, image, title

        except requests.exceptions.Timeout:  # 正经注释：下载超时时的处理 / 大白话注释：下载太久了，超时了
            print(f"Download timed out. Please check the link : {self.link}")
            return "", [], ""
        except Exception as e:  # 正经注释：其他异常的通用处理 / 大白话注释：其他错误就打印一下
            print(f"Error loading PDF : {self.link} {e}")
            return "", [], ""
