# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GPT Researcher is an LLM-based autonomous agent that conducts web and local research on any topic, producing detailed reports with citations. It uses a planner-executor-publisher pattern with parallelized agent work. The backend is Python/FastAPI; the frontend has both a lightweight static HTML version and a production Next.js app.

## Common Commands

### Backend
```bash
# Install dependencies
pip install -r requirements.txt

# Run the FastAPI server (development, with reload)
python -m uvicorn main:app --reload

# Run the FastAPI server (alternative via main.py directly)
python main.py

# Run with Docker
docker-compose up --build
```

### Frontend (Next.js)
```bash
cd frontend/nextjs
npm install
npm run dev          # Development server on :3000
npm run build        # Production build
```

### Testing
```bash
python -m pytest                              # Run all tests
python -m pytest tests/test_costs.py          # Run a single test file
python -m pytest tests/test_costs.py::test_fn # Run a single test function
python -m pytest -v                           # Verbose output
```

pytest config: `asyncio_mode = "strict"`, test files match `test_*.py`, testpaths = `tests/`.

### CLI
```bash
python cli.py "<query>" --report_type research_report --tone Objective
```

## Architecture

### Core Research Flow

```
User Query → GPTResearcher (gpt_researcher/agent.py)
  │
  ├─ choose_agent() → determines agent type + role prompt
  ├─ ResearchConductor (skills/researcher.py)
  │    ├─ plan_research() → generates sub-queries
  │    ├─ For each sub_query: _process_sub_query()
  │    │    ├─ Retriever.search() → web results
  │    │    ├─ Scraper → page content
  │    │    └─ ContextManager → filtered context
  │    └─ Aggregate all contexts
  ├─ [Optional] ImageGenerator (skills/image_generator.py)
  ├─ [Optional] DeepResearchSkill (skills/deep_research.py) — recursive tree exploration
  └─ ReportGenerator (skills/writer.py) → Markdown report
```

### Key Directories

| Path | Purpose |
|------|---------|
| `gpt_researcher/agent.py` | Main `GPTResearcher` orchestrator class |
| `gpt_researcher/skills/` | Core capabilities: `researcher.py`, `writer.py`, `browser.py`, `context_manager.py`, `curator.py`, `deep_research.py`, `image_generator.py` |
| `gpt_researcher/prompts.py` | All prompt templates via `PromptFamily` |
| `gpt_researcher/actions/` | Shared actions: `retriever.py` (retriever factory), `web_scraping.py`, `query_processing.py`, `report_generation.py`, `agent_creator.py`, `markdown_processing.py` |
| `gpt_researcher/config/` | Config system; defaults in `variables/default.py` |
| `gpt_researcher/retrievers/` | Search engine integrations: tavily, google, duckduckgo, bing, arxiv, semantic_scholar, pubmed_central, exa, searx, serpapi, serper, searchapi, bocha, xquik, openalex, mcp, custom |
| `gpt_researcher/scraper/` | Scraping backends: beautiful_soup, browser, firecrawl, pymupdf, tavily_extract, arxiv, web_base_loader |
| `gpt_researcher/llm_provider/` | LLM abstraction via `GenericLLMProvider` (supports any LangChain-compatible model) |
| `gpt_researcher/memory/` | Embedding-based memory (`embeddings.py`) |
| `backend/server/` | FastAPI app (`app.py`), WebSocket manager, server utilities |
| `backend/report_type/` | Report type handlers: `BasicReport`, `DetailedReport`, `DeepResearch` |
| `backend/chat/` | Chat agent with memory for post-report Q&A |
| `multi_agents/` | LangGraph-based multi-agent system (Browser, Editor, Researcher, Reviewer, Revisor, Writer, Publisher) |
| `multi_agents_ag2/` | AG2-based multi-agent system |
| `frontend/` | Static HTML frontend (`index.html`, `scripts.js`, `styles.css`) |
| `frontend/nextjs/` | Next.js + Tailwind production frontend |
| `tests/` | Test suite |

### Configuration System

Config keys are **lowercased** when accessed at runtime. Defined as uppercase in `default.py`:
```python
# In default.py: "SMART_LLM": "gpt-4.1"
# Access as: self.cfg.smart_llm
```

Priority: **Environment Variables → JSON Config File → Default Values**

Three LLM tiers: `FAST_LLM` (quick tasks), `SMART_LLM` (report writing), `STRATEGIC_LLM` (reasoning/research planning). Model format: `provider:model-name` (e.g., `openai:gpt-4.1`, `anthropic:claude-sonnet-4-6`).

### Adding a New Retriever

1. Create `gpt_researcher/retrievers/<name>/<name>.py` with an async `search(self, max_results) -> list[dict]` returning `[{"title", "href", "body"}]`
2. Add a `match` case in `gpt_researcher/actions/retriever.py` → `get_retriever()`
3. Export from `gpt_researcher/retrievers/__init__.py`
4. Set `RETRIEVER=<name>` in config or env

Multiple retrievers can be used simultaneously: `RETRIEVER=tavily,mcp`

### WebSocket Streaming

Real-time research progress streams via WebSocket at `/ws`. The `stream_output()` function in `gpt_researcher/actions/__init__.py` sends typed events (`logs`, `report`, `path`, etc.). Always guard with `if websocket:` before calling.

### Report Types

Enum values in `gpt_researcher/utils/enum.py`: `research_report`, `resource_report`, `outline_report`, `custom_report`, `detailed_report`, `subtopic_report`, `deep` (deep research with recursive tree exploration).

### Report Sources

`web`, `local` (documents from `DOC_PATH`), `hybrid`, `static`, `langchain_documents`, `langchain_vectorstore`.

## Key Conventions

- All core research methods are **async** — always use `await`
- Use graceful degradation in skills: return empty lists on failure, never crash
- The `GPTResearcher` class is the single entry point for programmatic usage
- `GenericLLMProvider` wraps any LangChain-compatible chat model
- LangSmith tracing: set `LANGCHAIN_TRACING_V2=true` + `LANGCHAIN_API_KEY`

## Required API Keys

- `OPENAI_API_KEY` — primary LLM provider
- `TAVILY_API_KEY` — default search retriever
- Optional: `GOOGLE_API_KEY` (image generation), various retriever-specific keys