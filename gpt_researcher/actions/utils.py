"""GPT Researcher 工具函数模块
【正经注释】
本模块提供研究流程中使用的通用工具函数，包括：
- WebSocket 实时输出流（stream_output / safe_send_json）
- API 调用费用计算（calculate_cost / update_cost / create_cost_callback）
- Token 数量格式化（format_token_count）

这些函数被 ResearchConductor、ReportGenerator 等核心组件广泛调用。

【大白话注释】
这个文件就是"工具箱"——里面装着各种小工具：
- stream_output：给前端发实时消息（"正在搜xxx"、"搜完了"）
- calculate_cost：算调 AI 接口花了多少钱
- 其他几个都是这两个功能的辅助版本
"""

from typing import Dict, Any, Callable					# 正经注释：类型提示导入，Dict=字典类型，Any=任意类型，Callable=可调用对象类型 / 大白话注释：告诉代码"这些东西是什么类型"的工具
from ..utils.logger import get_formatted_logger		# 正经注释：导入格式化日志记录器工厂函数 / 大白话注释：导入"记日志"的工具

logger = get_formatted_logger()						# 正经注释：创建格式化日志记录器实例 / 大白话注释：准备一个"记事本"


async def stream_output(								# 正经注释：WebSocket 实时输出流函数，用于向前端推送研究进度和状态信息 / 大白话注释：给前端发消息的函数——告诉用户"在干嘛"
    type, content, output, websocket=None, output_log=True, metadata=None
):
    """
    通过 WebSocket 流式输出内容

    【正经注释】
    双通道输出函数：
    1. 日志通道：将输出内容写入 Python logger（本地日志）
    2. WebSocket 通道：将结构化消息发送给前端客户端（实时推送）

    支持消息类型包括：logs（日志）、report（报告）、images（图片）等。
    内置 UnicodeEncodeError 容错处理，适配 Windows 等非 UTF-8 终端环境。

    【大白话注释】
    这个函数就是"广播站"——把研究过程的每一步都播出去：
    - 先在本地记一份日志（自己留底）
    - 如果有 WebSocket 连接（前端在看），就把消息发过去
    - 如果遇到乱码（Windows 下常见），就自动替换掉

    Args:
        type: 消息类型（大白话：这是啥消息——"日志"、"报告"、"图片"等）
        content: 消息内容标识（大白话：消息的标签/类别）
        output: 输出文本（大白话：要播出去的具体内容）
        websocket: WebSocket 连接（大白话：前端的"接收器"，没有就只记本地日志）
        output_log: 是否写入本地日志（大白话：要不要在本地也记一份）
        metadata: 额外元数据（大白话：附带的附加信息，比如子查询列表等）

    Returns:
        None
    """
    if (not websocket or output_log) and type != "images":	# 正经注释：没有 WebSocket 或者要求写日志时，且不是图片类型，就写本地日志 / 大白话注释：除非是图片，否则都在本地记一笔
        try:
            logger.info(f"{output}")						# 正经注释：写入 INFO 级别日志 / 大白话注释：在记事本上写下来
        except UnicodeEncodeError:							# 正经注释：处理 Windows 终端编码不支持 UTF-8 的情况 / 大白话注释：遇到乱码就换个方式写
            # Option 1: Replace problematic characters with a placeholder	# 正经注释：将无法编码的字符替换为占位符 / 大白话注释：把不认识的字符换成问号之类
            logger.error(output.encode(
                'cp1252', errors='replace').decode('cp1252'))	# 正经注释：使用 cp1252 编码替换非法字符后输出 / 大白话注释：用 Windows 的编码格式重新写

    if websocket:											# 正经注释：有 WebSocket 连接时，发送结构化 JSON 消息 / 大白话注释：如果前端在看着，就把消息发过去
        await websocket.send_json(							# 正经注释：异步发送 JSON 格式消息 / 大白话注释：发一条 JSON 消息
            {"type": type, "content": content,				# 正经注释：消息结构包含类型、内容标识、输出文本和元数据 / 大白话注释：消息里装了"类型"、"标签"、"内容"和"附加信息"
                "output": output, "metadata": metadata}
        )


async def safe_send_json(websocket: Any, data: Dict[str, Any]) -> None:
    """
    安全地通过 WebSocket 发送 JSON 数据

    【正经注释】
    带 try-except 保护的 WebSocket 发送方法。
    捕获所有异常并记录详细错误信息，针对常见错误类型
    （连接关闭、超时）提供额外的诊断日志。
    防止单次发送失败导致整个研究流程中断。

    【大白话注释】
    "安全发消息"——就算发消息出错了也不影响正常工作：
    - 用户关了网页？没关系，记个日志就行
    - 网络超时？也没关系，记下来继续干
    - 不会因为前端断了就导致研究任务崩溃

    Args:
        websocket (WebSocket): WebSocket 连接（大白话：前端的"接收器"）
        data (Dict[str, Any]): 要发送的 JSON 数据（大白话：要发的内容）

    Returns:
        None
    """
    try:
        await websocket.send_json(data)						# 正经注释：尝试发送 JSON 数据 / 大白话注释：试着发消息
    except Exception as e:									# 正经注释：捕获所有异常，防止单次发送失败影响整体流程 / 大白话注释：出错了也别崩溃
        error_type = type(e).__name__						# 正经注释：获取异常类型名称（如 ConnectionClosed、TimeoutError 等） / 大白话注释：看看是什么类型的错误
        error_msg = str(e)									# 正经注释：获取异常消息文本 / 大白话注释：错误的具体内容
        logger.error(										# 正经注释：记录错误日志，包含完整堆栈信息 / 大白话注释：在日志里写下来出了什么错
            f"Error sending JSON through WebSocket: {error_type}: {error_msg}",
            exc_info=True
        )
        # Check for common WebSocket errors and provide helpful context	# 正经注释：针对常见错误类型提供诊断提示 / 大白话注释：看看是哪种常见问题
        if "closed" in error_msg.lower() or "connection" in error_msg.lower():	# 正经注释：连接关闭类错误 / 大白话注释：用户关了网页或者网络断了
            logger.warning("WebSocket connection appears to be closed. Client may have disconnected.")
        elif "timeout" in error_msg.lower():					# 正经注释：超时类错误 / 大白话注释：发消息等太久没回应
            logger.warning("WebSocket send operation timed out. The client may be unresponsive.")


def calculate_cost(										# 正经注释：API 调用费用计算函数，根据模型和 Token 用量计算美元费用 / 大白话注释：算钱——调一次 AI 接口花了多少美元
    prompt_tokens: int,
    completion_tokens: int,
    model: str
) -> float:
    """
    根据 Token 用量和模型类型计算 API 调用费用

    【正经注释】
    使用预定义的每千 Token 单价表计算费用。
    支持主流 OpenAI 模型（GPT-3.5、GPT-4、GPT-4o 等）。
    未知模型使用默认单价 0.0001 美元/千 Token。

    【大白话注释】
    算算花了多少钱：
    - 不同的 AI 模型收费不一样（GPT-4 贵，GPT-3.5 便宜）
    - 看你用了多少字（Token），乘以单价
    - 不认识的模型就按一个默认价算

    Args:
        prompt_tokens (int): 提示词 Token 数（大白话：你发给 AI 多少字）
        completion_tokens (int): 补全 Token 数（大白话：AI 回了你多少字）
        model (str): 模型名称（大白话：用的哪个 AI 模型）

    Returns:
        float: 计算出的费用（美元）（大白话：花了多少美元）
    """
    # Define cost per 1k tokens for different models			# 正经注释：各模型每 1000 Token 的单价表（美元） / 大白话注释：价目表——每个 AI 模型的"每千字价格"
    costs = {
        "gpt-3.5-turbo": 0.002,								# 正经注释：GPT-3.5 Turbo $0.002/1k tokens / 大白话注释：便宜，两千字才 0.002 美元
        "gpt-4": 0.03,										# 正经注释：GPT-4 $0.03/1k tokens / 大白话注释：贵，两千字 0.03 美元
        "gpt-4-32k": 0.06,									# 正经注释：GPT-4 32K 上下文版 $0.06/1k tokens / 大白话注释：更贵，能读更长的文章
        "gpt-4o": 0.00001,									# 正经注释：GPT-4o $0.00001/1k tokens / 大白话注释：新一代，反而很便宜
        "gpt-4o-mini": 0.000001,							# 正经注释：GPT-4o Mini $0.000001/1k tokens / 大白话注释：超级便宜
        "o3-mini": 0.0000005,								# 正经注释：O3 Mini $0.0000005/1k tokens / 大白话注释：推理模型的小版，最便宜
        # Add more models and their costs as needed			# 正经注释：可以在此添加更多模型的定价 / 大白话注释：有新模型就往这儿加
    }

    model = model.lower()									# 正经注释：模型名称转小写，确保匹配不区分大小写 / 大白话注释：统一小写，防止大小写不匹配
    if model not in costs:									# 正经注释：未知模型使用默认单价 / 大白话注释：价目表里没这个模型
        logger.warning(
            f"Unknown model: {model}. Cost calculation may be inaccurate.")
        return 0.0001 # Default avg cost if model is unknown	# 正经注释：返回默认均价 / 大白话注释：按一个大概的价格算

    cost_per_1k = costs[model]								# 正经注释：获取该模型的每千 Token 单价 / 大白话注释：查价目表
    total_tokens = prompt_tokens + completion_tokens		# 正经注释：计算总 Token 数 / 大白话注释：你发的 + AI 回的 = 总字数
    return (total_tokens / 1000) * cost_per_1k				# 正经注释：费用 = (总 Token / 1000) × 单价 / 大白话注释：字数除以一千乘以单价就是费用


def format_token_count(count: int) -> str:
    """
    格式化 Token 数量（加千位分隔符）

    【正经注释】
    使用 Python 的格式化语法为数字添加千位分隔符，
    提升大数字的可读性（如 1234567 → "1,234,567"）。

    【大白话注释】
    给数字加逗号，方便人看：
    - 1234567 → "1,234,567"
    一眼就能看出大概多少。

    Args:
        count (int): Token 数量（大白话：字数）

    Returns:
        str: 格式化后的字符串（大白话：加了逗号的数字字符串）
    """
    return f"{count:,}"										# 正经注释：使用 Python 格式化迷你语言添加千位分隔符 / 大白话注释：加逗号，比如 1000 变成 "1,000"


async def update_cost(									# 正经注释：计算并通过 WebSocket 推送费用更新 / 大白话注释：算钱 + 告诉用户花了多少
    prompt_tokens: int,
    completion_tokens: int,
    model: str,
    websocket: Any
) -> None:
    """
    计算并通过 WebSocket 发送费用信息

    【正经注释】
    组合调用 calculate_cost 和 format_token_count，
    将费用和 Token 用量封装为结构化消息通过 WebSocket 发送。
    使用 safe_send_json 确保发送失败不影响研究流程。

    【大白话注释】
    算完钱后打包发给前端：
    1. 先算花了多少美元
    2. 把总字数、输入字数、输出字数都格式化好
    3. 打包成一条消息发出去
    发送失败了也没关系（用的是安全发送）。

    Args:
        prompt_tokens (int): 提示词 Token 数（大白话：你发了多少字给 AI）
        completion_tokens (int): 补全 Token 数（大白话：AI 回了多少字）
        model (str): 模型名称（大白话：用的哪个 AI）
        websocket (WebSocket): WebSocket 连接（大白话：前端的"接收器"）

    Returns:
        None
    """
    cost = calculate_cost(prompt_tokens, completion_tokens, model)	# 正经注释：计算费用 / 大白话注释：算钱
    total_tokens = prompt_tokens + completion_tokens		# 正经注释：计算总 Token 数 / 大白话注释：算总字数

    await safe_send_json(websocket, {						# 正经注释：通过安全发送方法推送费用信息 / 大白话注释：安全地把费用信息发出去
        "type": "cost",										# 正经注释：消息类型为"费用" / 大白话注释：标记这是"费用"消息
        "data": {
            "total_tokens": format_token_count(total_tokens),		# 正经注释：格式化的总 Token 数 / 大白话注释：总字数（加逗号）
            "prompt_tokens": format_token_count(prompt_tokens),	# 正经注释：格式化的提示词 Token 数 / 大白话注释：输入字数（加逗号）
            "completion_tokens": format_token_count(completion_tokens),	# 正经注释：格式化的补全 Token 数 / 大白话注释：输出字数（加逗号）
            "total_cost": f"${cost:.4f}"					# 正经注释：格式化为 4 位小数的美元金额 / 大白话注释：花了多少美元（精确到小数点后4位）
        }
    })


def create_cost_callback(websocket: Any) -> Callable:
    """
    创建费用更新的回调函数

    【正经注释】
    工厂函数，返回一个异步回调函数用于 LLM 调用后自动更新费用。
    通过闭包捕获 websocket 连接，使回调函数可在任意上下文中使用。
    该回调被传递给 LLM Provider，在每次 API 调用完成后触发。

    【大白话注释】
    这是一个"造回调"的工厂：
    - 你把前端的"接收器"给它
    - 它给你返回一个函数
    - 每次调完 AI 接口，这个函数就会自动算钱并告诉前端
    - 不用你手动去算和发

    Args:
        websocket (WebSocket): WebSocket 连接（大白话：前端的"接收器"）

    Returns:
        Callable: 费用回调函数（大白话：一个"自动算钱+发消息"的函数）
    """
    async def cost_callback(								# 正经注释：内部异步回调函数，通过闭包捕获 websocket / 大白话注释：这就是造出来的"自动算钱"函数
        prompt_tokens: int,
        completion_tokens: int,
        model: str
    ) -> None:
        await update_cost(prompt_tokens, completion_tokens, model, websocket)	# 正经注释：调用 update_cost 计算并发送费用 / 大白话注释：算钱 + 告诉前端

    return cost_callback									# 正经注释：返回回调函数 / 大白话注释：把造好的函数交出去