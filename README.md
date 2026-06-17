# EcomResearcher · 跨境电商 AI 选品与市场调研助手

> 基于 [GPT Researcher](https://github.com/assafelovic/gpt-researcher) 与 LangGraph 二次开发的跨境电商垂直领域多 Agent 工作流。
> 输入品类关键词，自动完成市场趋势、竞品格局、用户评论痛点研究，生成机会评分、结构化选品报告、质量检查与执行审计日志。

## 它能展示什么

- 趋势 / 竞品 / 评论 **三路并发**研究
- **LLM 打分 + 规则兜底**（DeepSeek 或任意 OpenAI 兼容模型）
- **WebSocket** 实时进度流（8 段阶段推送）
- **审计日志** + **质量评估**（引用覆盖率 / 证据充分度 / 风险披露 / 过度确定性拦截）
- 失败降级，长链路任务稳定不崩

## 标准样例（无需运行即可阅读）

| Case | 深度 | 报告 | 评估摘要 |
|------|------|------|----------|
| Portable Blender | standard | [report](outputs/ecommerce/demo-cases/portable-blender/report.md) | [evaluation](outputs/ecommerce/demo-cases/portable-blender/evaluation.json) |
| Pet Water Fountain | standard | [report](outputs/ecommerce/demo-cases/pet-water-fountain/report.md) | [evaluation](outputs/ecommerce/demo-cases/pet-water-fountain/evaluation.json) |
| Standing Desk | deep | [report](outputs/ecommerce/demo-cases/standing-desk/report.md) | [evaluation](outputs/ecommerce/demo-cases/standing-desk/evaluation.json) |

## 快速开始

```bash
pip install -r requirements.txt
# .env: TAVILY_API_KEY=...  OPENAI_API_KEY=...  OPENAI_BASE_URL=...  SMART_LLM=openai:<model>
python -m multi_agents.ecommerce --query "portable blender" --market US --depth standard
```

输出：`outputs/ecommerce/<关键词>-{report.md,audit.json,quality.json,evaluation.json}` + 全链路日志 `logs/ecommerce/<时间戳>_<关键词>.log`。

## 界面预览

启动后端 `python -m uvicorn main:app --port 8000`，浏览器访问：

- 研究页：`http://localhost:8000/site/ecommerce.html`（输入品类 → 实时进度 → 评分雷达图 → 报告）
- 评估对比页：`http://localhost:8000/site/ecommerce-eval.html`（三个 case 横向对比）

> 截图待补充：运行后将界面截图保存到 `docs/assets/ecommerce/{home,workflow,evaluation}.png`（见该目录 PLACEHOLDER）。

## 简历亮点

- 在开源 GPT Researcher 上二次开发跨境电商选品垂直多 Agent 工作流（LangGraph 编排 7 个 Agent，三路并发研究）
- LLM 结构化打分 + 规则降级兜底；WebSocket 阶段流式进度；审计日志与质量评估（引用覆盖率 / 证据充分度 / 风险披露 / 过度确定性）
- 标准化 demo case + 评估对比页，可重复导出与横向比较

## 文档

- 设计文档：`docs/superpowers/specs/2026-06-18-ecommerce-research-agent-design.md`
- 实现计划：`docs/superpowers/plans/2026-06-18-ecommerce-research-agent.md`
- 使用说明：`docs/ecommerce-researcher.md`

---

<!-- 以下为原项目 GPT Researcher 的说明；EcomResearcher 在其基础上二次开发。 -->

<div align="center" id="top">

<img src="https://github.com/assafelovic/gpt-researcher/assets/13554167/20af8286-b386-44a5-9a83-3be1365139c3" alt="Logo" width="80">

####

[![Website](https://img.shields.io/badge/Official%20Website-gptr.dev-teal?style=for-the-badge&logo=world&logoColor=white&color=0891b2)](https://gptr.dev)
[![Documentation](https://img.shields.io/badge/Documentation-DOCS-f472b6?logo=googledocs&logoColor=white&style=for-the-badge)](https://docs.gptr.dev)
[![Discord](https://img.shields.io/discord/1127851779011391548?logo=discord&logoColor=white&label=Discord&color=34b76a&style=for-the-badge)](https://discord.gg/QgZXvJAccX)


[![PyPI version](https://img.shields.io/pypi/v/gpt-researcher?logo=pypi&logoColor=white&style=flat)](https://badge.fury.io/py/gpt-researcher)
![GitHub Release](https://img.shields.io/github/v/release/assafelovic/gpt-researcher?style=flat&logo=github)
[![Open In Colab](https://img.shields.io/static/v1?message=Open%20in%20Colab&logo=googlecolab&labelColor=grey&color=yellow&label=%20&style=flat&logoSize=40)](https://colab.research.google.com/github/assafelovic/gpt-researcher/blob/master/docs/docs/examples/pip-run.ipynb)
[![Docker Image Version](https://img.shields.io/docker/v/elestio/gpt-researcher/latest?arch=amd64&style=flat&logo=docker&logoColor=white&color=1D63ED)](https://hub.docker.com/r/gptresearcher/gpt-researcher)
[![Skill](https://img.shields.io/badge/Claude%20Skill-skills.sh-blueviolet?style=flat&logo=anthropic&logoColor=white)](https://skills.sh/assafelovic/gpt-researcher/gpt-researcher)
[![Twitter Follow](https://img.shields.io/twitter/follow/assaf_elovic?style=social)](https://twitter.com/assaf_elovic)

[English](README.md) | [中文](README-zh_CN.md) | [日本語](README-ja_JP.md) | [한국어](README-ko_KR.md)

</div>

# 🔎 GPT Researcher

**GPT Researcher the first open deep research agent designed for both web and local research on any given task.** 

The agent produces detailed, factual, and unbiased research reports with citations. GPT Researcher provides a full suite of customization options to create tailor made and domain specific research agents. Inspired by the recent [Plan-and-Solve](https://arxiv.org/abs/2305.04091) and [RAG](https://arxiv.org/abs/2005.11401) papers, GPT Researcher addresses misinformation, speed, determinism, and reliability by offering stable performance and increased speed through parallelized agent work.

**Our mission is to empower individuals and organizations with accurate, unbiased, and factual information through AI.**

## Why GPT Researcher?

- Objective conclusions for manual research can take weeks, requiring vast resources and time.
- LLMs trained on outdated information can hallucinate, becoming irrelevant for current research tasks.
- Current LLMs have token limitations, insufficient for generating long research reports.
- Limited web sources in existing services lead to misinformation and shallow results.
- Selective web sources can introduce bias into research tasks.

## Demo
<a href="https://www.youtube.com/watch?v=f60rlc_QCxE" target="_blank" rel="noopener">
  <img src="https://github.com/user-attachments/assets/ac2ec55f-b487-4b3f-ae6f-b8743ad296e4" alt="Demo video" width="800" target="_blank" />
</a>

## Install as Claude Skill

Extend Claude's deep research capabilities by installing GPT Researcher as a [Claude Skill](https://skills.sh/assafelovic/gpt-researcher/gpt-researcher):

```bash
npx skills add assafelovic/gpt-researcher
```

Once installed, Claude can leverage GPT Researcher's deep research capabilities directly within your conversations.

## Architecture

The core idea is to utilize 'planner' and 'execution' agents. The planner generates research questions, while the execution agents gather relevant information. The publisher then aggregates all findings into a comprehensive report.

<div align="center">
<img align="center" height="600" src="https://github.com/assafelovic/gpt-researcher/assets/13554167/4ac896fd-63ab-4b77-9688-ff62aafcc527">
</div>

Steps:
* Create a task-specific agent based on a research query.
* Generate questions that collectively form an objective opinion on the task.
* Use a crawler agent for gathering information for each question.
* Summarize and source-track each resource.
* Filter and aggregate summaries into a final research report.

## Tutorials
 - [How it Works](https://docs.gptr.dev/blog/building-gpt-researcher)
 - [How to Install](https://www.loom.com/share/04ebffb6ed2a4520a27c3e3addcdde20?sid=da1848e8-b1f1-42d1-93c3-5b0b9c3b24ea)
 - [Live Demo](https://www.loom.com/share/6a3385db4e8747a1913dd85a7834846f?sid=a740fd5b-2aa3-457e-8fb7-86976f59f9b8)

## Features

- 📝 Generate detailed research reports using web and local documents.
- 🖼️ Smart image scraping and filtering for reports.
- 🍌 **AI-generated inline images** using Google Gemini (Nano Banana) for visual illustrations.
- 📜 Generate detailed reports exceeding 2,000 words.
- 🌐 Aggregate over 20 sources for objective conclusions.
- 🖥️ Frontend available in lightweight (HTML/CSS/JS) and production-ready (NextJS + Tailwind) versions.
- 🔍 JavaScript-enabled web scraping.
- 📂 Maintains memory and context throughout research.
- 📄 Export reports to PDF, Word, and other formats.

## 📖 Documentation

See the [Documentation](https://docs.gptr.dev/docs/gpt-researcher/getting-started) for:
- Installation and setup guides
- Configuration and customization options
- How-To examples
- Full API references

## ⚙️ Getting Started

### Installation

1. Install Python 3.11 or later. [Guide](https://www.tutorialsteacher.com/python/install-python).
2. Clone the project and navigate to the directory:

    ```bash
    git clone https://github.com/assafelovic/gpt-researcher.git
    cd gpt-researcher
    ```

3. Set up API keys by exporting them or storing them in a `.env` file.

    ```bash
    export OPENAI_API_KEY={Your OpenAI API Key here}
    export TAVILY_API_KEY={Your Tavily API Key here}
    ```

    (Optional) For enhanced tracing and observability, you can also set:
    
    ```bash
    # export LANGCHAIN_TRACING_V2=true
    # export LANGCHAIN_API_KEY={Your LangChain API Key here}
    ```

    For custom OpenAI-compatible APIs (e.g., local models, other providers), you can also set:
    
    ```bash
    export OPENAI_BASE_URL={Your custom API base URL here}
    ```

4. Install dependencies and start the server:

    ```bash
    pip install -r requirements.txt
    python -m uvicorn main:app --reload
    ```

Visit [http://localhost:8000](http://localhost:8000) to start.

For other setups (e.g., Poetry or virtual environments), check the [Getting Started page](https://docs.gptr.dev/docs/gpt-researcher/getting-started).

## Run as PIP package
```bash
pip install gpt-researcher

```
### Example Usage:
```python
...
from gpt_researcher import GPTResearcher

query = "why is Nvidia stock going up?"
researcher = GPTResearcher(query=query)
# Conduct research on the given query
research_result = await researcher.conduct_research()
# Write the report
report = await researcher.write_report()
...
```

**For more examples and configurations, please refer to the [PIP documentation](https://docs.gptr.dev/docs/gpt-researcher/gptr/pip-package) page.**

### 🔧 MCP Client
GPT Researcher supports MCP integration to connect with specialized data sources like GitHub repositories, databases, and custom APIs. This enables research from data sources alongside web search.

```bash
export RETRIEVER=tavily,mcp  # Enable hybrid web + MCP research
```

```python
from gpt_researcher import GPTResearcher
import asyncio
import os

async def mcp_research_example():
    # Enable MCP with web search
    os.environ["RETRIEVER"] = "tavily,mcp"
    
    researcher = GPTResearcher(
        query="What are the top open source web research agents?",
        mcp_configs=[
            {
                "name": "github",
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-github"],
                "env": {"GITHUB_TOKEN": os.getenv("GITHUB_TOKEN")}
            }
        ]
    )
    
    research_result = await researcher.conduct_research()
    report = await researcher.write_report()
    return report
```

> For comprehensive MCP documentation and advanced examples, visit the [MCP Integration Guide](https://docs.gptr.dev/docs/gpt-researcher/retrievers/mcp-configs).

## 🍌 Inline Image Generation

GPT Researcher can automatically generate and embed AI-created illustrations in your research reports using Google's Gemini models (Nano Banana).

```bash
# Enable in your .env file
IMAGE_GENERATION_ENABLED=true
GOOGLE_API_KEY=your_google_api_key
IMAGE_GENERATION_MODEL=models/gemini-2.5-flash-image
```

When enabled, the system will:
1. Analyze your research context to identify visualization opportunities
2. Pre-generate 2-3 relevant images during the research phase
3. Embed them inline as the report is written

Images are generated with dark-mode styling that matches the GPT Researcher UI, featuring professional infographic aesthetics with teal accents.

[Learn more about Image Generation](https://docs.gptr.dev/docs/gpt-researcher/gptr/image_generation) in our documentation.

## ✨ Deep Research

GPT Researcher now includes Deep Research - an advanced recursive research workflow that explores topics with agentic depth and breadth. This feature employs a tree-like exploration pattern, diving deeper into subtopics while maintaining a comprehensive view of the research subject.

- 🌳 Tree-like exploration with configurable depth and breadth
- ⚡️ Concurrent processing for faster results
- 🤝 Smart context management across research branches
- ⏱️ Takes ~5 minutes per deep research
- 💰 Costs ~$0.4 per research (using `o3-mini` on "high" reasoning effort)

[Learn more about Deep Research](https://docs.gptr.dev/docs/gpt-researcher/gptr/deep_research) in our documentation.

## Run with Docker

> **Step 1** - [Install Docker](https://docs.gptr.dev/docs/gpt-researcher/getting-started/getting-started-with-docker)

> **Step 2** - Clone the '.env.example' file, add your API Keys to the cloned file and save the file as '.env'

> **Step 3** - Within the docker-compose file comment out services that you don't want to run with Docker.

```bash
docker-compose up --build
```

If that doesn't work, try running it without the dash:
```bash
docker compose up --build
```

> **Step 4** - By default, if you haven't uncommented anything in your docker-compose file, this flow will start 2 processes:
 - the Python server running on localhost:8000<br>
 - the React app running on localhost:3000<br>

Visit localhost:3000 on any browser and enjoy researching!


## 📄 Research on Local Documents

You can instruct the GPT Researcher to run research tasks based on your local documents. Currently supported file formats are: PDF, plain text, CSV, Excel, Markdown, PowerPoint, and Word documents.

Step 1: Add the env variable `DOC_PATH` pointing to the folder where your documents are located.

```bash
export DOC_PATH="./my-docs"
```

Step 2: 
 - If you're running the frontend app on localhost:8000, simply select "My Documents" from the "Report Source" Dropdown Options.
 - If you're running GPT Researcher with the [PIP package](https://docs.tavily.com/guides/gpt-researcher/gpt-researcher#pip-package), pass the `report_source` argument as "local" when you instantiate the `GPTResearcher` class [code sample here](https://docs.gptr.dev/docs/gpt-researcher/context/tailored-research).


## 🤖 MCP Server

We've moved our MCP server to a dedicated repository: [gptr-mcp](https://github.com/assafelovic/gptr-mcp).

The GPT Researcher MCP Server enables AI applications like Claude to conduct deep research. While LLM apps can access web search tools with MCP, GPT Researcher MCP delivers deeper, more reliable research results.

Features:
- Deep research capabilities for AI assistants
- Higher quality information with optimized context usage
- Comprehensive results with better reasoning for LLMs
- Claude Desktop integration

For detailed installation and usage instructions, please visit the [official repository](https://github.com/assafelovic/gptr-mcp).


## 👪 Multi-Agent Assistant
As AI evolves from prompt engineering and RAG to multi-agent systems, we're excited to introduce multi-agent assistants built with [LangGraph](https://python.langchain.com/v0.1/docs/langgraph/) and [AG2](https://github.com/ag2ai/ag2).

By using multi-agent frameworks, the research process can be significantly improved in depth and quality by leveraging multiple agents with specialized skills. Inspired by the recent [STORM](https://arxiv.org/abs/2402.14207) paper, this project showcases how a team of AI agents can work together to conduct research on a given topic, from planning to publication.

An average run generates a 5-6 page research report in multiple formats such as PDF, Docx and Markdown.

Check it out [here](https://github.com/assafelovic/gpt-researcher/tree/master/multi_agents) or head over to our documentation for [LangGraph](https://docs.gptr.dev/docs/gpt-researcher/multi_agents/langgraph) and [AG2](https://docs.gptr.dev/docs/gpt-researcher/multi_agents/ag2) for more information.

## 🛒 Ecommerce Demo Cases

This repo ships a vertical **cross-border ecommerce product-research** workflow (`multi_agents/ecommerce/`) built on top of the multi-agent stack, plus three committed canonical demo cases you can read without running anything:

| Case | Report | Evaluation |
|------|--------|------------|
| Portable Blender | [report.md](outputs/ecommerce/demo-cases/portable-blender/report.md) | [evaluation.json](outputs/ecommerce/demo-cases/portable-blender/evaluation.json) |
| Pet Water Fountain | [report.md](outputs/ecommerce/demo-cases/pet-water-fountain/report.md) | [evaluation.json](outputs/ecommerce/demo-cases/pet-water-fountain/evaluation.json) |
| Standing Desk (deep) | [report.md](outputs/ecommerce/demo-cases/standing-desk/report.md) | [evaluation.json](outputs/ecommerce/demo-cases/standing-desk/evaluation.json) |

Each case folder holds `report.md` / `audit.json` / `quality.json` / `evaluation.json`; the index is [`outputs/ecommerce/demo-cases/case-index.json`](outputs/ecommerce/demo-cases/case-index.json). See [`docs/ecommerce-researcher.md`](docs/ecommerce-researcher.md) for the full design, and regenerate them with:

```bash
python scripts/export_ecommerce_demo_cases.py --output-root outputs/ecommerce/demo-cases
```

## 🔍 Observability

GPT Researcher supports **LangSmith** for enhanced tracing and observability, making it easier to debug and optimize complex multi-agent workflows.

To enable tracing:
1. Set the following environment variables:
   ```bash
   export LANGCHAIN_TRACING_V2=true
   export LANGCHAIN_API_KEY=your_api_key
   export LANGCHAIN_PROJECT="gpt-researcher"
   ```
2. Run your research tasks as usual. All LangGraph-based agent interactions will be automatically traced and visualized in your LangSmith dashboard.

## 🖥️ Frontend Applications

GPT-Researcher now features an enhanced frontend to improve the user experience and streamline the research process. The frontend offers:

- An intuitive interface for inputting research queries
- Real-time progress tracking of research tasks
- Interactive display of research findings
- Customizable settings for tailored research experiences

Two deployment options are available:
1. A lightweight static frontend served by FastAPI
2. A feature-rich NextJS application for advanced functionality

For detailed setup instructions and more information about the frontend features, please visit our [documentation page](https://docs.gptr.dev/docs/gpt-researcher/frontend/introduction).

## 🚀 Contributing
We highly welcome contributions! Please check out [contributing](https://github.com/assafelovic/gpt-researcher/blob/master/CONTRIBUTING.md) if you're interested.

Please check out our [roadmap](https://trello.com/b/3O7KBePw/gpt-researcher-roadmap) page and reach out to us via our [Discord community](https://discord.gg/QgZXvJAccX) if you're interested in joining our mission.
<a href="https://github.com/assafelovic/gpt-researcher/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=assafelovic/gpt-researcher&max=1000" />
</a>
## ✉️ Support / Contact us
- [Community Discord](https://discord.gg/spBgZmm3Xe)
- Author Email: assaf.elovic@gmail.com

## 🛡 Disclaimer

This project, GPT Researcher, is an experimental application and is provided "as-is" without any warranty, express or implied. We are sharing codes for academic purposes under the Apache 2 license. Nothing herein is academic advice, and NOT a recommendation to use in academic or research papers.

Our view on unbiased research claims:
1. The main goal of GPT Researcher is to reduce incorrect and biased facts. How? We assume that the more sites we scrape the less chances of incorrect data. By scraping multiple sites per research, and choosing the most frequent information, the chances that they are all wrong is extremely low.
2. We do not aim to eliminate biases; we aim to reduce it as much as possible. **We are here as a community to figure out the most effective human/llm interactions.**
3. In research, people also tend towards biases as most have already opinions on the topics they research about. This tool scrapes many opinions and will evenly explain diverse views that a biased person would never have read.

---

<p align="center">
<a href="https://star-history.com/#assafelovic/gpt-researcher">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=assafelovic/gpt-researcher&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=assafelovic/gpt-researcher&type=Date" />
    <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=assafelovic/gpt-researcher&type=Date" />
  </picture>
</a>
</p>


<p align="right">
  <a href="#top">⬆️ Back to Top</a>
</p>
