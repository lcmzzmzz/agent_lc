"""
【正经注释】
深度研究技能模块，实现递归式多层级 Web 研究能力。
通过广度优先 + 深度递归的策略，先扩展搜索查询覆盖面，再逐步深入挖掘子问题，
最终将所有层级的研究发现整合为带引用的上下文，供报告生成器使用。
支持并发控制和进度追踪。

【大白话注释】
这是 GPT Researcher 的"究极进化模式"——深度研究。
不像普通研究搜一轮就完事，它会像剥洋葱一样一层一层往下挖：
第一轮广撒网搜好几个方向，发现有意思的线索就继续深挖，
深挖完了还能继续更深地挖……最后把所有挖到的宝贝整合到一起。
"""

from typing import List, Dict, Any, Optional, Set  # 正经注释：类型注解工具 / 大白话注释：告诉代码读者变量是什么类型
import asyncio  # 正经注释：异步 IO 库，支持并发执行多个研究查询 / 大白话注释：让多个搜索任务同时跑，不用一个一个等
import logging  # 正经注释：日志记录模块 / 大白话注释：记录运行日志，出了问题好排查
import re  # 正经注释：正则表达式模块，用于解析 LLM 返回的非标准格式 / 大白话注释：用正则从 AI 的回复里"抠"出有用信息
import time  # 正经注释：时间模块，用于计算研究耗时 / 大白话注释：计时用的，看研究花了多久
from datetime import datetime, timedelta  # 正经注释：日期时间处理 / 大白话注释：处理日期和时间

import json_repair  # 正经注释：JSON 修复库，能从不完整的 JSON 中提取有效数据 / 大白话注释：AI 返回的 JSON 经常格式不对，这个库负责"抢救"

from gpt_researcher.llm_provider.generic.base import ReasoningEfforts  # 正经注释：推理努力程度枚举，控制 LLM 的思考深度 / 大白话注释：让 AI "多想想"还是"随便想想"的开关
from ..utils.llm import create_chat_completion  # 正经注释：LLM 调用封装函数 / 大白话注释：跟 AI 对话的接口
from ..utils.enum import ReportType, ReportSource, Tone  # 正经注释：报告类型、来源和语气枚举 / 大白话注释：报告的几种格式选项
from ..actions.query_processing import get_search_results  # 正经注释：搜索结果获取函数 / 大白话注释：拿搜索结果用的

logger = logging.getLogger(__name__)  # 正经注释：创建模块级日志记录器 / 大白话注释：给这个模块配个"日记本"

# Maximum words allowed in context (25k words for safety margin)
# 正经注释：上下文最大词数限制，25k 词以留出安全余量 / 大白话注释：最多存 25000 个词，再多 AI 也看不过来
MAX_CONTEXT_WORDS = 25000

# 正经注释：JSON 块提取的正则模式列表，依次尝试：代码块包裹的 JSON、数组、对象 / 大白话注释：几种从 AI 回复里"抠"JSON 的方式，一个不行试下一个
JSON_BLOCK_PATTERNS = [
    re.compile(
        r"```(?:json)?\s*(?P<payload>[\s\S]*?)```",
        re.IGNORECASE,
    ),  # 正经注释：匹配 ```json ... ``` 代码块格式 / 大白话注释：找被三个反引号包起来的 JSON
    re.compile(r"(?P<payload>\[[\s\S]*\])"),  # 正经注释：匹配方括号数组格式 / 大白话注释：找方括号开闭的数组
    re.compile(r"(?P<payload>\{[\s\S]*\})"),  # 正经注释：匹配花括号对象格式 / 大白话注释：找花括号开闭的对象
]

# 正经注释：以下为从 LLM 非标准文本回复中逐行提取结构化数据的正则模式 / 大白话注释：AI 有时不返回标准 JSON，而是写纯文本，这些正则负责"逐行抠"有用信息
QUERY_LINE_PATTERN = re.compile(
    r"^(?:[-*]|\d+[.)])?\s*Query:\s*(?P<query>.+)$",
    re.IGNORECASE,
)  # 正经注释：匹配 "Query: xxx" 行 / 大白话注释：找"查询：xxx"这种行
GOAL_LINE_PATTERN = re.compile(
    r"^(?:[-*]|\d+[.)])?\s*(?:Goal|Research Goal):\s*(?P<goal>.+)$",
    re.IGNORECASE,
)  # 正经注释：匹配 "Goal:" 或 "Research Goal:" 行 / 大白话注释：找"目标：xxx"这种行
QUESTION_LINE_PATTERN = re.compile(
    r"^(?:[-*]|\d+[.)])?\s*(?:Question:\s*)?(?P<question>.+\?)$",
    re.IGNORECASE,
)  # 正经注释：匹配以问号结尾的问题行 / 大白话注释：找带问号的句子
LEARNING_LINE_PATTERN = re.compile(
    r"^(?:[-*]|\d+[.)])?\s*Learning(?:\s*\[(?P<citation>[^\]]+)\])?:\s*(?P<learning>.+)$",
    re.IGNORECASE,
)  # 正经注释：匹配 "Learning: xxx" 或 "Learning [引用]: xxx" 行 / 大白话注释：找"发现：xxx"这种行，可能带引用链接
URL_PATTERN = re.compile(r"https?://[^\s\]\)>\",;]+")  # 正经注释：匹配 URL / 大白话注释：从文本里抠网址


def _extract_json_payloads(response: str) -> list[str]:
    """
    【正经注释】
    从 LLM 响应文本中提取所有可能的 JSON 有效载荷。
    按正则模式优先级逐一匹配，去重后返回候选列表。

    【大白话注释】
    AI 的回复里可能藏着好几段 JSON，这个函数负责把它们全都"抠"出来。
    抠出来的 JSON 可能是代码块里的、也可能是直接写在文本里的。

    Args:
        response: LLM 的原始响应文本
    Returns:
        list[str]: 去重后的 JSON 候选字符串列表
    """
    candidates: list[str] = []
    seen: set[str] = set()  # 正经注释：已见候选集合，用于去重 / 大白话注释：记下已经见过的，防止重复

    for pattern in JSON_BLOCK_PATTERNS:  # 正经注释：按优先级遍历所有 JSON 提取模式 / 大白话注释：用几种不同方式挨个找
        for match in pattern.finditer(response):
            candidate = match.group("payload").strip()  # 正经注释：提取匹配到的 payload 并去除首尾空白 / 大白话注释：把找到的内容扒干净
            if candidate and candidate not in seen:  # 正经注释：跳过空串和重复项 / 大白话注释：空的不要，见过的也不要
                candidates.append(candidate)
                seen.add(candidate)

    return candidates


def _load_repaired_json(response: str) -> Any:
    """
    【正经注释】
    尝试从 LLM 响应中加载并修复 JSON 数据。
    先尝试解析原始文本，再尝试各个提取出的 JSON 候选，使用 json_repair 进行容错解析。
    所有尝试均失败时返回 None。

    【大白话注释】
    用尽全力把 AI 回复里的 JSON 救回来。先试原文本，再试抠出来的各段 JSON，
    用专门的修复工具来处理格式错误。实在救不回来就返回 None。

    Args:
        response: LLM 的原始响应文本
    Returns:
        Any: 解析后的 Python 对象（dict/list），失败返回 None
    """
    for candidate in [response.strip(), *_extract_json_payloads(response)]:  # 正经注释：先尝试原始文本，再尝试提取的候选 / 大白话注释：先啃一口原汤，再吃配菜
        if not candidate:
            continue  # 正经注释：跳过空候选 / 大白话注释：空的就跳过
        try:
            return json_repair.loads(candidate)  # 正经注释：使用 json_repair 容错解析 / 大白话注释：用修复工具试着解析
        except Exception as exc:
            logger.debug(
                "json_repair failed on candidate (%d chars): %s",
                len(candidate), exc,
            )  # 正经注释：记录解析失败的调试信息 / 大白话注释：解析失败就记个小本本，不影响程序继续跑
            continue
    return None  # 正经注释：所有候选均失败，返回 None / 大白话注释：全军覆没，啥也没解析出来


def parse_search_queries_response(response: str, num_queries: int) -> List[Dict[str, str]]:
    """
    【正经注释】
    解析 LLM 返回的搜索查询结果。支持两种格式：(1) 标准 JSON（数组或嵌套在对象中）；
    (2) 纯文本的 "Query:/Goal:" 键值对行。优先尝试 JSON 解析，失败后回退到正则逐行提取。

    【大白话注释】
    AI 返回的搜索查询可能是正规的 JSON，也可能是随便写的文本。
    这个函数先试 JSON，解析不了就用正则一行一行抠。
    最终返回统一格式的查询列表，每个查询包含 query 和 researchGoal。

    Args:
        response: LLM 原始响应
        num_queries: 需要的最大查询数量
    Returns:
        List[Dict[str, str]]: [{"query": "...", "researchGoal": "..."}, ...]
    """
    parsed = _load_repaired_json(response)  # 正经注释：尝试修复并解析 JSON / 大白话注释：先试着把 JSON 救回来
    candidate_queries = parsed
    if isinstance(parsed, dict):  # 正经注释：如果解析结果是字典，尝试从常见键名中获取查询列表 / 大白话注释：JSON 包在字典里了，找找有没有 queries/searchQueries/items 这些键
        candidate_queries = parsed.get("queries") or parsed.get("searchQueries") or parsed.get("items")

    if isinstance(candidate_queries, list):  # 正经注释：成功获取列表，提取有效查询项 / 大白话注释：找到列表了，开始提取
        queries = [
            {
                "query": item["query"].strip(),
                "researchGoal": item["researchGoal"].strip(),
            }
            for item in candidate_queries
            if isinstance(item, dict) and item.get("query") and item.get("researchGoal")
        ]  # 正经注释：过滤出同时包含 query 和 researchGoal 的有效项 / 大白话注释：两个字段都有才要
        if queries:
            return queries[:num_queries]  # 正经注释：截取到所需数量 / 大白话注释：多了就砍掉

    # 正经注释：JSON 解析失败，回退到正则逐行提取模式 / 大白话注释：JSON 救不回来，改用一行一行抠的方式
    queries: List[Dict[str, str]] = []
    current_query: Dict[str, str] = {}  # 正经注释：当前正在构建的查询对象 / 大白话注释：正在拼装的查询

    for raw_line in response.replace("```json", "").replace("```", "").splitlines():
        line = raw_line.strip()
        if not line:
            continue  # 正经注释：跳过空行 / 大白话注释：空行跳过

        query_match = QUERY_LINE_PATTERN.match(line)  # 正经注释：匹配 Query 行 / 大白话注释：看看是不是"查询：xxx"
        goal_match = GOAL_LINE_PATTERN.match(line)  # 正经注释：匹配 Goal 行 / 大白话注释：看看是不是"目标：xxx"

        if query_match:
            if current_query.get("query") and current_query.get("researchGoal"):
                queries.append(current_query)  # 正经注释：之前的查询已完整，加入列表 / 大白话注释：上一组拼好了，存起来
            current_query = {"query": query_match.group("query").strip()}  # 正经注释：开始新的查询对象 / 大白话注释：开始拼新的一组
        elif goal_match and current_query.get("query"):
            current_query["researchGoal"] = goal_match.group("goal").strip()  # 正经注释：补充当前查询的研究目标 / 大白话注释：给当前这组补上目标

    if current_query.get("query") and current_query.get("researchGoal"):
        queries.append(current_query)  # 正经注释：别忘了最后一个查询 / 大白话注释：最后一组别忘了存

    return queries[:num_queries]


def parse_follow_up_questions_response(response: str, num_questions: int) -> List[str]:
    """
    【正经注释】
    解析 LLM 返回的后续问题列表。与搜索查询解析类似，优先 JSON 解析，
    失败后回退到正则匹配以问号结尾的问题行。

    【大白话注释】
    跟上面的函数差不多的套路——先试 JSON，不行就正则抠。
    这回抠的是"后续问题"（就是 AI 建议继续研究的问题）。

    Args:
        response: LLM 原始响应
        num_questions: 需要的最大问题数量
    Returns:
        List[str]: 问题字符串列表
    """
    parsed = _load_repaired_json(response)  # 正经注释：尝试修复并解析 JSON / 大白话注释：先抢救 JSON
    candidate_questions = parsed
    if isinstance(parsed, dict):  # 正经注释：从字典的常见键名中提取问题列表 / 大白话注释：从 JSON 对象里找 questions/followUpQuestions/items
        candidate_questions = parsed.get("questions") or parsed.get("followUpQuestions") or parsed.get("items")

    if isinstance(candidate_questions, list):  # 正经注释：成功获取列表，转为字符串 / 大白话注释：拿到了，转成字符串列表
        questions = [str(item).strip() for item in candidate_questions if str(item).strip()]
        if questions:
            return questions[:num_questions]

    # 正经注释：JSON 解析失败，回退到正则逐行提取 / 大白话注释：JSON 没救成，改用正则抠
    questions: List[str] = []
    for raw_line in response.replace("```json", "").replace("```", "").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        question_match = QUESTION_LINE_PATTERN.match(line)  # 正经注释：匹配以问号结尾的行 / 大白话注释：找带问号的句子
        if question_match:
            questions.append(question_match.group("question").strip())

    return questions[:num_questions]


def parse_research_results_response(response: str, num_learnings: int) -> Dict[str, Any]:
    """
    【正经注释】
    解析 LLM 返回的研究结果，提取学习发现（learnings）、后续问题（followUpQuestions）
    和引用来源（citations）。支持 JSON 和纯文本两种格式，JSON 模式下会从 insight/learning
    和 sourceUrl/citation 等多种键名中提取数据。

    【大白话注释】
    这个函数把 AI 分析搜索结果后的回复"拆解"成三样东西：
    1. 学习发现——搜到了什么重要信息
    2. 后续问题——还有什么值得继续研究的
    3. 引用——信息来源的网址

    Args:
        response: LLM 原始响应
        num_learnings: 最大保留的发现数量
    Returns:
        Dict[str, Any]: {"learnings": [...], "followUpQuestions": [...], "citations": {...}}
    """
    parsed = _load_repaired_json(response)  # 正经注释：尝试修复并解析 JSON / 大白话注释：先抢救 JSON

    if isinstance(parsed, dict):  # 正经注释：JSON 解析成功，从字典中提取各字段 / 大白话注释：JSON 救回来了，开始分拣
        learnings_payload = parsed.get("learnings", [])  # 正经注释：获取学习发现列表 / 大白话注释：拿到"发现"列表
        follow_up_payload = parsed.get("followUpQuestions") or parsed.get("questions") or []  # 正经注释：获取后续问题列表 / 大白话注释：拿到"后续问题"列表
        learnings: List[str] = []
        citations: Dict[str, str] = {}  # 正经注释：引用字典，key 为发现内容，value 为来源 URL / 大白话注释：记录每条发现对应的来源网址

        if isinstance(learnings_payload, list):  # 正经注释：遍历学习发现列表 / 大白话注释：逐条处理发现
            for item in learnings_payload:
                if isinstance(item, dict):  # 正经注释：字典类型的发现项，尝试多种键名 / 大白话注释：发现是对象格式，找 insight 或 learning 字段
                    learning = str(item.get("insight") or item.get("learning") or "").strip()
                    citation = str(item.get("sourceUrl") or item.get("citation") or "").strip()
                else:  # 正经注释：纯文本发现项 / 大白话注释：发现就是一段文字，没有引用
                    learning = str(item).strip()
                    citation = ""

                if learning:
                    learnings.append(learning)
                    if citation:
                        citations[learning] = citation  # 正经注释：建立发现到引用的映射 / 大白话注释：把发现和它的来源网址配对

        questions = [str(item).strip() for item in follow_up_payload if str(item).strip()]
        if learnings or questions:  # 正经注释：有有效数据时立即返回 / 大白话注释：拿到了就返回
            return {
                "learnings": learnings[:num_learnings],
                "followUpQuestions": questions[:num_learnings],
                "citations": citations,
            }

    # 正经注释：JSON 解析失败，回退到正则逐行提取 / 大白话注释：JSON 没救成，老办法——正则一行行抠
    learnings: List[str] = []
    questions: List[str] = []
    citations: Dict[str, str] = {}

    for raw_line in response.replace("```json", "").replace("```", "").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        learning_match = LEARNING_LINE_PATTERN.match(line)  # 正经注释：匹配 Learning 行 / 大白话注释：看看是不是"发现：xxx"
        question_match = QUESTION_LINE_PATTERN.match(line)  # 正经注释：匹配问题行 / 大白话注释：看看是不是问题

        if learning_match:
            learning = learning_match.group("learning").strip()
            citation = (learning_match.group("citation") or "").strip()  # 正经注释：提取方括号中的引用 / 大白话注释：看看有没有 [引用链接]
            if not citation:  # 正经注释：如果没有显式引用，尝试从文本中提取 URL / 大白话注释：引用没找到，看看正文里有没有网址
                url_match = URL_PATTERN.search(learning)
                if url_match:
                    citation = url_match.group(0)
                    learning = learning.replace(citation, "").strip(" -")  # 正经注释：从正文中移除 URL，避免重复 / 大白话注释：网址已经单独记了，从正文里删掉
            if learning:
                learnings.append(learning)
                if citation:
                    citations[learning] = citation
        elif question_match:
            questions.append(question_match.group("question").strip())

    return {
        "learnings": learnings[:num_learnings],
        "followUpQuestions": questions[:num_learnings],
        "citations": citations,
    }

def count_words(text) -> int:
    """Count words in a text string. Handles both strings and lists.

    【正经注释】
    计算文本词数。支持字符串和列表输入，列表会先拼接为字符串再计数。

    【大白话注释】
    数一数文本有多少个词。传字符串直接数，传列表先拼起来再数。

    Args:
        text: 字符串或字符串列表
    Returns:
        int: 词数
    """
    if isinstance(text, list):
        text = " ".join(str(item) for item in text)  # 正经注释：列表元素拼接为单一字符串 / 大白话注释：列表就先拼成一段话
    return len(str(text).split())  # 正经注释：按空格分词计数 / 大白话注释：按空格切一刀，数有几块

def trim_context_to_word_limit(context_list: List[str], max_words: int = MAX_CONTEXT_WORDS) -> List[str]:
    """Trim context list to stay within word limit while preserving most recent/relevant items

    【正经注释】
    将上下文列表裁剪到词数限制内。从后向前遍历（保留最新的条目），
    超出限制时截断，最终保持原始顺序。

    【大白话注释】
    上下文太多了 AI 看不完，得裁一裁。策略是：从后面（最新的）开始保留，
    加到超限为止。这样保证留下的是最新、最相关的信息。

    Args:
        context_list: 上下文字符串列表
        max_words: 最大允许词数
    Returns:
        List[str]: 裁剪后的上下文列表
    """
    total_words = 0
    trimmed_context = []

    # Process in reverse to keep most recent items
    # 正经注释：反向遍历以保留最近的条目 / 大白话注释：从后往前看，最新的先留
    for item in reversed(context_list):
        words = count_words(item)
        if total_words + words <= max_words:  # 正经注释：未超限则保留 / 大白话注释：还能放下，继续加
            trimmed_context.insert(0, item)  # Insert at start to maintain original order  # 正经注释：插入头部以保持原始顺序 / 大白话注释：插到最前面，这样顺序不会乱
            total_words += words
        else:
            break  # 正经注释：超限则停止 / 大白话注释：放不下了，到此为止

    return trimmed_context

class ResearchProgress:
    """
    【正经注释】
    深度研究进度追踪器。记录当前递归深度、广度完成度、查询执行状态等信息，
    通过回调函数向前端推送实时进度。

    【大白话注释】
    研究"进度条"的数据结构。记录：现在挖到第几层了、搜了几个方向了、
    当前在查什么问题、总共要查几个、完成了几个。方便告诉用户"我在忙，别催"。

    Attributes:
        current_depth: 当前递归深度层级
        total_depth: 总递归深度
        current_breadth: 当前已完成的广度查询数
        total_breadth: 总广度查询数
        current_query: 当前正在处理的查询
        total_queries: 总查询数
        completed_queries: 已完成查询数
    """
    def __init__(self, total_depth: int, total_breadth: int):
        """
        【正经注释】
        初始化进度追踪器。

        【大白话注释】
        告诉进度条"总共要挖几层、每层查几个方向"。

        Args:
            total_depth: 总深度层数
            total_breadth: 总广度（查询方向数）
        """
        self.current_depth = 1  # Start from 1 and increment up to total_depth  # 正经注释：深度从 1 开始递增到 total_depth / 大白话注释：从第 1 层开始挖
        self.total_depth = total_depth
        self.current_breadth = 0  # Start from 0 and count up to total_breadth as queries complete  # 正经注释：广度从 0 开始计数 / 大白话注释：完成了几个方向，从 0 数
        self.total_breadth = total_breadth
        self.current_query: Optional[str] = None  # 正经注释：当前正在执行的查询文本 / 大白话注释：正在搜什么
        self.total_queries = 0  # 正经注释：本轮总查询数 / 大白话注释：这轮总共要搜几个
        self.completed_queries = 0  # 正经注释：已完成查询数 / 大白话注释：这轮已经搜完几个


class DeepResearchSkill:
    """
    【正经注释】
    深度研究技能核心类。实现递归式多层级研究流程：
    1. 生成初始搜索查询（广度）
    2. 对每个查询执行独立研究
    3. 从研究结果中提取学习发现和后续问题
    4. 根据后续问题递归深入研究（深度）
    5. 整合所有层级的研究发现

    支持并发控制和进度回调。

    【大白话注释】
    这就是"深度研究"的大脑。它的工作方式像一棵树：
    先横向长出好几根树枝（广度搜索），每根树枝上再长小树枝（递归深挖），
    最后把所有树枝上的果子（研究发现）都收回来。
    """

    def __init__(self, researcher):
        """
        【正经注释】
        初始化深度研究技能，从 researcher 实例和配置中提取所需参数。

        【大白话注释】
        把研究员的装备和配置都拿过来，准备开工。

        Args:
            researcher: GPTResearcher 实例，提供配置、WebSocket、语气等上下文
        """
        self.researcher = researcher
        self.breadth = getattr(researcher.cfg, 'deep_research_breadth', 4)  # 正经注释：每轮搜索的查询数量，默认 4 / 大白话注释：每轮搜几个方向，默认 4 个
        self.depth = getattr(researcher.cfg, 'deep_research_depth', 2)  # 正经注释：递归深度，默认 2 层 / 大白话注释：挖几层深，默认 2 层
        self.concurrency_limit = getattr(researcher.cfg, 'deep_research_concurrency', 2)  # 正经注释：并发查询上限，默认 2 / 大白话注释：最多几个搜索同时跑，默认 2 个
        self.websocket = researcher.websocket  # 正经注释：WebSocket 连接，用于实时推送进度 / 大白话注释：给前端发消息的管道
        self.tone = researcher.tone  # 正经注释：报告写作语气 / 大白话注释：什么调调
        self.config_path = researcher.cfg.config_path if hasattr(researcher.cfg, 'config_path') else None  # 正经注释：配置文件路径 / 大白话注释：配置文件在哪
        self.headers = researcher.headers or {}  # 正经注释：HTTP 请求头 / 大白话注释：发请求时带的信息头
        self.visited_urls = researcher.visited_urls  # 正经注释：已访问 URL 集合，避免重复抓取 / 大白话注释：已经去过的网址，别再去了
        self.learnings = []  # 正经注释：所有学习发现累积列表 / 大白话注释：收集所有"发现"的篮子
        self.research_sources = []  # Track all research sources  # 正经注释：所有研究来源追踪列表 / 大白话注释：所有资料来源的清单
        self.context = []  # Track all context  # 正经注释：所有上下文累积列表 / 大白话注释：所有搜到的内容的容器

    async def generate_search_queries(self, query: str, num_queries: int = 3) -> List[Dict[str, str]]:
        """Generate SERP queries for research

        【正经注释】
        使用战略 LLM 生成搜索查询。通过精心设计的 system prompt 约束 LLM
        只返回纯 JSON 数组格式，每个元素包含 query（搜索词）和 researchGoal（研究目标）。
        使用 strategic_llm 模型以确保查询质量。

        【大白话注释】
        让"聪明的 AI"帮忙想几个搜索关键词。告诉它：你要搜什么方向、为什么搜这个方向。
        用的是"军师"模型（strategic_llm），因为它负责出谋划策。

        Args:
            query: 研究问题
            num_queries: 要生成的查询数量
        Returns:
            List[Dict[str, str]]: [{"query": "...", "researchGoal": "..."}, ...]
        """
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert researcher generating search queries. "
                    "Return valid JSON only. Do not include markdown, code fences, bullets, numbering, or prose."
                ),
            },  # 正经注释：系统提示，约束输出格式为纯 JSON / 大白话注释：告诉 AI"别废话，只给 JSON"
            {
                "role": "user",
                "content": (
                    f"Given the following prompt, generate {num_queries} unique search queries to research the topic thoroughly. "
                    "For each query, provide a research goal.\n\n"
                    "Return ONLY a JSON array of objects using this exact schema:\n"
                    '[{"query": "<search query>", "researchGoal": "<research goal>"}]\n\n'
                    f"Prompt: {query}"
                ),
            },  # 正经注释：用户提示，提供查询上下文和输出 schema / 大白话注释：告诉 AI 具体要干什么、输出长什么样
        ]

        response = await create_chat_completion(
            messages=messages,
            llm_provider=self.researcher.cfg.strategic_llm_provider,  # 正经注释：使用战略级 LLM 提供商 / 大白话注释：用"军师"级别的 AI
            model=self.researcher.cfg.strategic_llm_model,  # 正经注释：使用战略级模型 / 大白话注释：用最聪明的模型
            reasoning_effort=self.researcher.cfg.reasoning_effort,  # 正经注释：推理努力程度 / 大白话注释：想多深
            temperature=0.4  # 正经注释：较低温度以获得稳定输出 / 大白话注释：别太发散，稳一点
        )

        return parse_search_queries_response(response, num_queries)  # 正经注释：解析 LLM 响应为结构化查询列表 / 大白话注释：把 AI 的回复拆成查询列表

    async def generate_research_plan(self, query: str, num_questions: int = 3) -> List[str]:
        """Generate follow-up questions to clarify research direction

        【正经注释】
        生成研究计划，即后续研究问题。先用所有检索器获取初始搜索结果，
        再结合当前时间让 LLM 分析原始查询和搜索结果，生成探索不同维度和时间段的后续问题。

        【大白话注释】
        先快速搜一轮看看有什么，然后让 AI 根据初步结果想几个值得深挖的问题。
        相当于"先看一眼地图，再决定往哪走"。

        Args:
            query: 研究问题
            num_questions: 要生成的问题数量
        Returns:
            List[str]: 后续研究问题列表
        """
        # Get initial search results from all retrievers to inform query generation
        # 正经注释：从所有检索器获取初始搜索结果，为后续问题生成提供上下文 / 大白话注释：先用各种搜索工具快速搜一遍
        all_search_results = []
        for retriever in self.researcher.retrievers:
            try:
                results = await get_search_results(
                    query,
                    retriever,
                    researcher=self.researcher
                )
                all_search_results.extend(results)
            except Exception as e:
                logger.warning(f"Error with retriever {retriever.__name__}: {e}")  # 正经注释：单个检索器失败不影响整体流程 / 大白话注释：某个搜索工具挂了就跳过，不影响别的
        search_results = all_search_results
        logger.info(f"Initial web knowledge obtained: {len(search_results)} results")  # 正经注释：记录初始搜索结果数量 / 大白话注释：记一下搜到了多少条

        # Get current time for context
        # 正经注释：获取当前时间，注入提示词让 LLM 考虑时效性 / 大白话注释：告诉 AI 现在几点，这样它能关注最新消息
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert researcher. Your task is to analyze the original query and search results, "
                    "then generate targeted questions that explore different aspects and time periods of the topic. "
                    "Return valid JSON only."
                ),
            },  # 正经注释：系统提示，约束为 JSON 格式输出 / 大白话注释：告诉 AI"你是专家，只给 JSON"
            {"role": "user",
             "content": f"""Original query: {query}

Current time: {current_time}

Search results:
{search_results}

Based on these results, the original query, and the current time, generate {num_questions} unique questions. Each question should explore a different aspect or time period of the topic, considering recent developments up to {current_time}.

Return ONLY a JSON object using this exact schema:
{{"questions": ["<question 1>", "<question 2>"]}}"""}  # 正经注释：用户提供完整上下文和输出 schema / 大白话注释：把搜到的结果和时间都给 AI，让它想几个方向
        ]

        response = await create_chat_completion(
            messages=messages,
            llm_provider=self.researcher.cfg.strategic_llm_provider,
            model=self.researcher.cfg.strategic_llm_model,
            reasoning_effort=ReasoningEfforts.High.value,  # 正经注释：使用高推理努力以获得更好的问题质量 / 大白话注释：让 AI 多想想，这步很重要
            temperature=0.4
        )

        return parse_follow_up_questions_response(response, num_questions)

    async def process_research_results(self, query: str, context: str, num_learnings: int = 3) -> Dict[str, List[str]]:
        """Process research results to extract learnings and follow-up questions

        【正经注释】
        使用战略 LLM 分析搜索结果，提取关键学习发现（含引用来源）和后续研究问题。
        要求 LLM 以 JSON 格式返回结构化结果。

        【大白话注释】
        把搜到的一大堆资料丢给 AI，让它提炼出"重点发现"和"还值得继续查的问题"。
        每个发现都要标明信息来源，方便后面写引用。

        Args:
            query: 原始搜索查询
            context: 搜索结果文本
            num_learnings: 最大保留发现数量
        Returns:
            Dict: {"learnings": [...], "followUpQuestions": [...], "citations": {...}}
        """
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert researcher analyzing search results. "
                    "Return valid JSON only."
                ),
            },  # 正经注释：系统提示约束 JSON 输出 / 大白话注释：AI 你只给 JSON，别废话
            {"role": "user",
             "content": (
                 f"Given the following research results for the query '{query}', extract key learnings and suggest "
                 "follow-up questions. For each learning, include a citation to the source URL if available.\n\n"
                 "Return ONLY a JSON object using this exact schema:\n"
                 '{"learnings": [{"insight": "<insight>", "sourceUrl": "<url or empty string>"}], '
                 '"followUpQuestions": ["<question 1>", "<question 2>"]}\n\n'
                 f"Research results:\n{context}"
             )}  # 正经注释：提供查询、schema 和完整搜索结果 / 大白话注释：告诉 AI 要提炼什么、输出格式是什么、资料在这里
        ]

        response = await create_chat_completion(
            messages=messages,
            llm_provider=self.researcher.cfg.strategic_llm_provider,
            model=self.researcher.cfg.strategic_llm_model,
            temperature=0.4,  # 正经注释：低温度保证稳定输出 / 大白话注释：稳一点别乱发挥
            reasoning_effort=ReasoningEfforts.High.value,  # 正经注释：高推理努力以提取高质量发现 / 大白话注释：多想想，提炼重点不能马虎
            max_tokens=1000  # 正经注释：限制最大 token 数 / 大白话注释：别写太长
        )

        return parse_research_results_response(response, num_learnings)

    async def deep_research(
            self,
            query: str,
            breadth: int,
            depth: int,
            learnings: List[str] = None,
            citations: Dict[str, str] = None,
            visited_urls: Set[str] = None,
            on_progress=None
    ) -> Dict[str, Any]:
        """Conduct deep iterative research

        【正经注释】
        核心递归研究方法。执行流程：
        1. 生成 breadth 个搜索查询
        2. 使用信号量控制并发，为每个查询创建独立 GPTResearcher 实例执行研究
        3. 提取每个查询的学习发现、引用和后续问题
        4. 若 depth > 1，将广度减半，构造新的查询（结合研究目标和后续问题）进行递归
        5. 整合所有层级的发现、引用和上下文

        【大白话注释】
        这是深度研究的"心脏"——递归搜索的入口。
        每一轮：搜 N 个方向 -> 每个方向拿到结果后，挑有意思的继续往下搜 ->
        下一轮搜索方向减半，越搜越精 -> 直到达到指定深度为止。
        最后把所有层搜到的东西打包返回。

        Args:
            query: 研究查询
            breadth: 广度（每轮搜索方向数）
            depth: 深度（递归层数）
            learnings: 已有的学习发现（递归间传递）
            citations: 已有的引用映射（递归间传递）
            visited_urls: 已访问 URL 集合（递归间传递）
            on_progress: 进度回调函数
        Returns:
            Dict[str, Any]: 包含 learnings, visited_urls, citations, context, sources 的结果字典
        """
        print(f"\n📊 DEEP RESEARCH: depth={depth}, breadth={breadth}, query={query[:100]}...", flush=True)
        if learnings is None:
            learnings = []  # 正经注释：初始化空列表避免可变默认参数陷阱 / 大白话注释：第一次调用时初始化空篮子
        if citations is None:
            citations = {}
        if visited_urls is None:
            visited_urls = set()  # 正经注释：初始化空集合 / 大白话注释：记去过的网址

        progress = ResearchProgress(depth, breadth)  # 正经注释：创建进度追踪器 / 大白话注释：准备进度条

        if on_progress:
            on_progress(progress)  # 正经注释：通知初始进度 / 大白话注释：告诉前端"我开始了"

        # Generate search queries
        # 正经注释：生成本轮的搜索查询 / 大白话注释：想几个搜索方向
        print(f"🔎 Generating {breadth} search queries...", flush=True)
        serp_queries = await self.generate_search_queries(query, num_queries=breadth)
        print(f"✅ Generated {len(serp_queries)} queries: {[q['query'] for q in serp_queries]}", flush=True)
        progress.total_queries = len(serp_queries)  # 正经注释：记录总查询数 / 大白话注释：这轮总共要搜几个

        all_learnings = learnings.copy()  # 正经注释：复制已有发现，避免修改传入参数 / 大白话注释：把之前找到的复制一份
        all_citations = citations.copy()
        all_visited_urls = visited_urls.copy()
        all_context = []  # 正经注释：本轮收集的上下文 / 大白话注释：这轮搜到的内容
        all_sources = []  # 正经注释：本轮收集的来源 / 大白话注释：这轮的资料来源

        # Process queries with concurrency limit
        # 正经注释：使用 asyncio.Semaphore 控制并发查询数 / 大白话注释：用"信号灯"控制同时跑几个搜索，别把服务器挤爆
        semaphore = asyncio.Semaphore(self.concurrency_limit)

        async def process_query(serp_query: Dict[str, str]) -> Optional[Dict[str, Any]]:
            """
            【正经注释】
            处理单个搜索查询的异步函数。为每个查询创建独立的 GPTResearcher 实例，
            执行完整研究流程并提取结构化结果。通过信号量控制并发数。

            【大白话注释】
            搜一个方向的全过程：创建一个"小研究员" -> 让它去搜 -> 提炼发现 -> 汇报结果。
            通过信号灯排队，不能一窝蜂全上。

            Args:
                serp_query: {"query": "...", "researchGoal": "..."}
            Returns:
                处理结果字典或 None（异常时）
            """
            async with semaphore:  # 正经注释：获取信号量，超过并发上限时阻塞等待 / 大白话注释：排队等位
                try:
                    progress.current_query = serp_query['query']
                    if on_progress:
                        on_progress(progress)  # 正经注释：更新当前查询进度 / 大白话注释：告诉前端"我在查这个"

                    from .. import GPTResearcher  # 正经注释：延迟导入避免循环依赖 / 大白话注释：这里才导入，防止导入时互相卡死
                    researcher = GPTResearcher(
                        query=serp_query['query'],
                        report_type=ReportType.ResearchReport.value,  # 正经注释：使用标准研究报告类型 / 大白话注释：普通报告模式
                        report_source=ReportSource.Web.value,  # 正经注释：来源为 Web / 大白话注释：从网上搜
                        tone=self.tone,
                        websocket=self.websocket,
                        config_path=self.config_path,
                        headers=self.headers,
                        visited_urls=self.visited_urls,
                        # Propagate MCP configuration to nested researchers
                        # 正经注释：将 MCP 配置传递给嵌套的研究员实例 / 大白话注释：把外部工具的配置也传给"小研究员"
                        mcp_configs=self.researcher.mcp_configs,
                        mcp_strategy=self.researcher.mcp_strategy
                    )

                    # Conduct research
                    # 正经注释：执行完整研究流程获取上下文 / 大白话注释：让小研究员开工
                    context = await researcher.conduct_research()

                    # Get results and visited URLs
                    # 正经注释：获取访问过的 URL 和来源 / 大白话注释：小研究员干完了，看看它去了哪些网站、用了哪些资料
                    visited = researcher.visited_urls
                    sources = researcher.research_sources

                    # Process results to extract learnings and citations
                    # 正经注释：从研究结果中提取学习发现和引用 / 大白话注释：把搜到的东西提炼一下，拿出重点
                    results = await self.process_research_results(
                        query=serp_query['query'],
                        context=context
                    )

                    # Update progress
                    # 正经注释：更新进度状态 / 大白话注释：进度条往前挪一点
                    progress.completed_queries += 1
                    progress.current_breadth += 1
                    if on_progress:
                        on_progress(progress)

                    return {
                        'learnings': results['learnings'],
                        'visited_urls': list(visited),
                        'followUpQuestions': results['followUpQuestions'],
                        'researchGoal': serp_query['researchGoal'],
                        'citations': results['citations'],
                        'context': "\n".join(context) if isinstance(context, list) else (context or ""),  # 正经注释：列表拼接为字符串 / 大白话注释：内容是列表就拼起来
                        'sources': sources if sources else []
                    }

                except Exception as e:
                    import traceback
                    error_details = traceback.format_exc()
                    logger.error(f"Error processing query '{serp_query['query']}': {str(e)}")
                    print(f"\n❌ DEEP RESEARCH ERROR: {str(e)}\n{error_details}", flush=True)
                    return None  # 正经注释：单个查询失败返回 None，不影响其他查询 / 大白话注释：这个方向挂了就跳过，别拖累其他方向

        # Process queries concurrently with limit
        # 正经注释：创建并发任务并等待全部完成 / 大白话注释：所有方向同时搜，搜完一起收
        tasks = [process_query(query) for query in serp_queries]
        results = await asyncio.gather(*tasks)
        results = [r for r in results if r is not None]  # 正经注释：过滤掉失败的查询 / 大白话注释：挂了的就不要了

        # Update breadth progress based on successful queries
        progress.current_breadth = len(results)  # 正经注释：用实际成功数更新广度进度 / 大白话注释：实际完成了几个
        if on_progress:
            on_progress(progress)

        # Collect all results
        # 正经注释：汇总所有查询结果 / 大白话注释：把各方向搜到的东西汇总
        for result in results:
            all_learnings.extend(result['learnings'])  # 正经注释：累积学习发现 / 大白话注释：发现加到篮子里
            all_visited_urls.update(result['visited_urls'])  # 正经注释：累积已访问 URL / 大白话注释：记下去过的网址
            all_citations.update(result['citations'])  # 正经注释：累积引用映射 / 大白话注释：把引用也收好
            if result['context']:
                all_context.append(result['context'])  # 正经注释：累积上下文 / 大白话注释：搜到的内容也存起来
            if result['sources']:
                all_sources.extend(result['sources'])  # 正经注释：累积来源 / 大白话注释：资料来源记一下

            # Continue deeper if needed
            # 正经注释：若还有深度剩余，进行递归深入研究 / 大白话注释：还能往下挖，继续挖
            if depth > 1:
                new_breadth = max(2, breadth // 2)  # 正经注释：下一轮广度减半，最少 2 个 / 大白话注释：方向砍一半，至少留 2 个
                new_depth = depth - 1  # 正经注释：深度递减 / 大白话注释：层数减一
                progress.current_depth += 1  # 正经注释：递增深度层级 / 大白话注释：记录"我挖深了一层"

                # Create next query from research goal and follow-up questions
                # 正经注释：基于研究目标和后续问题构造下一轮查询 / 大白话注释：把"本来想查什么"和"还有什么想查的"拼成新问题
                next_query = f"""
                Previous research goal: {result['researchGoal']}
                Follow-up questions: {' '.join(result['followUpQuestions'])}
                """

                # Recursive research
                # 正经注释：递归调用自身进行更深层次研究 / 大白话注释：自己调自己，往更深处挖
                deeper_results = await self.deep_research(
                    query=next_query,
                    breadth=new_breadth,
                    depth=new_depth,
                    learnings=all_learnings,
                    citations=all_citations,
                    visited_urls=all_visited_urls,
                    on_progress=on_progress
                )

                all_learnings = deeper_results['learnings']  # 正经注释：用递归结果覆盖累积发现 / 大白话注释：把更深层挖到的也收进来
                all_visited_urls.update(deeper_results['visited_urls'])
                all_citations.update(deeper_results['citations'])
                if deeper_results.get('context'):
                    all_context.extend(deeper_results['context'])
                if deeper_results.get('sources'):
                    all_sources.extend(deeper_results['sources'])

        # Update class tracking
        # 正经注释：更新类级别的追踪变量 / 大白话注释：把本轮成果存到实例上
        self.context.extend(all_context)
        self.research_sources.extend(all_sources)

        # Trim context to stay within word limits
        # 正经注释：裁剪上下文到词数限制内 / 大白话注释：内容太多的话裁一裁，AI 看不完
        trimmed_context = trim_context_to_word_limit(all_context)
        logger.info(f"Trimmed context from {len(all_context)} items to {len(trimmed_context)} items to stay within word limit")

        return {
            'learnings': list(set(all_learnings)),  # 正经注释：去重后返回 / 大白话注释：去掉重复的发现
            'visited_urls': list(all_visited_urls),
            'citations': all_citations,
            'context': trimmed_context,
            'sources': all_sources
        }

    async def run(self, on_progress=None) -> str:
        """Run the deep research process and generate final report

        【正经注释】
        深度研究的入口方法。完整流程：
        1. 记录初始成本和时间
        2. 生成研究计划（后续问题）
        3. 将原始查询与后续问题合并为增强查询
        4. 调用递归 deep_research 执行多层级研究
        5. 计算并记录研究成本
        6. 将学习发现与引用合并，生成带引用的上下文
        7. 裁剪到词数限制，设置到 researcher 实例上
        注意：此方法只返回上下文，不生成报告（报告由主 agent 负责生成）。

        【大白话注释】
        "一键开始深度研究"按钮背后的函数。
        流程：先想几个问题 -> 把问题和原始查询拼在一起 -> 开始递归搜索 ->
        搜完后把所有发现整理好（带上来源引用） -> 塞回 researcher 的口袋里。
        注意它不写报告，只负责把资料找齐，写报告的事交给别人。

        Args:
            on_progress: 进度回调函数
        Returns:
            str: 最终的研究上下文字符串（带引用）
        """
        print(f"\n🔍 DEEP RESEARCH: Starting with breadth={self.breadth}, depth={self.depth}, concurrency={self.concurrency_limit}", flush=True)
        start_time = time.time()  # 正经注释：记录开始时间用于计算总耗时 / 大白话注释：按下秒表

        # Log initial costs
        # 正经注释：记录初始 API 调用成本 / 大白话注释：记下刚开始花了多少钱
        initial_costs = self.researcher.get_costs()

        follow_up_questions = await self.generate_research_plan(self.researcher.query)  # 正经注释：生成研究计划 / 大白话注释：先想几个问题
        answers = ["Automatically proceeding with research"] * len(follow_up_questions)  # 正经注释：自动填充答案（无需用户交互） / 大白话注释：不用等用户回答，直接往下走

        qa_pairs = [f"Q: {q}\nA: {a}" for q, a in zip(follow_up_questions, answers)]  # 正经注释：构建问答对 / 大白话注释：把问题和自动答案配对
        combined_query = f"""
        Initial Query: {self.researcher.query}\nFollow - up Questions and Answers:\n
        """ + "\n".join(qa_pairs)  # 正经注释：合并原始查询与问答对作为增强查询 / 大白话注释：把原始问题和后续问题拼成一份大问卷

        results = await self.deep_research(  # 正经注释：执行递归深度研究 / 大白话注释：开始挖！
            query=combined_query,
            breadth=self.breadth,
            depth=self.depth,
            on_progress=on_progress
        )

        # Get costs after deep research
        # 正经注释：计算深度研究期间产生的 API 成本 / 大白话注释：算算花了多少钱
        research_costs = self.researcher.get_costs() - initial_costs

        # Log research costs if we have a log handler
        # 正经注释：如果配置了日志处理器，记录研究成本 / 大白话注释：有日志工具的话就记一下开销
        if self.researcher.log_handler:
            await self.researcher._log_event("research", step="deep_research_costs", details={
                "research_costs": research_costs,
                "total_costs": self.researcher.get_costs()
            })

        # Prepare context with citations
        # 正经注释：将学习发现与引用信息合并，构建带引用的上下文 / 大白话注释：给每条发现加上"来自哪里"的标注
        context_with_citations = []
        for learning in results['learnings']:
            citation = results['citations'].get(learning, '')
            if citation:
                context_with_citations.append(f"{learning} [Source: {citation}]")  # 正经注释：有引用则附加来源 / 大白话注释：有来源就标上
            else:
                context_with_citations.append(learning)  # 正经注释：无引用则直接添加 / 大白话注释：没来源也不丢

        # Add all research context
        # 正经注释：追加完整的研究上下文 / 大白话注释：把搜到的完整内容也加进去
        if results.get('context'):
            context_with_citations.extend(results['context'])

        # Trim final context to word limit
        # 正经注释：最终裁剪上下文到词数限制 / 大白话注释：最后一道关卡，太长就砍
        final_context = trim_context_to_word_limit(context_with_citations)

        # Set enhanced context and visited URLs
        # 正经注释：将最终上下文和已访问 URL 设置回 researcher 实例 / 大白话注释：把成果塞回研究员的口袋
        self.researcher.context = "\n".join(final_context)
        self.researcher.visited_urls = results['visited_urls']

        # Set research sources
        # 正经注释：设置研究来源列表 / 大白话注释：资料来源也存好
        if results.get('sources'):
            self.researcher.research_sources = results['sources']

        # Log total execution time
        # 正经注释：记录并输出总执行时间和成本 / 大白话注释：停秒表，汇报耗时和花费
        end_time = time.time()
        execution_time = timedelta(seconds=end_time - start_time)
        logger.info(f"Total research execution time: {execution_time}")
        logger.info(f"Total research costs: ${research_costs:.2f}")

        # Return the context - don't generate report here as it will be done by the main agent
        # 正经注释：返回上下文而非报告，报告生成由主 agent 的 write_report 流程负责 / 大白话注释：只把资料交回去，写报告是别人的活
        return self.researcher.context
