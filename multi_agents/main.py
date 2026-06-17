from dotenv import load_dotenv
import sys
import os
import uuid
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from multi_agents.agents import ChiefEditorAgent
import asyncio
import json
from gpt_researcher.utils.enum import Tone

# Run with LangSmith if API key is set
if os.environ.get("LANGCHAIN_API_KEY"):
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
load_dotenv()

def open_task():
    """
    读取多 Agent 任务配置

    【正经注释】
    从当前 multi_agents 目录下的 task.json 加载任务配置，并在存在 STRATEGIC_LLM
    环境变量时覆盖配置中的 model 字段，用于统一控制多 Agent 工作流使用的模型。

    【大白话注释】
    这个函数就是先把 task.json 里的默认任务设置读出来。
    如果你在环境变量里指定了 STRATEGIC_LLM，就优先用环境变量里的模型，
    不再用 task.json 里写死的 model。

    Returns:
        dict: 多 Agent 任务配置（大白话：后面总编辑 Agent 要拿着这份配置开工）
    """
    # 正经注释：获取当前脚本所在目录，确保无论从哪里启动都能定位到 multi_agents 目录。
    # 大白话注释：先找到这个 main.py 自己在哪个文件夹里。
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # 正经注释：基于脚本目录构造 task.json 的绝对路径，避免依赖当前工作目录。
    # 大白话注释：拼出 task.json 的完整地址，防止从别的地方启动时找错文件。
    task_json_path = os.path.join(current_dir, 'task.json')

    # 正经注释：读取 JSON 配置文件并解析为 Python 字典。
    # 大白话注释：打开 task.json，把里面的配置变成 Python 能用的数据。
    with open(task_json_path, 'r') as f:
        task = json.load(f)

    if not task:
        raise Exception("No task found. Please ensure a valid task.json file is present in the multi_agents directory and contains the necessary task information.")

    # 正经注释：允许通过 STRATEGIC_LLM 环境变量覆盖 task.json 中的模型配置。
    # 大白话注释：如果外面单独指定了模型，就听外面的，不用配置文件里的。
    strategic_llm = os.environ.get("STRATEGIC_LLM")
    if strategic_llm and ":" in strategic_llm:
        # 正经注释：兼容 provider:model-name 格式，仅提取冒号后的模型名写入任务配置。
        # 大白话注释：比如 anthropic:claude-xxx，只拿 claude-xxx 这一段。
        model_name = strategic_llm.split(":", 1)[1]
        task["model"] = model_name
    elif strategic_llm:
        task["model"] = strategic_llm

    return task

async def run_research_task(query, websocket=None, stream_output=None, tone=Tone.Objective, headers=None):
    task = open_task()
    task["query"] = query

    chief_editor = ChiefEditorAgent(task, websocket, stream_output, tone, headers)
    research_report = await chief_editor.run_research_task()

    if websocket and stream_output:
        await stream_output("logs", "research_report", research_report, websocket)

    return research_report

async def main():
    task = open_task()

    chief_editor = ChiefEditorAgent(task)
    research_report = await chief_editor.run_research_task(task_id=uuid.uuid4())

    return research_report

if __name__ == "__main__":
    asyncio.run(main())
