"""Markdown 处理模块（Markdown Processing）
【正经注释】
本模块提供 Markdown 文本的处理功能，包括：
- 标题提取（extract_headers）：解析标题层级结构
- 章节提取（extract_sections）：按标题拆分为独立章节
- 目录生成（table_of_contents）：自动生成带缩进的 TOC
- 参考文献添加（add_references）：在报告末尾追加引用链接
【大白话注释】
这个文件就是"报告格式化工具"——把 Markdown 报告的标题挑出来、切成段、生成目录、加参考文献。
"""
import re															# 正经注释：正则表达式库 / 大白话注释：用模式匹配处理文字
import markdown														# 正经注释：Markdown 转 HTML 库 / 大白话注释：把 Markdown 变成网页格式
from typing import List, Dict										# 正经注释：类型提示 / 大白话注释：类型标记

def extract_headers(markdown_text: str) -> List[Dict]:
    """
    从 Markdown 文本中提取标题层级结构
    【正经注释】将 Markdown 转为 HTML 后解析 h1-h6 标签，构建嵌套的标题树。
    使用栈维护父子关系，level 决定层级深度。
    【大白话注释】把报告里所有的标题找出来，按层级排好：
    比如"一、概述"下面有"1.1 背景"、"1.2 目的"等。
    Args:
        markdown_text (str): Markdown 文本（大白话：报告内容）
    Returns:
        List[Dict]: 标题字典列表，含 level、text 和 children（大白话：标题树）
    """
    headers = []														# 正经注释：初始化标题列表 / 大白话注释：准备装标题
    parsed_md = markdown.markdown(markdown_text)						# 正经注释：将 Markdown 转为 HTML / 大白话注释：先变成网页格式
    lines = parsed_md.split("\n")										# 正经注释：按行分割 / 大白话注释：一行一行看

    stack = []															# 正经注释：栈结构维护标题层级 / 大白话注释：用栈记住"当前在哪个大标题下面"
    for line in lines:													# 正经注释：遍历每一行 / 大白话注释：一行一行看
        if line.startswith("<h") and len(line) > 2 and line[2].isdigit():	# 正经注释：检测 HTML 标题标签（h1-h6） / 大白话注释：看看是不是标题行
            level = int(line[2])										# 正经注释：提取标题级别（1-6） / 大白话注释：几级标题？
            header_text = line[line.index(">") + 1 : line.rindex("<")]	# 正经注释：提取标签间的标题文本 / 大白话注释：标题内容是什么

            while stack and stack[-1]["level"] >= level:				# 正经注释：弹出栈中级别 >= 当前的标题，回溯到父级 / 大白话注释：如果是同级或更深的标题，就弹出到上级
                stack.pop()

            header = {													# 正经注释：构建标题字典 / 大白话注释：把标题信息记下来
                "level": level,											# 正经注释：标题级别 / 大白话注释：几级
                "text": header_text,									# 正经注释：标题文本 / 大白话注释：标题内容
            }
            if stack:													# 正经注释：栈非空则当前标题是栈顶标题的子标题 / 大白话注释：如果在某个大标题下面，就是它的子标题
                stack[-1].setdefault("children", []).append(header)		# 正经注释：添加为父标题的子节点 / 大白话注释：加到子标题列表里
            else:														# 正经注释：栈空则当前标题是顶级标题 / 大白话注释：不在任何标题下面，就是顶级标题
                headers.append(header)									# 正经注释：添加到顶级标题列表 / 大白话注释：直接加到列表里

            stack.append(header)										# 正经注释：当前标题入栈 / 大白话注释：记住这个标题

    return headers														# 正经注释：返回标题树 / 大白话注释：交出去

def extract_sections(markdown_text: str) -> List[Dict[str, str]]:
    """
    从 Markdown 文本中按标题拆分为独立章节
    【正经注释】将 Markdown 转为 HTML 后，用正则按 h 标签拆分，
    每个章节包含标题和对应的内容文本。
    【大白话注释】把报告按标题切成一段一段的——每段有标题和内容。
    Args:
        markdown_text (str): Markdown 文本（大白话：报告内容）
    Returns:
        List[Dict]: 章节列表，每个含 section_title 和 written_content（大白话：切好的段落列表）
    """
    sections = []														# 正经注释：初始化章节列表 / 大白话注释：准备装切好的段落
    parsed_md = markdown.markdown(markdown_text)						# 正经注释：Markdown → HTML / 大白话注释：变成网页格式

    pattern = r'<h\d>(.*?)</h\d>(.*?)(?=<h\d>|$)'						# 正经注释：正则匹配标题+内容的模式 / 大白话注释：找到每个标题和它下面的内容
    matches = re.findall(pattern, parsed_md, re.DOTALL)					# 正经注释：全局匹配 / 大白话注释：全部找出来

    for title, content in matches:										# 正经注释：遍历每个匹配结果 / 大白话注释：一段一段整理
        clean_content = re.sub(r'<.*?>', '', content).strip()			# 正经注释：去除内容中的 HTML 标签 / 大白话注释：把 HTML 标签去掉，只要纯文字
        if clean_content:												# 正经注释：仅保留有内容的章节 / 大白话注释：有内容才留
            sections.append({
                "section_title": title.strip(),							# 正经注释：章节标题 / 大白话注释：小标题
                "written_content": clean_content						# 正经注释：章节内容 / 大白话注释：标题下面的正文
            })

    return sections														# 正经注释：返回章节列表 / 大白话注释：交出去

def table_of_contents(markdown_text: str) -> str:
    """
    从 Markdown 文本生成目录（TOC）
    【正经注释】基于 extract_headers 提取的标题树，递归生成带缩进的 Markdown 目录。
    每级缩进 4 个空格，子标题嵌套显示。
    【大白话注释】自动生成"目录"——报告开头那种"一、xxx ... 1"的东西。
    Args:
        markdown_text (str): Markdown 文本（大白话：报告内容）
    Returns:
        str: Markdown 格式的目录（大白话：生成的目录）
    """
    def generate_table_of_contents(headers, indent_level=0):			# 正经注释：递归生成目录的内部函数 / 大白话注释：递归——一层一层生成
        toc = ""														# 正经注释：初始化目录字符串 / 大白话注释：准备写目录
        for header in headers:											# 正经注释：遍历每个标题 / 大白话注释：一个标题一个标题来
            toc += " " * (indent_level * 4) + "- " + header["text"] + "\n"	# 正经注释：添加缩进 + 列表标记 + 标题文本 / 大白话注释：加上缩进和标题
            if "children" in header:									# 正经注释：有子标题则递归处理 / 大白话注释：如果有子标题就继续深入
                toc += generate_table_of_contents(header["children"], indent_level + 1)	# 正经注释：递归生成子标题目录 / 大白话注释：子标题再生成一层
        return toc														# 正经注释：返回当前层级的目录 / 大白话注释：交出去

    try:
        headers = extract_headers(markdown_text)						# 正经注释：先提取标题结构 / 大白话注释：先把标题找出来
        toc = "## Table of Contents\n\n" + generate_table_of_contents(headers)	# 正经注释：加上目录标题前缀 / 大白话注释：加上"目录"这个大标题
        return toc														# 正经注释：返回完整目录 / 大白话注释：交出去
    except Exception as e:												# 正经注释：出错时返回原始文本 / 大白话注释：出错了就返回原文
        print("table_of_contents Exception : ", e)
        return markdown_text											# 正经注释：降级返回原始 Markdown / 大白话注释：原样返回

def add_references(report_markdown: str, visited_urls: set) -> str:
    """
    在 Markdown 报告末尾添加参考文献
    【正经注释】将所有访问过的 URL 格式化为 Markdown 链接列表，
    追加到报告末尾作为参考文献章节。
    【大白话注释】在报告最后加上"参考资料"——把看过的网页链接都列出来。
    Args:
        report_markdown (str): 报告 Markdown 文本（大白话：报告内容）
        visited_urls (set): 访问过的 URL 集合（大白话：看过的网页链接）
    Returns:
        str: 带参考文献的报告（大白话：加了"参考资料"后的报告）
    """
    try:
        url_markdown = "\n\n\n## References\n\n"						# 正经注释：创建参考文献标题 / 大白话注释：写上"参考资料"标题
        url_markdown += "".join(f"- [{url}]({url})\n" for url in visited_urls)	# 正经注释：将每个 URL 格式化为 Markdown 链接 / 大白话注释：一个链接一行列出来
        updated_markdown_report = report_markdown + url_markdown		# 正经注释：拼接到报告末尾 / 大白话注释：把参考资料加到报告后面
        return updated_markdown_report									# 正经注释：返回更新后的报告 / 大白话注释：交出去
    except Exception as e:												# 正经注释：出错时返回原始报告 / 大白话注释：出错了就返回原报告
        print(f"Encountered exception in adding source urls : {e}")
        return report_markdown											# 正经注释：降级返回原始 Markdown / 大白话注释：原样返回
