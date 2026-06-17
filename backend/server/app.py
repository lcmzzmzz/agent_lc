"""
FastAPI 主应用模块

【正经注释】
本模块是 GPT Researcher 后端服务的入口文件，基于 FastAPI 框架构建。
定义了所有 HTTP 路由（RESTful API）和 WebSocket 端点，涵盖以下核心功能：
- 前端页面托管与静态资源服务
- Agent Discovery Protocol 服务发现
- 研究报告的 CRUD 操作（创建、读取、更新、删除）
- 报告生成（支持同步和后台异步两种模式）
- 文件上传与管理
- 多代理研究任务执行
- WebSocket 实时通信（研究进度流式推送）
- 对话式问答（基于报告上下文）
同时配置了 CORS 跨域中间件、日志系统和应用生命周期管理。

【大白话注释】
这个文件是整个后端的"心脏"，几乎所有对外提供的接口都在这里定义。
前端能做什么事情，全看这里暴露了哪些接口：
- 打开网页看界面
- 提交研究任务、查看/修改/删除研究报告
- 上传文件、删除文件
- 通过 WebSocket 实时看研究进度
- 对着研究报告问问题、聊天
- 让一组 AI 协作做研究
还配置了跨域访问（让前端能从不同端口调用后端）和日志记录等基础设施。
"""
import json  # 正经注释：导入 JSON 序列化库 / 大白话注释：读写 JSON 的工具
import os  # 正经注释：导入操作系统接口模块 / 大白话注释：操作文件和目录的工具
from typing import Dict, List, Any  # 正经注释：导入类型提示相关 / 大白话注释：告诉 Python 变量是啥类型
import time  # 正经注释：导入时间模块用于时间戳生成 / 大白话注释：获取时间的工具
import logging  # 正经注释：导入日志模块 / 大白话注释：记日志的工具
import sys  # 正经注释：导入系统模块用于路径操作 / 大白话注释：用来改 Python 找模块的路径
import warnings  # 正经注释：导入警告控制模块 / 大白话注释：用来屏蔽烦人的警告信息
from pathlib import Path  # 正经注释：导入路径操作类 / 大白话注释：更方便地处理文件路径

# Suppress Pydantic V2 migration warnings
warnings.filterwarnings("ignore", message="Valid config keys have changed in V2")  # 正经注释：屏蔽 Pydantic V2 迁移警告 / 大白话注释：把 Pydantic 升级带来的烦人警告关掉
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")  # 正经注释：屏蔽 Pydantic 用户警告 / 大白话注释：把 Pydantic 的用户警告也关掉

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, File, UploadFile, BackgroundTasks, HTTPException  # 正经注释：导入 FastAPI 核心组件 / 大白话注释：FastAPI 的各种工具——请求、WebSocket、文件上传、后台任务等
from contextlib import asynccontextmanager  # 正经注释：导入异步上下文管理器装饰器 / 大白话注释：用来管理应用启动和关闭时的操作
from fastapi.middleware.cors import CORSMiddleware  # 正经注释：导入 CORS 跨域中间件 / 大白话注释：让前端能从不同端口访问后端
from fastapi.staticfiles import StaticFiles  # 正经注释：导入静态文件服务 / 大白话注释：用来托管前端文件（HTML/CSS/JS）
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse  # 正经注释：导入各种响应类型 / 大白话注释：返回文件、JSON、HTML 等不同类型的响应
from pydantic import BaseModel, ConfigDict  # 正经注释：导入 Pydantic 数据模型基类 / 大白话注释：用来定义请求参数的数据结构

# Add the parent directory to sys.path to make sure we can import from server
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))  # 正经注释：将上级目录加入模块搜索路径 / 大白话注释：让 Python 能找到 server 包

from server.websocket_manager import WebSocketManager  # 正经注释：导入 WebSocket 管理器 / 大白话注释：管 WebSocket 连接的工具
from server.server_utils import (  # 正经注释：从工具模块导入各种辅助函数 / 大白话注释：把"工具箱"里的工具拿出来
    get_config_dict, sanitize_filename,
    update_environment_variables, handle_file_upload, handle_file_deletion,
    execute_multi_agents, handle_websocket_communication
)
from server.agent_discovery import build_agent_discovery_document  # 正经注释：导入 Agent Discovery 文档构建函数 / 大白话注释：拿来拼装"名片"的函数

from server.websocket_manager import run_agent  # 正经注释：导入核心研究执行函数 / 大白话注释：让研究引擎跑起来的函数
from utils import write_md_to_word, write_md_to_pdf  # 正经注释：导入报告格式转换工具 / 大白话注释：把报告转成 Word 和 PDF 的工具
from gpt_researcher.utils.enum import Tone  # 正经注释：导入语气枚举类型 / 大白话注释：报告语气的选项
from chat.chat import ChatAgentWithMemory  # 正经注释：导入带记忆的对话代理 / 大白话注释：能记住聊天记录的 AI 对话助手

from server.report_store import ReportStore  # 正经注释：导入报告存储管理器 / 大白话注释：管报告存取的"仓库"

# MongoDB services removed - no database persistence needed  # 正经注释：MongoDB 相关服务已移除，不需要数据库持久化 / 大白话注释：以前用 MongoDB 存数据，现在不用了

# Setup logging
logger = logging.getLogger(__name__)  # 正经注释：获取当前模块的日志记录器 / 大白话注释：给这个模块准备一个"记事本"

# Don't override parent logger settings
logger.propagate = True  # 正经注释：允许日志传播到父 Logger / 大白话注释：让日志也显示在上层的日志器里

# Silence uvicorn reload logs
logging.getLogger("uvicorn.supervisors.ChangeReload").setLevel(logging.WARNING)  # 正经注释：降低 uvicorn 热重载日志级别 / 大白话注释：把 uvicorn 热重载时的刷屏日志关掉

# Models


class ResearchRequest(BaseModel):
    """
    研究请求数据模型。

    【正经注释】
    定义了提交研究任务时所需的所有参数，包括任务描述、报告类型、来源、语气等。
    继承自 Pydantic BaseModel，提供自动的请求体验证和序列化。

    【大白话注释】
    前端发来"帮我做个研究"请求时，数据长什么样都在这里定义了：
    - task：研究什么问题
    - report_type：要什么类型的报告
    - report_source：从哪里查资料
    - tone：用啥语气写
    - 等等
    """
    task: str  # 正经注释：研究任务描述 / 大白话注释：要研究啥问题
    report_type: str  # 正经注释：报告类型 / 大白话注释：报告啥格式
    report_source: str  # 正经注释：报告来源类型 / 大白话注释：从哪里查资料
    tone: str  # 正经注释：报告语气 / 大白话注释：用啥语气写
    headers: dict | None = None  # 正经注释：可选的 HTTP 请求头 / 大白话注释：额外的请求头，一般不用
    repo_name: str  # 正经注释：仓库名称 / 大白话注释：Git 仓库名
    branch_name: str  # 正经注释：分支名称 / 大白话注释：Git 分支名
    generate_in_background: bool = True  # 正经注释：是否在后台生成报告 / 大白话注释：要不要在后台慢慢跑，默认是的


class ChatRequest(BaseModel):
    """
    对话请求数据模型。

    【正经注释】
    定义了发起对话请求时的参数，包含报告文本和消息历史列表。
    使用 ConfigDict(extra="allow") 允许请求体中包含额外字段。

    【大白话注释】
    前端发来"跟报告对话"请求时的数据格式：
    - report：关联的研究报告
    - messages：之前的聊天记录
    还允许带额外的字段，不会报错。
    """
    model_config = ConfigDict(extra="allow")  # Allow extra fields in the request  # 正经注释：允许请求体包含额外字段 / 大白话注释：前端多传了字段也不报错

    report: str  # 正经注释：报告文本 / 大白话注释：关联的研究报告
    messages: List[Dict[str, Any]]  # 正经注释：消息历史列表 / 大白话注释：之前的聊天记录


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理上下文。

    【正经注释】
    使用异步上下文管理器管理应用的启动和关闭生命周期。
    启动时创建输出目录、挂载输出文件和前端静态资源的路由。
    关闭时记录日志。

    【大白话注释】
    这是应用"开机关机"时要干的事：
    - 开机：建好 outputs 文件夹、把前端文件挂上来让用户能访问
    - 关机：记个日志说"我要关了"

    Args:
        app: FastAPI 应用实例
    """
    # Startup
    os.makedirs("outputs", exist_ok=True)  # 正经注释：创建输出目录 / 大白话注释：确保 outputs 文件夹存在
    app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")  # 正经注释：挂载输出文件静态服务 / 大白话注释：让用户能通过网页下载生成的报告文件

    # Mount frontend static files
    frontend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend")  # 正经注释：计算前端文件目录路径 / 大白话注释：找到前端文件在哪
    if os.path.exists(frontend_path):  # 正经注释：检查前端目录是否存在 / 大白话注释：前端文件夹在不在
        app.mount("/site", StaticFiles(directory=frontend_path), name="frontend")  # 正经注释：挂载前端静态文件 / 大白话注释：让用户能访问前端页面
        logger.debug(f"Frontend mounted from: {frontend_path}")

        # Also mount the static directory directly for assets referenced as /static/
        static_path = os.path.join(frontend_path, "static")  # 正经注释：构造静态资源子目录路径 / 大白话注释：前端静态资源（CSS/JS等）的路径
        if os.path.exists(static_path):  # 正经注释：检查静态资源目录是否存在 / 大白话注释：看看有没有 static 文件夹
            app.mount("/static", StaticFiles(directory=static_path), name="static")  # 正经注释：挂载静态资源服务 / 大白话注释：让 /static/ 路径能访问 CSS/JS
            logger.debug(f"Static assets mounted from: {static_path}")
    else:
        logger.warning(f"Frontend directory not found: {frontend_path}")  # 正经注释：前端目录未找到则记录警告 / 大白话注释：找不到前端文件就提醒一下

    logger.info("GPT Researcher API ready - local mode (no database persistence)")  # 正经注释：记录应用就绪日志 / 大白话注释：告诉控制台"服务准备好了"
    yield  # 正经注释：yield 之前的代码在启动时执行，之后的在关闭时执行 / 大白话注释：这里是分界线——上面是开机，下面是关机
    # Shutdown
    logger.info("Research API shutting down")  # 正经注释：记录关闭日志 / 大白话注释：告诉控制台"我要关了"

# App initialization
app = FastAPI(lifespan=lifespan)  # 正经注释：创建 FastAPI 应用实例并绑定生命周期管理 / 大白话注释：把"开机关机"流程告诉 FastAPI

# Configure allowed origins for CORS
allowed_origins_env = os.getenv("CORS_ALLOW_ORIGINS")  # 正经注释：从环境变量获取允许的跨域来源 / 大白话注释：看看环境变量里有没有配允许哪些网站跨域访问
ALLOWED_ORIGINS = (  # 正经注释：解析允许的跨域来源列表 / 大白话注释：整理出允许跨域访问的网站名单
    [o.strip() for o in allowed_origins_env.split(",") if o.strip()]  # 正经注释：按逗号分割并去空白 / 大白话注释：把环境变量按逗号拆开，去掉空格
    if allowed_origins_env
    else [  # 正经注释：环境变量未设置时使用默认值 / 大白话注释：没配的话就用默认的几个地址
        "http://localhost:3000",  # 正经注释：本地开发前端默认地址 / 大白话注释：前端开发服务器的默认地址
        "http://127.0.0.1:3000",  # 正经注释：本地 IP 形式的前端地址 / 大白话注释：跟上面一样，换个写法
        "https://app.gptr.dev",  # 正经注释：生产环境前端地址 / 大白话注释：线上环境的前端地址
    ]
)

# Standard JSON response - no custom MongoDB encoding needed  # 正经注释：使用标准 JSON 响应，无需自定义 MongoDB 编码 / 大白话注释：不用数据库了，普通 JSON 就行

# Add CORS middleware
app.add_middleware(  # 正经注释：添加 CORS 中间件 / 大白话注释：把跨域访问的规则加上去
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # 正经注释：允许的来源列表 / 大白话注释：这些网站可以跨域访问
    allow_credentials=True,  # 正经注释：允许携带凭据 / 大白话注释：允许带 Cookie 之类的认证信息
    allow_methods=["*"],  # 正经注释：允许所有 HTTP 方法 / 大白话注释：GET、POST、PUT、DELETE 都行
    allow_headers=["*"],  # 正经注释：允许所有请求头 / 大白话注释：请求头随便带
)

# Use default JSON response class  # 正经注释：使用默认的 JSON 响应类 / 大白话注释：就用 FastAPI 自带的 JSON 返回方式

# Mount static files for frontend
# Get the absolute path to the frontend directory
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))  # 正经注释：计算前端目录的绝对路径 / 大白话注释：找到前端文件在哪

# Mount static directories
app.mount("/static", StaticFiles(directory=os.path.join(frontend_dir, "static")), name="static")  # 正经注释：挂载 /static 静态资源路由 / 大白话注释：让 /static/ 路径能访问前端静态文件
app.mount("/site", StaticFiles(directory=frontend_dir), name="site")  # 正经注释：挂载 /site 前端路由 / 大白话注释：让 /site 路径能访问前端页面

# WebSocket manager
manager = WebSocketManager()  # 正经注释：创建 WebSocket 管理器实例 / 大白话注释：把"前台接待员"叫来

report_store = ReportStore(Path(os.getenv('REPORT_STORE_PATH', os.path.join('data', 'reports.json'))))  # 正经注释：创建报告存储实例，支持自定义存储路径 / 大白话注释：建一个"报告仓库"，默认把报告存在 data/reports.json 里

# Constants
DOC_PATH = os.getenv("DOC_PATH", "./my-docs")  # 正经注释：文档存储路径常量 / 大白话注释：用户上传的文档放在哪，默认是 my-docs 文件夹

# Startup event


# Lifespan events now handled in the lifespan context manager above  # 正经注释：启动事件已在上方生命周期管理器中处理 / 大白话注释：开机的活在上面那个函数里干了


# Routes
@app.get("/", response_class=HTMLResponse)  # 正经注释：定义根路径 GET 路由，返回 HTML / 大白话注释：访问首页时显示前端页面
async def serve_frontend():
    """
    提供前端主页 HTML 页面。

    【正经注释】
    读取前端 index.html 文件内容并以 HTMLResponse 形式返回。
    如果文件不存在则返回 404 错误。

    【大白话注释】
    当用户打开网站首页时，把前端的主页面（index.html）读出来显示给用户。
    如果前端文件没了就报 404 错误。

    Returns:
        HTMLResponse: 前端 HTML 页面内容

    Raises:
        HTTPException: 前端文件不存在时返回 404
    """
    """Serve the main frontend HTML page."""
    frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))  # 正经注释：计算前端目录路径 / 大白话注释：找到前端文件夹
    index_path = os.path.join(frontend_dir, "index.html")  # 正经注释：构造 index.html 的完整路径 / 大白话注释：找到首页文件

    if not os.path.exists(index_path):  # 正经注释：检查文件是否存在 / 大白话注释：文件在不在
        raise HTTPException(status_code=404, detail="Frontend index.html not found")  # 正经注释：文件不存在则抛出 404 异常 / 大白话注释：没了就报 404

    with open(index_path, "r", encoding="utf-8") as f:  # 正经注释：以 UTF-8 编码读取 HTML 文件 / 大白话注释：打开首页文件读内容
        content = f.read()

    return HTMLResponse(content=content)  # 正经注释：返回 HTML 响应 / 大白话注释：把首页内容返回给用户


@app.get("/.well-known/agent-discovery.json")  # 正经注释：定义 Agent Discovery 协议端点 / 大白话注释：别人来问"你能干啥"时的接口
async def agent_discovery(request: Request):
    """
    提供 Agent Discovery Protocol 服务发现端点。

    【正经注释】
    根据 Agent Discovery Protocol 规范，构建并返回描述本服务所有能力的 JSON 文档。
    同时设置 Access-Control-Allow-Origin 头允许跨域访问。

    【大白话注释】
    当别的系统来问"你这服务能干啥"时，把咱的"名片"掏出来：
    列出所有能提供的服务（做研究、管报告、聊天、实时推送等），
    并允许任何人来查。

    Args:
        request: FastAPI Request 对象

    Returns:
        JSONResponse: Agent Discovery 文档
    """
    """Advertise GPT Researcher services via the Agent Discovery Protocol."""
    origin = str(request.base_url).rstrip("/")  # 正经注释：获取并规范化服务基础 URL / 大白话注释：拿到自己的网址
    domain = request.url.hostname or request.headers.get("host", "")  # 正经注释：获取域名或 host 头 / 大白话注释：拿到域名
    contact = os.getenv("AGENT_DISCOVERY_CONTACT")  # 正经注释：从环境变量获取联系方式 / 大白话注释：看看有没有配联系人信息

    document = build_agent_discovery_document(origin=origin, domain=domain, contact=contact)  # 正经注释：构建发现文档 / 大白话注释：拼装"名片"
    response = JSONResponse(content=document)  # 正经注释：创建 JSON 响应 / 大白话注释：把"名片"包成响应
    response.headers["Access-Control-Allow-Origin"] = "*"  # 正经注释：设置允许所有来源的跨域访问 / 大白话注释：谁都能来看这张"名片"
    return response

@app.get("/report/{research_id}")  # 正经注释：定义报告文件下载路由 / 大白话注释：下载某份报告的 Word 文件
async def read_report(request: Request, research_id: str):
    """
    下载指定研究报告的 Word 文档。

    【正经注释】
    根据 research_id 查找对应的 .docx 文件，存在则返回文件下载响应，否则返回提示消息。

    【大白话注释】
    给个研究报告的 ID，就能下载它的 Word 文件。
    文件不存在的话就告诉你"找不到"。

    Args:
        request: FastAPI Request 对象
        research_id: 研究报告的唯一标识

    Returns:
        FileResponse 或 dict: 文件下载响应或未找到提示
    """
    docx_path = os.path.join('outputs', f"{research_id}.docx")  # 正经注释：构造 Word 文件路径 / 大白话注释：拼出 Word 文件的完整路径
    if not os.path.exists(docx_path):  # 正经注释：检查文件是否存在 / 大白话注释：文件在不在
        return {"message": "Report not found."}  # 正经注释：文件不存在返回提示 / 大白话注释：告诉你找不到
    return FileResponse(docx_path)  # 正经注释：返回文件下载响应 / 大白话注释：把文件给你下载


# Simplified API routes - no database persistence
@app.get("/api/reports")  # 正经注释：定义获取报告列表 API / 大白话注释：查所有报告的接口
async def get_all_reports(report_ids: str = None):
    """
    获取报告列表。

    【正经注释】
    支持通过逗号分隔的 report_ids 参数过滤返回结果。
    未指定 IDs 时返回所有报告。

    【大白话注释】
    拿报告列表。你可以传几个 ID（用逗号隔开），只拿这几份；
    不传 ID 就返回所有报告。

    Args:
        report_ids: 可选的逗号分隔报告 ID 字符串

    Returns:
        dict: 包含 reports 列表的字典
    """
    report_ids_list = report_ids.split(",") if report_ids else None  # 正经注释：解析逗号分隔的 ID 列表 / 大白话注释：把逗号隔开的 ID 拆成列表
    reports = await report_store.list_reports(report_ids_list)  # 正经注释：从存储中获取报告列表 / 大白话注释：从仓库里拿报告
    return {"reports": reports}  # 正经注释：返回报告列表 / 大白话注释：把报告打包交出去


@app.get("/api/reports/{research_id}")  # 正经注释：定义获取单个报告 API / 大白话注释：查某一份报告的接口
async def get_report_by_id(research_id: str):
    """
    根据 ID 获取单个研究报告。

    【正经注释】
    从报告存储中查找指定 ID 的报告，不存在时返回 404 错误。

    【大白话注释】
    给个报告 ID，返回那一份报告的详细内容。
    找不到就报 404 错误。

    Args:
        research_id: 研究报告 ID

    Returns:
        dict: 包含 report 数据的字典

    Raises:
        HTTPException: 报告不存在时返回 404
    """
    report = await report_store.get_report(research_id)  # 正经注释：从存储中获取指定报告 / 大白话注释：从仓库里找那份报告
    if report is None:  # 正经注释：报告不存在则抛出 404 / 大白话注释：找不到就报错
        raise HTTPException(status_code=404, detail="Report not found")
    return {"report": report}  # 正经注释：返回报告数据 / 大白话注释：把报告交出去


@app.post("/api/reports")  # 正经注释：定义创建/更新报告 API / 大白话注释：新建或更新报告的接口
async def create_or_update_report(request: Request):
    """
    创建或更新研究报告。

    【正经注释】
    接收 JSON 请求体创建新报告或更新已有报告。自动处理时间戳合并逻辑：
    取传入时间戳和已有时间戳中的较大值，确保时间戳不会回退。

    【大白话注释】
    存一份报告。如果已有同 ID 的报告，就合并数据（时间戳取最新的）。
    出错了就返回 500 错误。

    Args:
        request: FastAPI Request 对象

    Returns:
        dict: 包含 success 标志和报告 ID 的字典

    Raises:
        HTTPException: 处理失败时返回 500
    """
    try:
        data = await request.json()  # 正经注释：解析请求体 JSON / 大白话注释：把前端发来的数据读出来
        research_id = data.get("id", "temp_id")  # 正经注释：获取报告 ID，默认为 temp_id / 大白话注释：拿到报告编号，没有的话用临时 ID

        now_ms = int(time.time() * 1000)  # 正经注释：获取当前毫秒级时间戳 / 大白话注释：现在几点（精确到毫秒）
        existing = await report_store.get_report(research_id)  # 正经注释：查询是否已有同 ID 报告 / 大白话注释：看看仓库里有没有这份报告
        incoming_timestamp = data.get("timestamp")  # 正经注释：获取传入的时间戳 / 大白话注释：前端传过来的时间
        timestamp = incoming_timestamp if isinstance(incoming_timestamp, int) else now_ms  # 正经注释：使用传入时间戳或当前时间 / 大白话注释：前端给了有效时间就用前端的，否则用现在的
        if existing and isinstance(existing.get("timestamp"), int):  # 正经注释：已有报告的时间戳合并逻辑 / 大白话注释：如果仓库里已经有且有时间戳
            timestamp = max(timestamp, existing["timestamp"])  # 正经注释：取较大值防止时间戳回退 / 大白话注释：用最新的那个时间

        report = {  # 正经注释：构建报告数据字典 / 大白话注释：把报告数据整理好
            "id": research_id,
            "question": data.get("question"),
            "answer": data.get("answer"),
            "orderedData": data.get("orderedData") or [],
            "chatMessages": data.get("chatMessages") or [],
            "timestamp": timestamp,
        }

        await report_store.upsert_report(research_id, report)  # 正经注释：存储或更新报告 / 大白话注释：把报告存进仓库
        return {"success": True, "id": research_id}  # 正经注释：返回成功响应 / 大白话注释：告诉前端"存好了"
    except Exception as e:  # 正经注释：捕获所有异常 / 大白话注释：出错了
        logger.error(f"Error processing report creation: {e}")
        raise HTTPException(status_code=500, detail=str(e))  # 正经注释：返回 500 错误 / 大白话注释：告诉前端出问题了


@app.put("/api/reports/{research_id}")  # 正经注释：定义更新报告 API（PUT 方法） / 大白话注释：修改某份报告的接口
async def update_report(research_id: str, request: Request):
    """
    更新指定的研究报告。

    【正经注释】
    合并已有报告数据和新传入的数据，自动更新时间戳。
    新传入的非 None 字段会覆盖已有数据。

    【大白话注释】
    修改一份已有的报告。新旧数据合并，新的不为空的字段覆盖旧的，
    时间戳更新为当前时间。

    Args:
        research_id: 研究报告 ID
        request: FastAPI Request 对象

    Returns:
        dict: 包含 success 标志和报告 ID 的字典

    Raises:
        HTTPException: 报告不存在时返回 404
    """
    existing = await report_store.get_report(research_id)  # 正经注释：获取已有报告 / 大白话注释：先看看仓库里有没有
    if existing is None:  # 正经注释：报告不存在则返回 404 / 大白话注释：没有就报错
        raise HTTPException(status_code=404, detail="Report not found")

    data = await request.json()  # 正经注释：解析请求体 / 大白话注释：读出前端发来的新数据
    now_ms = int(time.time() * 1000)  # 正经注释：获取当前毫秒时间戳 / 大白话注释：现在几点

    updated = {  # 正经注释：合并新旧数据 / 大白话注释：把新旧数据混在一起，新的覆盖旧的
        **existing,  # 正经注释：展开已有数据 / 大白话注释：先铺上旧数据
        **{k: v for k, v in data.items() if v is not None},  # 正经注释：覆盖非 None 的新数据 / 大白话注释：再把不为空的新数据盖上去
        "id": research_id,  # 正经注释：确保 ID 不被覆盖 / 大白话注释：ID 一定不能变
        "timestamp": now_ms,  # 正经注释：更新时间戳 / 大白话注释：记下修改时间
    }

    await report_store.upsert_report(research_id, updated)  # 正经注释：存储更新后的报告 / 大白话注释：把改好的报告存回去
    return {"success": True, "id": research_id}  # 正经注释：返回成功 / 大白话注释：告诉前端"改好了"


@app.delete("/api/reports/{research_id}")  # 正经注释：定义删除报告 API / 大白话注释：删掉某份报告的接口
async def delete_report(research_id: str):
    """
    删除指定的研究报告。

    【正经注释】
    从存储中删除指定 ID 的报告。如果报告不存在则返回 404 错误。

    【大白话注释】
    删掉一份报告。报告不存在就报 404 错误。

    Args:
        research_id: 研究报告 ID

    Returns:
        dict: 包含 success 标志的字典

    Raises:
        HTTPException: 报告不存在时返回 404
    """
    existed = await report_store.delete_report(research_id)  # 正经注释：从存储中删除报告 / 大白话注释：从仓库里删掉
    if not existed:  # 正经注释：报告不存在则返回 404 / 大白话注释：原来就没有
        raise HTTPException(status_code=404, detail="Report not found")
    return {"success": True}  # 正经注释：返回成功 / 大白话注释：告诉前端"删好了"


@app.get("/api/reports/{research_id}/chat")  # 正经注释：定义获取报告对话历史 API / 大白话注释：查看某份报告的聊天记录
async def get_report_chat(research_id: str):
    """
    获取指定报告的对话消息历史。

    【正经注释】
    从报告中提取 chatMessages 字段，返回该报告关联的所有对话消息列表。

    【大白话注释】
    拿到某份报告下面的所有聊天记录。报告不存在就报 404。

    Args:
        research_id: 研究报告 ID

    Returns:
        dict: 包含 chatMessages 列表的字典

    Raises:
        HTTPException: 报告不存在时返回 404
    """
    report = await report_store.get_report(research_id)  # 正经注释：获取报告数据 / 大白话注释：先从仓库拿报告
    if report is None:  # 正经注释：报告不存在则返回 404 / 大白话注释：没有就报错
        raise HTTPException(status_code=404, detail="Report not found")
    return {"chatMessages": report.get("chatMessages") or []}  # 正经注释：返回对话消息列表 / 大白话注释：把聊天记录交出去，没有就返回空的


@app.post("/api/reports/{research_id}/chat")  # 正经注释：定义添加报告对话消息 API / 大白话注释：给某份报告的聊天加一条消息
async def add_report_chat_message(research_id: str, request: Request):
    """
    向指定报告追加一条对话消息。

    【正经注释】
    接收一条新消息，追加到报告的 chatMessages 列表中，并更新时间戳。
    如果 chatMessages 不是列表类型则重新初始化。

    【大白话注释】
    给某份报告的聊天记录里加一条新消息。
    如果之前的聊天记录格式不对（不是列表），就重新建一个。

    Args:
        research_id: 研究报告 ID
        request: FastAPI Request 对象

    Returns:
        dict: 包含 success 标志和报告 ID 的字典

    Raises:
        HTTPException: 报告不存在时返回 404
    """
    report = await report_store.get_report(research_id)  # 正经注释：获取报告数据 / 大白话注释：先从仓库拿报告
    if report is None:  # 正经注释：报告不存在则返回 404 / 大白话注释：没有就报错
        raise HTTPException(status_code=404, detail="Report not found")

    message = await request.json()  # 正经注释：解析新消息 / 大白话注释：读出新消息内容
    chat_messages = report.get("chatMessages") or []  # 正经注释：获取已有的聊天记录 / 大白话注释：先看看之前聊了啥
    if isinstance(chat_messages, list):  # 正经注释：已有记录是列表则追加 / 大白话注释：格式对的话就在后面加
        chat_messages = [*chat_messages, message]
    else:
        chat_messages = [message]  # 正经注释：格式不对则重新初始化 / 大白话注释：格式不对就只放这一条

    now_ms = int(time.time() * 1000)  # 正经注释：获取当前毫秒时间戳 / 大白话注释：现在几点
    updated = {  # 正经注释：构建更新后的报告数据 / 大白话注释：把改好的数据整理好
        **report,  # 正经注释：展开已有报告数据 / 大白话注释：先铺上原来的数据
        "chatMessages": chat_messages,  # 正经注释：更新聊天记录 / 大白话注释：把新的聊天记录放上去
        "timestamp": now_ms,  # 正经注释：更新时间戳 / 大白话注释：记下修改时间
    }

    await report_store.upsert_report(research_id, updated)  # 正经注释：存储更新后的报告 / 大白话注释：存回仓库
    return {"success": True, "id": research_id}  # 正经注释：返回成功 / 大白话注释：告诉前端"加好了"


async def write_report(research_request: ResearchRequest, research_id: str = None):
    """
    执行研究报告生成。

    【正经注释】
    调用 run_agent 执行研究任务，获取报告文本和研究者实例，
    然后生成 Word 和 PDF 格式的报告文件。
    对于非多代理类型，还会收集来源 URL、费用、已访问 URL 和研究图片等元数据。

    【大白话注释】
    这是"写报告"的核心流程：
    1. 让研究引擎跑起来，拿到报告内容
    2. 把报告转成 Word 和 PDF 文件
    3. 如果不是多代理模式，还要收集一堆额外信息（查了哪些网站、花了多少钱等）
    最后把所有信息打包返回。

    Args:
        research_request: 研究请求参数
        research_id: 可选的研究报告 ID

    Returns:
        dict: 包含报告内容、文件路径和元数据的字典
    """
    report_information = await run_agent(  # 正经注释：执行研究任务并获取报告 / 大白话注释：让研究引擎开始干活
        task=research_request.task,
        report_type=research_request.report_type,
        report_source=research_request.report_source,
        source_urls=[],
        document_urls=[],
        tone=Tone[research_request.tone],
        websocket=None,  # 正经注释：不通过 WebSocket 推送 / 大白话注释：不实时推送，直接等结果
        stream_output=None,
        headers=research_request.headers,
        query_domains=[],
        config_path="",
        return_researcher=True  # 正经注释：要求返回研究者实例以获取元数据 / 大白话注释：把研究引擎本身也拿出来看看
    )

    docx_path = await write_md_to_word(report_information[0], research_id)  # 正经注释：生成 Word 文件 / 大白话注释：转成 Word
    pdf_path = await write_md_to_pdf(report_information[0], research_id)  # 正经注释：生成 PDF 文件 / 大白话注释：转成 PDF
    if research_request.report_type != "multi_agents":  # 正经注释：非多代理模式收集额外信息 / 大白话注释：不是一群 AI 干的活，就多收集点信息
        report, researcher = report_information  # 正经注释：解包报告和研究器 / 大白话注释：把报告和引擎分开
        response = {  # 正经注释：构建完整响应 / 大白话注释：把所有信息打包
            "research_id": research_id,
            "research_information": {
                "source_urls": researcher.get_source_urls(),  # 正经注释：获取来源 URL / 大白话注释：查了哪些资料来源
                "research_costs": researcher.get_costs(),  # 正经注释：获取研究花费 / 大白话注释：花了多少钱
                "visited_urls": list(researcher.visited_urls),  # 正经注释：获取已访问的 URL / 大白话注释：实际去了哪些网站
                "research_images": researcher.get_research_images(),  # 正经注释：获取研究相关图片 / 大白话注释：找到了哪些图片
                # "research_sources": researcher.get_research_sources(),  # Raw content of sources may be very large  # 正经注释：原始来源内容可能太大已注释掉 / 大白话注释：原始网页内容太多了，先不返回了
            },
            "report": report,  # 正经注释：报告文本 / 大白话注释：报告内容
            "docx_path": docx_path,  # 正经注释：Word 文件路径 / 大白话注释：Word 文件在哪
            "pdf_path": pdf_path  # 正经注释：PDF 文件路径 / 大白话注释：PDF 文件在哪
        }
    else:
        response = { "research_id": research_id, "report": "", "docx_path": docx_path, "pdf_path": pdf_path }  # 正经注释：多代理模式返回简化响应 / 大白话注释：多代理模式只返回文件路径

    return response  # 正经注释：返回响应 / 大白话注释：把结果交出去

@app.post("/report/")  # 正经注释：定义报告生成 API / 大白话注释：提交研究任务的接口
async def generate_report(research_request: ResearchRequest, background_tasks: BackgroundTasks):
    """
    生成研究报告。

    【正经注释】
    接收研究请求参数，生成安全的文件名。如果请求指定后台生成，
    则将任务添加到 FastAPI 后台任务队列；否则同步等待报告生成完成。

    【大白话注释】
    提交一个研究任务。有两种模式：
    - 后台模式（默认）：把任务扔到后台慢慢跑，先告诉你"在做了"
    - 同步模式：等着做完才返回结果

    Args:
        research_request: 研究请求参数
        background_tasks: FastAPI 后台任务管理器

    Returns:
        dict: 报告生成结果或后台任务提示
    """
    research_id = sanitize_filename(f"task_{int(time.time())}_{research_request.task}")  # 正经注释：生成安全的报告 ID / 大白话注释：把文件名处理好当 ID 用

    if research_request.generate_in_background:  # 正经注释：检查是否后台生成 / 大白话注释：要不要在后台跑
        background_tasks.add_task(write_report, research_request=research_request, research_id=research_id)  # 正经注释：添加到后台任务队列 / 大白话注释：把任务扔到后台
        return {"message": "Your report is being generated in the background. Please check back later.",  # 正经注释：返回后台任务提示 / 大白话注释：告诉前端"在做了，回头来看"
                "research_id": research_id}
    else:
        response = await write_report(research_request, research_id)  # 正经注释：同步等待报告生成 / 大白话注释：等着做完
        return response


@app.get("/files/")  # 正经注释：定义文件列表 API / 大白话注释：查看上传了哪些文件的接口
async def list_files():
    """
    列出文档目录中的所有文件。

    【正经注释】
    返回 DOC_PATH 目录下所有文件的文件名列表。
    如果目录不存在则自动创建。

    【大白话注释】
    看看文档文件夹里有哪些文件。文件夹不存在就先建一个。

    Returns:
        dict: 包含 files 列表的字典
    """
    if not os.path.exists(DOC_PATH):  # 正经注释：检查文档目录是否存在 / 大白话注释：文件夹在不在
        os.makedirs(DOC_PATH, exist_ok=True)  # 正经注释：不存在则创建 / 大白话注释：不在就建一个
    files = os.listdir(DOC_PATH)  # 正经注释：列出目录下所有文件 / 大白话注释：把文件名都拿出来
    print(f"Files in {DOC_PATH}: {files}")  # 正经注释：打印文件列表 / 大白话注释：在控制台显示一下
    return {"files": files}  # 正经注释：返回文件列表 / 大白话注释：把文件名交出去


@app.post("/api/multi_agents")  # 正经注释：定义多代理研究 API / 大白话注释：让一群 AI 协作做研究的接口
async def run_multi_agents():
    """
    执行多代理研究任务。

    【正经注释】
    使用 WebSocketManager 的活跃连接执行多代理研究任务。
    返回多代理系统生成的研究报告。

    【大白话注释】
    让一组 AI 一起做一个研究任务（默认问题："AI 是不是泡沫？"）。
    需要有 WebSocket 连着才能跑。

    Returns:
        dict: 包含报告的字典
    """
    return await execute_multi_agents(manager)  # 正经注释：调用多代理执行函数 / 大白话注释：让多代理系统跑起来


@app.post("/upload/")  # 正经注释：定义文件上传 API / 大白话注释：上传文件的接口
async def upload_file(file: UploadFile = File(...)):
    """
    处理文件上传请求。

    【正经注释】
    接收上传的文件，保存到 DOC_PATH 目录并加载其内容到文档系统中。

    【大白话注释】
    上传一个文件，存到文档文件夹里并加载内容，这样研究时就能用到这些文件。

    Args:
        file: 上传的文件对象

    Returns:
        dict: 包含文件名和路径的字典
    """
    return await handle_file_upload(file, DOC_PATH)  # 正经注释：调用文件上传处理函数 / 大白话注释：交给工具箱里的上传函数处理


@app.delete("/files/{filename}")  # 正经注释：定义文件删除 API / 大白话注释：删掉某个文件的接口
async def delete_file(filename: str):
    """
    删除指定文件。

    【正经注释】
    从文档目录中删除指定文件名的文件。

    【大白话注释】
    删掉文档文件夹里的某个文件。

    Args:
        filename: 要删除的文件名

    Returns:
        JSONResponse: 删除结果响应
    """
    return await handle_file_deletion(filename, DOC_PATH)  # 正经注释：调用文件删除处理函数 / 大白话注释：交给工具箱里的删除函数处理


@app.websocket("/ws")  # 正经注释：定义 WebSocket 端点 / 大白话注释：实时通信的入口
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket 通信端点。

    【正经注释】
    建立 WebSocket 连接，处理实时消息通信。
    正常断开时记录断开原因码，异常断开时记录错误信息并确保连接被正确清理。

    【大白话注释】
    这是前后端实时通信的"大门"。前端连上这个 WebSocket 后，
    就能实时收到研究进度、发命令开始研究、聊天等。
    断开连接时（不管正常还是异常），都会做好清理工作。

    Args:
        websocket: WebSocket 连接对象
    """
    await manager.connect(websocket)  # 正经注释：接受并注册 WebSocket 连接 / 大白话注释："前台接待员"登记新客人
    try:
        await handle_websocket_communication(websocket, manager)  # 正经注释：进入消息处理循环 / 大白话注释：开始听前端说话
    except WebSocketDisconnect as e:  # 正经注释：捕获 WebSocket 正常断开异常 / 大白话注释：前端主动断开了
        # Disconnect with more detailed logging about the WebSocket disconnect reason
        logger.info(f"WebSocket disconnected with code {e.code} and reason: '{e.reason}'")  # 正经注释：记录断开原因 / 大白话注释：记下来为啥断的
        await manager.disconnect(websocket)  # 正经注释：清理连接资源 / 大白话注释：做好清理
    except Exception as e:  # 正经注释：捕获其他异常 / 大白话注释：出了意外错误
        # More general exception handling
        logger.error(f"Unexpected WebSocket error: {str(e)}")  # 正经注释：记录错误 / 大白话注释：记下来出啥错了
        await manager.disconnect(websocket)  # 正经注释：清理连接资源 / 大白话注释：做好清理

@app.post("/api/chat")  # 正经注释：定义对话 API / 大白话注释：跟 AI 聊天的接口
async def chat(chat_request: ChatRequest):
    """
    处理对话请求。

    【正经注释】
    接收报告上下文和消息历史，创建带记忆的对话代理进行多轮对话，
    返回包含回复内容和工具调用元数据的结构化响应。

    【大白话注释】
    前端发来聊天消息时，这个函数来处理：
    根据报告内容创建一个聊天机器人，让它根据之前的聊天记录来回答，
    然后把回答格式化好返回。如果用了什么工具（比如搜索），也会一并告知。

    Args:
        chat_request: 对话请求数据（包含报告和消息历史）

    Returns:
        dict: 包含回复消息或错误信息的字典
    """
    """Process a chat request with a report and message history.

    Args:
        chat_request: ChatRequest object containing report text and message history

    Returns:
        JSON response with the assistant's message and any tool usage metadata
    """
    try:
        logger.info(f"Received chat request with {len(chat_request.messages)} messages")  # 正经注释：记录收到的消息数量 / 大白话注释：记下来收了几条消息

        # Create chat agent with the report
        chat_agent = ChatAgentWithMemory(  # 正经注释：创建带记忆的对话代理 / 大白话注释：把聊天机器人叫出来，让它知道报告内容
            report=chat_request.report,
            config_path="default",
            headers=None
        )

        # Process the chat and get response with metadata
        response_content, tool_calls_metadata = await chat_agent.chat(chat_request.messages, None)  # 正经注释：执行对话并获取回复 / 大白话注释：让机器人回答问题
        logger.info(f"response_content: {response_content}")
        logger.info(f"Got chat response of length: {len(response_content) if response_content else 0}")

        if tool_calls_metadata:  # 正经注释：记录工具调用信息 / 大白话注释：如果用了工具就记下来
            logger.info(f"Tool calls used: {json.dumps(tool_calls_metadata)}")

        # Format response as a ChatMessage object with role, content, timestamp and metadata
        response_message = {  # 正经注释：构建结构化的回复消息 / 大白话注释：把回答包装好
            "role": "assistant",  # 正经注释：消息角色为助手 / 大白话注释：标记为 AI 的回复
            "content": response_content,  # 正经注释：回复内容 / 大白话注释：AI 说了啥
            "timestamp": int(time.time() * 1000),  # Current time in milliseconds  # 正经注释：毫秒级时间戳 / 大白话注释：回复时间
            "metadata": {  # 正经注释：元数据 / 大白话注释：附加信息
                "tool_calls": tool_calls_metadata  # 正经注释：工具调用记录 / 大白话注释：用了哪些工具
            } if tool_calls_metadata else None
        }

        logger.info(f"Returning formatted response: {json.dumps(response_message)[:100]}...")  # 正经注释：记录返回的响应预览 / 大白话注释：记下来返回了啥（只记前 100 个字符）
        return {"response": response_message}  # 正经注释：返回回复消息 / 大白话注释：把回答交出去
    except Exception as e:  # 正经注释：捕获异常 / 大白话注释：出错了
        logger.error(f"Error processing chat request: {str(e)}", exc_info=True)
        return {"error": str(e)}  # 正经注释：返回错误信息 / 大白话注释：告诉前端出啥错了

@app.post("/api/reports/{research_id}/chat")  # 正经注释：定义报告对话 API / 大白话注释：跟某份报告聊天的接口
async def research_report_chat(research_id: str, request: Request):
    """
    处理针对特定研究报告的对话请求。

    【正经注释】
    直接解析原始请求数据以避免 Pydantic 验证错误。
    创建基于报告上下文的对话代理，处理对话并返回回复。

    【大白话注释】
    跟某份特定的研究报告聊天。不用 Pydantic 模型来接收数据，
    直接读原始 JSON，这样可以避免验证出错。
    让聊天机器人根据这份报告的内容来回答你的问题。

    Args:
        research_id: 研究报告 ID
        request: FastAPI Request 对象

    Returns:
        dict: 包含回复消息或错误信息的字典
    """
    """Handle chat requests for a specific research report.
    Directly processes the raw request data to avoid validation errors.
    """
    try:
        # Get raw JSON data from request
        data = await request.json()  # 正经注释：直接解析原始 JSON / 大白话注释：直接读 JSON 数据

        # Create chat agent with the report
        chat_agent = ChatAgentWithMemory(  # 正经注释：创建带记忆的对话代理 / 大白话注释：把聊天机器人叫出来
            report=data.get("report", ""),
            config_path="default",
            headers=None
        )

        # Process the chat and get response with metadata
        response_content, tool_calls_metadata = await chat_agent.chat(data.get("messages", []), None)  # 正经注释：执行对话 / 大白话注释：让机器人回答

        if tool_calls_metadata:  # 正经注释：记录工具调用 / 大白话注释：用了工具就记下来
            logger.info(f"Tool calls used: {json.dumps(tool_calls_metadata)}")

        # Format response as a ChatMessage object
        response_message = {  # 正经注释：构建回复消息 / 大白话注释：把回答包装好
            "role": "assistant",
            "content": response_content,
            "timestamp": int(time.time() * 1000),  # 正经注释：毫秒级时间戳 / 大白话注释：回复时间
            "metadata": {
                "tool_calls": tool_calls_metadata
            } if tool_calls_metadata else None
        }

        return {"response": response_message}  # 正经注释：返回回复 / 大白话注释：把回答交出去
    except Exception as e:  # 正经注释：捕获异常 / 大白话注释：出错了
        logger.error(f"Error in research report chat: {str(e)}", exc_info=True)
        return {"error": str(e)}  # 正经注释：返回错误信息 / 大白话注释：告诉前端出啥错了

@app.put("/api/reports/{research_id}")  # 正经注释：定义报告更新 API（PUT，无数据库版本） / 大白话注释：更新报告的接口（占位用）
async def update_report(research_id: str, request: Request):
    """
    更新研究报告（无数据库持久化的占位实现）。

    【正经注释】
    此端点为无数据库配置时的占位实现，仅记录调试日志并返回成功响应。
    实际数据不会持久化存储。

    【大白话注释】
    这是个"假"的更新接口——不会真的存数据，只是告诉你"好了"。
    因为没有配数据库，所以什么也没改。

    Args:
        research_id: 研究报告 ID
        request: FastAPI Request 对象

    Returns:
        dict: 包含 success 标志的字典
    """
    """Update a specific research report by ID - no database configured."""
    logger.debug(f"Update requested for report {research_id} - no database configured, not persisted")  # 正经注释：记录调试日志 / 大白话注释：记下来有人想更新但没数据库存不了
    return {"success": True, "id": research_id}  # 正经注释：返回成功（但实际未持久化） / 大白话注释：说"好了"但其实啥也没干

@app.delete("/api/reports/{research_id}")  # 正经注释：定义报告删除 API（无数据库版本） / 大白话注释：删除报告的接口（占位用）
async def delete_report(research_id: str):
    """
    删除研究报告（无数据库持久化的占位实现）。

    【正经注释】
    此端点为无数据库配置时的占位实现，仅记录调试日志并返回成功响应。
    实际数据不会被删除。

    【大白话注释】
    这是个"假"的删除接口——不会真的删数据，只是告诉你"好了"。
    因为没有配数据库，所以什么也没删。

    Args:
        research_id: 研究报告 ID

    Returns:
        dict: 包含 success 标志和 ID 的字典
    """
    """Delete a specific research report by ID - no database configured."""
    logger.debug(f"Delete requested for report {research_id} - no database configured, nothing to delete")  # 正经注释：记录调试日志 / 大白话注释：记下来有人想删但没数据库删不了
    return {"success": True, "id": research_id}  # 正经注释：返回成功（但实际未删除） / 大白话注释：说"好了"但其实啥也没干
