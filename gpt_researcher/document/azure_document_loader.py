"""
azure_document_loader 模块 —— Azure Blob 存储文档加载器

【正经注释】
本模块实现了 AzureDocumentLoader 类，用于从 Azure Blob Storage 容器中批量下载文件。
该加载器通过 Azure SDK 连接到指定的存储容器，将所有 Blob 对象下载到本地临时目录，
并返回文件路径列表，以便后续交由 DocumentLoader 进行统一解析处理。

【大白话注释】
这个文件专门负责从微软 Azure 云存储上下文件。
你告诉它容器名和连接信息，它就把里面的所有文件都下载到本地一个临时文件夹里，
然后把文件路径列表交出去，让别的工具去读这些文件的内容。
"""

from azure.storage.blob import BlobServiceClient  # 正经注释：Azure Blob 存储服务客户端，用于连接和操作 Blob 存储 / 大白话注释：微软 Azure 云存储的工具，用来连上云端的文件仓库
import os  # 正经注释：操作系统接口模块，用于拼接本地文件路径 / 大白话注释：用来处理文件路径
import tempfile  # 正经注释：临时文件模块，用于创建临时目录存放下载的文件 / 大白话注释：创建临时文件夹用的，下载的文件先放这里


class AzureDocumentLoader:
    """
    Azure Blob 存储文档加载器

    【正经注释】
    该类封装了 Azure Blob Storage 的文件下载逻辑，支持从指定容器中批量下载所有 Blob 文件到本地临时目录。
    返回的文件路径列表可直接传递给 DocumentLoader 进行后续的文档内容解析。

    【大白话注释】
    专门从 Azure 云上下载文件的工具。连上云存储后，把里面的文件全都拉到本地，
    然后告诉你文件放在哪了，方便别的程序去读。
    """

    def __init__(self, container_name, connection_string):
        """
        初始化 Azure 文档加载器

        【正经注释】
        通过连接字符串创建 BlobServiceClient 实例，并获取指定容器的客户端对象。
        connection_string 需要包含 Azure 存储账户的完整认证信息。

        参数:
            container_name: Azure Blob 存储中的容器名称
            connection_string: Azure 存储账户的连接字符串（含认证信息）

        【大白话注释】
        初始化的时候需要告诉它两件事：容器叫啥名、连接密码（连接字符串）是啥。
        它会用这些信息连上你的 Azure 云存储。
        """
        self.client = BlobServiceClient.from_connection_string(connection_string)  # 正经注释：通过连接字符串创建 Blob 服务客户端 / 大白话注释：用连接密码连上 Azure 云存储
        self.container = self.client.get_container_client(container_name)  # 正经注释：获取指定容器的客户端实例 / 大白话注释：找到你要的那个文件容器（类似文件夹）

    async def load(self):
        """
        下载容器中所有 Blob 文件到本地临时目录

        【正经注释】
        创建临时目录后，遍历容器中的所有 Blob 对象，
        逐个下载到本地并记录文件路径。最终返回所有已下载文件的本地路径列表，
        该列表可直接传递给 DocumentLoader 进行文档内容解析。

        返回:
            list: 已下载文件的本地路径列表

        【大白话注释】
        把云上容器里所有文件都下载到本地一个临时文件夹里。
        下载完了把所有文件路径列出来交给你，方便后面去读这些文件。
        """
        """Download all blobs to temp files and return their paths."""
        temp_dir = tempfile.mkdtemp()  # 正经注释：创建临时目录用于存放下载的文件 / 大白话注释：建一个临时文件夹来装下载的文件
        blobs = self.container.list_blobs()  # 正经注释：列出容器中所有 Blob 对象 / 大白话注释：看看云上的容器里都有哪些文件
        file_paths = []  # 正经注释：初始化文件路径列表 / 大白话注释：准备一个空列表来记下载的文件路径
        for blob in blobs:  # 正经注释：遍历容器中的每个 Blob / 大白话注释：一个文件一个文件来处理
            blob_client = self.container.get_blob_client(blob.name)  # 正经注释：获取当前 Blob 的客户端实例 / 大白话注释：拿到这个文件的下载句柄
            local_path = os.path.join(temp_dir, blob.name)  # 正经注释：拼接本地存储路径 / 大白话注释：确定这个文件下载后放在本地的哪个位置
            with open(local_path, "wb") as f:  # 正经注释：以二进制写入模式打开本地文件 / 大白话注释：打开本地文件准备写入
                blob_data = blob_client.download_blob()  # 正经注释：下载 Blob 数据 / 大白话注释：从云上把这个文件下载下来
                f.write(blob_data.readall())  # 正经注释：将下载的数据全部写入本地文件 / 大白话注释：把下载的内容写进本地文件里
            file_paths.append(local_path)  # 正经注释：记录已下载文件的本地路径 / 大白话注释：把这个文件的路径记下来
        return file_paths  # Pass to existing DocumentLoader  # 正经注释：返回所有已下载文件的路径列表，可传递给 DocumentLoader 做后续解析 / 大白话注释：把所有文件路径交出去，让 DocumentLoader 去读