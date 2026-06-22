# Ecommerce Visual Concept Agent Implementation Plan (v2)

> **v2 note:** This is the reviewed revision of `2026-06-23-ecommerce-visual-concept-agent.md`. The
> original is kept untouched. v2 folds in FIX-1..9 from the design/plan review (see **Revision Notes**
> at the bottom). No code is written by this document — it is a plan only.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a real Volcengine Ark Seedream image-generation layer that turns ecommerce research outputs into product concept images and Amazon Listing visual drafts, with artifacts, trace, evaluation, HITL review, API, and frontend support.

**Architecture:** Keep the existing LangGraph text research graph unchanged. Run `VisualConceptAgent` as a post-graph runner stage after trend/competitor/review/scoring/report/quality are available, append a `visual` AgentOps trace node, call a provider abstraction backed by `VolcArkJimengProvider`, download generated images to local artifacts, and expose visual results through the existing API/frontend/eval/run-store surfaces.

**Tech Stack:** Python 3.11+, FastAPI, LangGraph, existing ecommerce runner/state/evaluation stack, `volcengine-python-sdk[ark]`, `Pillow`, static HTML/vanilla JS frontend, pytest.

## Global Constraints

- The current working tree already contains uncommitted review fixes and the visual concept spec. Do not revert or overwrite them.
- Default visual model is `doubao-seedream-4-5-251128`.
- All Seedream models send `output_format="png"` — the official Ark SDK example sends it for `doubao-seedream-4-5-251128` too. ([FIX-9] supersedes the spec's old "4-5 does not support output_format" claim; the `_supports_output_format` model-capability branch was removed.)
- API keys must only be read from `ARK_API_KEY` or `VOLCENGINE_ARK_API_KEY`; never write keys into source, logs, trace, evaluation, human review, or artifacts.
- Visual generation failure must degrade to prompt-only or failed visual assets and must not break the main text research report.
- Default unit tests must not call the real Volcengine API.
- Real API verification must live in a manual smoke script.
- Visual image count is capped at 6 for the first implementation.
- **[FIX-5] Test runner:** Run every `pytest` / `py_compile` / `python` command with the project conda-env interpreter `C:/Users/lcmzz/.conda/envs/gpt-researcher-main/python.exe` (verified to import `mistune`, `langchain_community`, `PIL`, and `volcenginesdkarkruntime` / Ark SDK 5.0.35). The system `py` resolves to a C-drive Python 3.13 missing those deps and fails at collection. `D:/conda/python.exe` (conda base) lacks `langchain_community` and only suffices for ecommerce-scoped files — do not use it here. Shell note: the automated Run steps below use a forward-slash path that runs unquoted in the executor's Git Bash; in PowerShell prefix the call operator `&` and quote the path (the manual smoke step in Task 7 is already in PowerShell form).
- **[FIX-4] Pillow pre-flight:** `volc_ark_jimeng.py` imports `from PIL import Image` at module top, and `visual_concept.py` / `runner.py` import it transitively. A missing Pillow breaks collection of every downstream test (not just one case). Pillow is **not** currently in `requirements.txt` (image generation today uses `google-genai`/Imagen); it is likely present as a transitive dep of `python-pptx`, but that must be verified before Task 2 — see Task 2 Step 1.

---

## File Structure

- Create `multi_agents/ecommerce/tools/image_generation/__init__.py`: exports image generation dataclasses and provider.
- Create `multi_agents/ecommerce/tools/image_generation/base.py`: provider-neutral request/result dataclasses and protocol.
- Create `multi_agents/ecommerce/tools/image_generation/volc_ark_jimeng.py`: Volcengine Ark SDK provider, model parameter compatibility, image download, redacted failures.
- Create `multi_agents/ecommerce/agents/visual_concept.py`: builds visual brief, prompt slots, prompt records, calls image provider, appends visual trace node.
- Create `tests/test_ecommerce_image_provider.py`: fake SDK/downloader tests for provider behavior.
- Create `tests/test_ecommerce_visual_agent.py`: prompt slot selection, prompt-only fallback, provider success/partial failure, trace summary.
- Create `tests/test_ecommerce_runner_visual.py`: runner artifact/output_paths/evaluation integration.
- Create `tests/test_ecommerce_frontend_visual.py`: static frontend sanity checks for visual controls/panels.
- Create `scripts/smoke_jimeng_image_generation.py`: manual one-image SDK smoke test.
- Modify `requirements.txt`: add `volcengine-python-sdk[ark]` and `Pillow`.
- Modify `multi_agents/ecommerce/state.py`: add `visual_result` to state contracts and initial state.
- Modify `multi_agents/ecommerce/evaluation.py`: summarize visual result and visual human review counts.
- Modify `multi_agents/ecommerce/runner.py`: visual params, config defaults, visual stage, visual artifact output, run metadata.
- Modify `multi_agents/ecommerce/runtime/run_store.py`: load visual artifacts with run lookup.
- Modify `backend/server/ecommerce_api.py`: request fields, POST/WS passthrough, summary response.
- Modify `frontend/ecommerce.html`: visual controls and visual result grid.
- Modify `frontend/ecommerce-review.html`: visual asset review controls.
- Modify `frontend/ecommerce-eval.html`: visual metric display.

---

### Task 1: State, Dependencies, And Evaluation Summary

**Files:**
- Modify: `requirements.txt`
- Modify: `multi_agents/ecommerce/state.py`
- Modify: `multi_agents/ecommerce/evaluation.py`
- Test: `tests/test_ecommerce_state.py`
- Test: `tests/test_ecommerce_evaluation.py`

**Interfaces:**
- Consumes: existing `create_initial_state(query, target_market="US", platforms=None, depth="standard")`.
- Produces: `state["visual_result"]` default structure.
- Produces: `build_evaluation_summary(state)` fields `visual_enabled`, `visual_status`, `visual_prompt_count`, `visual_asset_count`, `visual_failed_asset_count`, `visual_total_tokens`, `visual_approved_count`, `visual_rejected_count`, `visual_needs_edit_count`.

- [ ] **Step 1: Add failing state test**

Add this test to `tests/test_ecommerce_state.py`:

```python
def test_create_initial_state_contains_visual_result():
    state = create_initial_state("portable blender")

    assert state["visual_result"] == {
        "enabled": False,
        "status": "skipped",
        "visual_brief": {},
        "prompts": [],
        "assets": [],
        "warnings": [],
        "usage": {},
    }
```

- [ ] **Step 2: Add failing evaluation tests**

Add this test to `tests/test_ecommerce_evaluation.py`:

```python
def test_build_evaluation_summary_counts_visual_metrics():
    state = {
        "audit_log": [],
        "trend_result": {"evidence": []},
        "competitor_result": {"evidence": []},
        "review_result": {"evidence": []},
        "opportunity_score": {},
        "quality_check": {},
        "visual_result": {
            "enabled": True,
            "status": "partial",
            "prompts": [{"asset_id": "visual_product_01"}, {"asset_id": "visual_listing_01"}],
            "assets": [
                {"asset_id": "visual_product_01", "status": "success"},
                {"asset_id": "visual_listing_01", "status": "failed"},
            ],
            "usage": {"total_tokens": 16384},
        },
        "human_review": {
            "visual_reviews": [
                {"asset_id": "visual_product_01", "status": "approved"},
                {"asset_id": "visual_listing_01", "status": "rejected"},
                {"asset_id": "visual_listing_02", "status": "needs_edit"},
            ]
        },
    }

    summary = build_evaluation_summary(state)

    assert summary["visual_enabled"] is True
    assert summary["visual_status"] == "partial"
    assert summary["visual_prompt_count"] == 2
    assert summary["visual_asset_count"] == 1
    assert summary["visual_failed_asset_count"] == 1
    assert summary["visual_total_tokens"] == 16384
    assert summary["visual_approved_count"] == 1
    assert summary["visual_rejected_count"] == 1
    assert summary["visual_needs_edit_count"] == 1
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
C:/Users/lcmzz/.conda/envs/gpt-researcher-main/python.exe -m pytest tests/test_ecommerce_state.py::test_create_initial_state_contains_visual_result tests/test_ecommerce_evaluation.py::test_build_evaluation_summary_counts_visual_metrics -q
```

Expected: FAIL because `visual_result` and visual summary fields do not exist.

- [ ] **Step 4: Add dependencies**

Append these lines under the existing LLM/image or utility dependency sections in `requirements.txt`:

```text
volcengine-python-sdk[ark]>=5.0.35
Pillow>=10.0.0
```

- [ ] **Step 5: Add visual_result to state contracts**

In `multi_agents/ecommerce/state.py`, add `visual_result` to `EcommerceResearchState`:

```python
    visual_result: dict[str, Any]        # 多模态视觉产物（brief/prompts/assets/usage/warnings）
```

Add `visual_result` to `EcommerceGraphState`:

```python
    visual_result: dict[str, Any]
```

Add this default to `create_initial_state()`:

```python
        "visual_result": {
            "enabled": False,
            "status": "skipped",
            "visual_brief": {},
            "prompts": [],
            "assets": [],
            "warnings": [],
            "usage": {},
        },
```

- [ ] **Step 6: Add visual summary helpers**

In `multi_agents/ecommerce/evaluation.py`, add this helper near `_summarize_mcp_context`:

```python
def _summarize_visual_result(visual_result: Mapping[str, Any] | None) -> dict[str, Any]:
    if not visual_result:
        return {
            "visual_enabled": False,
            "visual_status": "skipped",
            "visual_prompt_count": 0,
            "visual_asset_count": 0,
            "visual_failed_asset_count": 0,
            "visual_total_tokens": 0,
        }
    assets = visual_result.get("assets", [])
    usage = visual_result.get("usage", {})
    return {
        "visual_enabled": bool(visual_result.get("enabled", False)),
        "visual_status": visual_result.get("status", "skipped"),
        "visual_prompt_count": len(visual_result.get("prompts", [])),
        "visual_asset_count": sum(1 for row in assets if row.get("status") == "success"),
        "visual_failed_asset_count": sum(1 for row in assets if row.get("status") == "failed"),
        "visual_total_tokens": int(usage.get("total_tokens", 0) or 0),
    }


def _summarize_visual_reviews(review: Mapping[str, Any] | None) -> dict[str, int]:
    rows = review.get("visual_reviews", []) if review else []
    return {
        "visual_approved_count": sum(1 for row in rows if row.get("status") == "approved"),
        "visual_rejected_count": sum(1 for row in rows if row.get("status") == "rejected"),
        "visual_needs_edit_count": sum(1 for row in rows if row.get("status") == "needs_edit"),
    }
```

Then update `build_evaluation_summary()` after the existing human/eval/MCP summaries:

```python
    summary.update(_summarize_visual_result(state.get("visual_result")))
    summary.update(_summarize_visual_reviews(state.get("human_review")))
```

- [ ] **Step 7: Run tests to verify they pass**

Run:

```bash
C:/Users/lcmzz/.conda/envs/gpt-researcher-main/python.exe -m pytest tests/test_ecommerce_state.py tests/test_ecommerce_evaluation.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add requirements.txt multi_agents/ecommerce/state.py multi_agents/ecommerce/evaluation.py tests/test_ecommerce_state.py tests/test_ecommerce_evaluation.py
git commit -m "feat(ecommerce): add visual state and evaluation metrics"
```

---

### Task 2: Image Provider Abstraction And Volcengine Ark Seedream Provider

**Files:**
- Create: `multi_agents/ecommerce/tools/image_generation/__init__.py`
- Create: `multi_agents/ecommerce/tools/image_generation/base.py`
- Create: `multi_agents/ecommerce/tools/image_generation/volc_ark_jimeng.py`
- Test: `tests/test_ecommerce_image_provider.py`

**Interfaces:**
- Consumes: `redact_secrets(value)` from `multi_agents.ecommerce.runtime.policy_guard`.
- Produces: `ImageGenerationRequest`, `ImageGenerationResult`, `ImageGenerationProvider`, `VolcArkJimengProvider`.
- Produces: `VolcArkJimengProvider.generate(request: ImageGenerationRequest) -> ImageGenerationResult`.

- [ ] **Step 1: Verify Pillow is importable [FIX-4 pre-flight]**

`volc_ark_jimeng.py` will `from PIL import Image` at module top; a missing Pillow breaks collection of this file and every transitive importer (`visual_concept.py`, `runner.py`). Pillow is not in `requirements.txt` today. Verify it is actually importable in the conda env before writing any code:

```bash
C:/Users/lcmzz/.conda/envs/gpt-researcher-main/python.exe -c "import PIL; print(PIL.__version__)"
```

Expected: prints a version (e.g. `10.x.x`). If this raises `ModuleNotFoundError`, install it first:

```bash
C:/Users/lcmzz/.conda/envs/gpt-researcher-main/python.exe -m pip install "Pillow>=10.0.0"
```

Do not proceed to Step 2 until `import PIL` succeeds. (The Ark SDK itself, `volcenginesdkarkruntime`, is imported lazily inside `_client()` and is NOT required for unit tests — only Pillow is a hard import-time dependency.)

- [ ] **Step 2: Write provider tests**

Create `tests/test_ecommerce_image_provider.py`:

```python
from pathlib import Path

import pytest

from multi_agents.ecommerce.tools.image_generation.base import ImageGenerationRequest
from multi_agents.ecommerce.tools.image_generation.volc_ark_jimeng import VolcArkJimengProvider


class FakeImageData:
    def __init__(self, url="https://example.com/image.jpeg", size="2048x2048"):
        self.url = url
        self.size = size


class FakeUsage:
    generated_images = 1
    output_tokens = 100
    total_tokens = 100


class FakeResponse:
    def __init__(self, size="2048x2048"):
        self.data = [FakeImageData(size=size)]
        self.usage = FakeUsage()


class FakeImages:
    def __init__(self, response=None):
        self.kwargs = None
        self.response = response or FakeResponse()

    def generate(self, **kwargs):
        self.kwargs = kwargs
        return self.response


class FakeArkClient:
    def __init__(self, response=None):
        self.images = FakeImages(response)


def fake_downloader(url, target_path):
    path = Path(target_path).with_suffix(".jpg")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fake-image")
    return {
        "local_path": str(path),
        "mime_type": "image/jpeg",
        "width": 2048,
        "height": 2048,
    }


@pytest.mark.asyncio
async def test_seedream_45_sends_png_output_format(tmp_path):
    client = FakeArkClient()
    provider = VolcArkJimengProvider(
        output_dir=tmp_path,
        ark_client=client,
        downloader=fake_downloader,
    )

    result = await provider.generate(
        ImageGenerationRequest(
            asset_id="visual_product_01",
            prompt="portable blender product photo",
            model="doubao-seedream-4-5-251128",
        )
    )

    assert result.status == "success"
    # [FIX-9] 官方示例对 4-5 也发 output_format="png"
    assert client.images.kwargs["output_format"] == "png"
    assert client.images.kwargs["response_format"] == "url"
    assert Path(result.local_path).exists()
    assert result.width == 2048
    assert result.height == 2048


@pytest.mark.asyncio
async def test_provider_reads_local_image_size_when_sdk_omits_size(tmp_path):
    from PIL import Image

    def png_downloader(url, target_path):
        path = Path(target_path).with_suffix(".png")
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (32, 24), color=(255, 255, 255)).save(path)
        return {
            "local_path": str(path),
            "mime_type": "image/png",
            "width": 0,
            "height": 0,
        }

    client = FakeArkClient(FakeResponse(size=""))
    provider = VolcArkJimengProvider(
        output_dir=tmp_path,
        ark_client=client,
        downloader=png_downloader,
    )

    result = await provider.generate(
        ImageGenerationRequest(
            asset_id="visual_product_01",
            prompt="portable blender product photo",
            model="doubao-seedream-4-5-251128",
        )
    )

    assert result.status == "success"
    assert result.width == 32
    assert result.height == 24


@pytest.mark.asyncio
async def test_seedream_50_sends_png_output_format(tmp_path):
    client = FakeArkClient()
    provider = VolcArkJimengProvider(
        output_dir=tmp_path,
        ark_client=client,
        downloader=fake_downloader,
    )

    await provider.generate(
        ImageGenerationRequest(
            asset_id="visual_product_01",
            prompt="portable blender product photo",
            model="doubao-seedream-5-0-260128",
        )
    )

    assert client.images.kwargs["output_format"] == "png"


@pytest.mark.asyncio
async def test_missing_api_key_returns_failed_result(tmp_path, monkeypatch):
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    monkeypatch.delenv("VOLCENGINE_ARK_API_KEY", raising=False)
    provider = VolcArkJimengProvider(output_dir=tmp_path)

    result = await provider.generate(
        ImageGenerationRequest(
            asset_id="visual_product_01",
            prompt="portable blender product photo",
            model="doubao-seedream-4-5-251128",
        )
    )

    assert result.status == "failed"
    assert result.warning == "missing ARK_API_KEY"


@pytest.mark.asyncio
async def test_provider_error_is_redacted(tmp_path):
    class BrokenImages:
        def generate(self, **kwargs):
            raise RuntimeError("ARK_API_KEY=secret-token exploded")

    class BrokenClient:
        images = BrokenImages()

    provider = VolcArkJimengProvider(
        output_dir=tmp_path,
        ark_client=BrokenClient(),
        downloader=fake_downloader,
    )

    result = await provider.generate(
        ImageGenerationRequest(
            asset_id="visual_product_01",
            prompt="portable blender product photo",
            model="doubao-seedream-4-5-251128",
        )
    )

    assert result.status == "failed"
    assert "secret-token" not in result.warning
    assert "ARK_API_KEY=[REDACTED]" in result.warning


@pytest.mark.asyncio
async def test_provider_returns_failed_when_client_init_raises(tmp_path):
    # [FIX-8] an SDK import / Ark() init failure must surface as a failed result, not raise.
    provider = VolcArkJimengProvider(output_dir=tmp_path, api_key="fake-key")

    def boom():
        raise RuntimeError("ARK_API_KEY=secret-init Ark init exploded")

    provider._client = boom  # type: ignore[assignment]

    result = await provider.generate(
        ImageGenerationRequest(
            asset_id="visual_product_01",
            prompt="portable blender product photo",
            model="doubao-seedream-4-5-251128",
        )
    )

    assert result.status == "failed"
    assert "secret-init" not in result.warning
    assert "ARK_API_KEY=[REDACTED]" in result.warning
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
C:/Users/lcmzz/.conda/envs/gpt-researcher-main/python.exe -m pytest tests/test_ecommerce_image_provider.py -q
```

Expected: FAIL because `multi_agents.ecommerce.tools.image_generation` does not exist.

- [ ] **Step 4: Create provider base module**

Create `multi_agents/ecommerce/tools/image_generation/base.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ImageGenerationRequest:
    asset_id: str
    prompt: str
    model: str
    size: str = "2K"
    watermark: bool = False


@dataclass
class ImageGenerationResult:
    asset_id: str
    status: str
    remote_url: str = ""
    local_path: str = ""
    width: int = 0
    height: int = 0
    model: str = ""
    duration_ms: int = 0
    usage: dict = field(default_factory=dict)
    mime_type: str = ""
    warning: str = ""


class ImageGenerationProvider(Protocol):
    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        raise NotImplementedError
```

Create `multi_agents/ecommerce/tools/image_generation/__init__.py`:

```python
from multi_agents.ecommerce.tools.image_generation.base import (
    ImageGenerationProvider,
    ImageGenerationRequest,
    ImageGenerationResult,
)
from multi_agents.ecommerce.tools.image_generation.volc_ark_jimeng import (
    VolcArkJimengProvider,
)

__all__ = [
    "ImageGenerationProvider",
    "ImageGenerationRequest",
    "ImageGenerationResult",
    "VolcArkJimengProvider",
]
```

- [ ] **Step 5: Implement VolcArkJimengProvider**

Create `multi_agents/ecommerce/tools/image_generation/volc_ark_jimeng.py`:

```python
from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

import requests
from PIL import Image

from multi_agents.ecommerce.runtime.policy_guard import redact_secrets
from multi_agents.ecommerce.tools.image_generation.base import (
    ImageGenerationRequest,
    ImageGenerationResult,
)

Downloader = Callable[[str, Path], dict[str, Any]]

ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"


def _redacted_error(exc: Exception) -> str:
    redacted = redact_secrets({"error": str(exc)})
    return str(redacted.get("error", ""))


def _parse_size(value: str | None) -> tuple[int, int]:
    if not value or "x" not in value:
        return 0, 0
    left, right = value.lower().split("x", 1)
    try:
        return int(left), int(right)
    except ValueError:
        return 0, 0


def _extension_from_url_or_type(url: str, mime_type: str) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        return ".jpg" if suffix == ".jpeg" else suffix
    if mime_type == "image/png":
        return ".png"
    if mime_type == "image/webp":
        return ".webp"
    return ".jpg"


def _default_downloader(url: str, target_without_ext: Path) -> dict[str, Any]:
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    mime_type = response.headers.get("content-type", "").split(";")[0].strip()
    extension = _extension_from_url_or_type(url, mime_type)
    target = target_without_ext.with_suffix(extension)
    target.write_bytes(response.content)
    return {
        "local_path": str(target),
        "mime_type": mime_type or "image/jpeg",
        "width": 0,
        "height": 0,
    }


def _read_local_image_size(path_value: str) -> tuple[int, int]:
    if not path_value:
        return 0, 0
    path = Path(path_value)
    if not path.exists():
        return 0, 0
    try:
        with Image.open(path) as image:
            return image.size
    except Exception:
        return 0, 0


class VolcArkJimengProvider:
    def __init__(
        self,
        *,
        output_dir: str | Path,
        api_key: str | None = None,
        base_url: str = ARK_BASE_URL,
        ark_client: Any | None = None,
        downloader: Downloader | None = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.api_key = api_key or os.getenv("ARK_API_KEY") or os.getenv("VOLCENGINE_ARK_API_KEY")
        self.base_url = base_url
        self.ark_client = ark_client
        self.downloader = downloader or _default_downloader

    def _client(self) -> Any | None:
        if self.ark_client is not None:
            return self.ark_client
        if not self.api_key:
            return None
        from volcenginesdkarkruntime import Ark

        self.ark_client = Ark(base_url=self.base_url, api_key=self.api_key)
        return self.ark_client

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        started = time.time()
        # [FIX-8] _client() (imports + constructs the Ark SDK) is inside the try so an SDK
        # import error or Ark() init failure returns a failed result instead of raising —
        # preserves the "always return ImageGenerationResult" contract (smoke prints status=failed).
        try:
            client = self._client()
            if client is None:
                return ImageGenerationResult(
                    asset_id=request.asset_id,
                    status="failed",
                    model=request.model,
                    warning="missing ARK_API_KEY",
                )
            # [FIX-9] 官方 Ark 示例对所有 seedream 模型都发 output_format="png"（含 4-5），
            # 推翻 spec 旧说法"4-5 不支持 output_format"。
            kwargs: dict[str, Any] = {
                "model": request.model,
                "prompt": request.prompt,
                "size": request.size,
                "response_format": "url",
                "watermark": request.watermark,
                "output_format": "png",
            }
            response = await asyncio.to_thread(client.images.generate, **kwargs)
            image = response.data[0]
            remote_url = str(image.url)
            self.output_dir.mkdir(parents=True, exist_ok=True)
            target_without_ext = self.output_dir / request.asset_id
            download_meta = await asyncio.to_thread(
                self.downloader,
                remote_url,
                target_without_ext,
            )
            width, height = _parse_size(getattr(image, "size", ""))
            if not width or not height:
                width, height = _read_local_image_size(str(download_meta.get("local_path", "")))
            usage_obj = getattr(response, "usage", None)
            usage = {
                "generated_images": int(getattr(usage_obj, "generated_images", 0) or 0),
                "output_tokens": int(getattr(usage_obj, "output_tokens", 0) or 0),
                "total_tokens": int(getattr(usage_obj, "total_tokens", 0) or 0),
            }
            return ImageGenerationResult(
                asset_id=request.asset_id,
                status="success",
                remote_url=remote_url,
                local_path=str(download_meta.get("local_path", "")),
                width=width or int(download_meta.get("width", 0) or 0),
                height=height or int(download_meta.get("height", 0) or 0),
                model=request.model,
                duration_ms=int((time.time() - started) * 1000),
                usage=usage,
                mime_type=str(download_meta.get("mime_type", "")),
            )
        except Exception as exc:
            return ImageGenerationResult(
                asset_id=request.asset_id,
                status="failed",
                model=request.model,
                duration_ms=int((time.time() - started) * 1000),
                warning=_redacted_error(exc),
            )
```

- [ ] **Step 6: Run provider tests**

Run:

```bash
C:/Users/lcmzz/.conda/envs/gpt-researcher-main/python.exe -m pytest tests/test_ecommerce_image_provider.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add multi_agents/ecommerce/tools/image_generation tests/test_ecommerce_image_provider.py
git commit -m "feat(ecommerce): add jimeng image provider"
```

---

### Task 3: VisualConceptAgent Prompt Planning And Image Generation Orchestration

**Files:**
- Create: `multi_agents/ecommerce/agents/visual_concept.py`
- Test: `tests/test_ecommerce_visual_agent.py`

**Interfaces:**
- Consumes: `EcommerceResearchState`.
- Consumes: `ImageGenerationProvider.generate(ImageGenerationRequest)`.
- Produces: `run_visual_concept_agent(state, *, image_provider=None, visual_enabled=False, visual_model="doubao-seedream-4-5-251128", visual_size="2K", visual_watermark=False, image_count=6, output_dir=None, progress_callback=None) -> EcommerceResearchState`.
- Produces: `visual_result` with `visual_brief`, `prompts`, `assets`, `warnings`, `usage`.
- Produces: `agent_trace` record with node `visual`.

- [ ] **Step 1: Write visual agent tests**

Create `tests/test_ecommerce_visual_agent.py`:

```python
from pathlib import Path

import pytest

from multi_agents.ecommerce.agents.visual_concept import (
    build_visual_prompts,
    run_visual_concept_agent,
)
from multi_agents.ecommerce.state import create_initial_state
from multi_agents.ecommerce.tools.image_generation.base import (
    ImageGenerationRequest,
    ImageGenerationResult,
)


def fake_state():
    state = create_initial_state("portable blender")
    state["trend_result"] = {
        "summary": "Demand is growing among commuters and fitness users.",
        "trend_score": 7.1,
        "key_findings": ["portable blending demand is rising"],
    }
    state["competitor_result"] = {
        "summary": "Most competitors look similar and compete on price.",
        "gaps": ["easy-clean blade", "leak-proof cap"],
    }
    state["review_result"] = {
        "pain_points": ["cleaning is difficult", "battery life is short", "leaks in bags"],
        "pain_point_score": 7.6,
    }
    state["opportunity_score"] = {
        "overall_score": 6.8,
        "recommendation": "test with differentiated easy-clean design",
        "risks": ["battery safety claims"],
    }
    return state


def test_build_visual_prompts_selects_slots_by_count():
    state = fake_state()

    one = build_visual_prompts(state, image_count=1)
    three = build_visual_prompts(state, image_count=3)
    six = build_visual_prompts(state, image_count=6)

    assert [(row["kind"], row["slot"]) for row in one] == [("listing", "main_image")]
    assert [(row["kind"], row["slot"]) for row in three] == [
        ("product_concept", "appearance"),
        ("listing", "main_image"),
        ("listing", "lifestyle"),
    ]
    assert len(six) == 6
    assert six[0]["asset_id"] == "visual_product_01"
    assert six[-1]["asset_id"] == "visual_listing_03"
    assert "portable blender" in six[0]["prompt"].lower()
    assert "logo" in six[0]["negative_prompt"].lower()


class SuccessProvider:
    async def generate(self, request: ImageGenerationRequest):
        return ImageGenerationResult(
            asset_id=request.asset_id,
            status="success",
            remote_url=f"https://example.com/{request.asset_id}.jpg",
            local_path=f"/tmp/{request.asset_id}.jpg",
            width=2048,
            height=2048,
            model=request.model,
            duration_ms=10,
            usage={"generated_images": 1, "total_tokens": 100},
            mime_type="image/jpeg",
        )


class FailingProvider:
    async def generate(self, request: ImageGenerationRequest):
        return ImageGenerationResult(
            asset_id=request.asset_id,
            status="failed",
            model=request.model,
            duration_ms=5,
            warning="provider down",
        )


class ExplodingProvider:
    async def generate(self, request: ImageGenerationRequest):
        raise RuntimeError("ARK_API_KEY=secret-value provider down")


@pytest.mark.asyncio
async def test_run_visual_concept_agent_generates_assets_and_trace(tmp_path):
    state = fake_state()

    updated = await run_visual_concept_agent(
        state,
        image_provider=SuccessProvider(),
        visual_enabled=True,
        image_count=3,
        output_dir=tmp_path,
    )

    visual = updated["visual_result"]
    assert visual["enabled"] is True
    assert visual["status"] == "success"
    assert len(visual["prompts"]) == 3
    assert len(visual["assets"]) == 3
    assert visual["usage"]["generated_images"] == 3
    assert visual["usage"]["total_tokens"] == 300
    trace = updated["agent_trace"][-1]
    assert trace["node"] == "visual"
    assert trace["status"] == "success"
    assert trace["output_summary"]["generated_image_count"] == 3


@pytest.mark.asyncio
async def test_run_visual_concept_agent_emits_trace_event(tmp_path):
    state = fake_state()
    events = []

    async def progress(event, payload):
        events.append((event, payload))

    await run_visual_concept_agent(
        state,
        image_provider=SuccessProvider(),
        visual_enabled=True,
        image_count=1,
        output_dir=tmp_path,
        progress_callback=progress,
    )

    assert events[-1][0] == "trace_node_done"
    assert events[-1][1]["node"] == "visual"
    assert events[-1][1]["status"] == "success"


@pytest.mark.asyncio
async def test_run_visual_concept_agent_degrades_to_prompt_only_on_failure(tmp_path):
    state = fake_state()

    updated = await run_visual_concept_agent(
        state,
        image_provider=FailingProvider(),
        visual_enabled=True,
        image_count=1,
        output_dir=tmp_path,
    )

    visual = updated["visual_result"]
    assert visual["status"] == "failed"
    assert len(visual["prompts"]) == 1
    assert visual["assets"][0]["status"] == "failed"
    assert visual["assets"][0]["prompt"]
    assert visual["warnings"] == ["provider down"]


@pytest.mark.asyncio
async def test_run_visual_concept_agent_catches_provider_exception(tmp_path):
    state = fake_state()

    updated = await run_visual_concept_agent(
        state,
        image_provider=ExplodingProvider(),
        visual_enabled=True,
        image_count=1,
        output_dir=tmp_path,
    )

    visual = updated["visual_result"]
    assert visual["status"] == "failed"
    assert visual["assets"][0]["status"] == "failed"
    assert "secret-value" not in visual["assets"][0]["warning"]
    assert "ARK_API_KEY=[REDACTED]" in visual["assets"][0]["warning"]


@pytest.mark.asyncio
async def test_run_visual_concept_agent_skips_when_disabled(tmp_path):
    state = fake_state()

    updated = await run_visual_concept_agent(
        state,
        image_provider=SuccessProvider(),
        visual_enabled=False,
        image_count=3,
        output_dir=tmp_path,
    )

    assert updated["visual_result"]["status"] == "skipped"
    assert updated["visual_result"]["prompts"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
C:/Users/lcmzz/.conda/envs/gpt-researcher-main/python.exe -m pytest tests/test_ecommerce_visual_agent.py -q
```

Expected: FAIL because `visual_concept.py` does not exist.

- [ ] **Step 3: Implement visual prompt planning and agent**

Create `multi_agents/ecommerce/agents/visual_concept.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from collections.abc import Awaitable, Callable

from multi_agents.ecommerce.runtime.policy_guard import redact_secrets
from multi_agents.ecommerce.runtime.trace_recorder import (
    emit_trace,
    finish_trace_node,
    start_trace_node,
)
from multi_agents.ecommerce.state import EcommerceResearchState
from multi_agents.ecommerce.tools.image_generation.base import (
    ImageGenerationProvider,
    ImageGenerationRequest,
)
from multi_agents.ecommerce.tools.image_generation.volc_ark_jimeng import (
    VolcArkJimengProvider,
)

DEFAULT_VISUAL_MODEL = "doubao-seedream-4-5-251128"
ProgressFn = Callable[[str, dict], Awaitable[None]]

SLOTS = [
    ("product_concept", "appearance", "visual_product_01"),
    ("product_concept", "use_case", "visual_product_02"),
    ("product_concept", "detail", "visual_product_03"),
    ("listing", "main_image", "visual_listing_01"),
    ("listing", "infographic", "visual_listing_02"),
    ("listing", "lifestyle", "visual_listing_03"),
]


def _selected_slots(image_count: int) -> list[tuple[str, str, str]]:
    if image_count <= 1:
        return [("listing", "main_image", "visual_listing_01")]
    if image_count <= 3:
        return [
            ("product_concept", "appearance", "visual_product_01"),
            ("listing", "main_image", "visual_listing_01"),
            ("listing", "lifestyle", "visual_listing_03"),
        ]
    return SLOTS[:6]


def build_visual_brief(state: EcommerceResearchState) -> dict[str, Any]:
    query = state.get("query", "")
    review = state.get("review_result", {})
    competitor = state.get("competitor_result", {})
    score = state.get("opportunity_score", {})
    pain_points = review.get("pain_points", [])[:3]
    gaps = competitor.get("gaps", [])[:3]
    return {
        "product_positioning": f"{query} product concept for {state.get('target_market', 'US')} ecommerce buyers",
        "target_customer": "buyers matching the observed trend and review pain points",
        "design_direction": ", ".join([*gaps, *pain_points]) or score.get("recommendation", ""),
        "differentiation": gaps,
        "risk_notes": score.get("risks", []) or ["avoid brand logos", "avoid medical claims", "avoid exaggerated promises"],
    }


def _prompt_for_slot(
    *,
    state: EcommerceResearchState,
    kind: str,
    slot: str,
    brief: dict[str, Any],
) -> tuple[str, str, str, list[str]]:
    query = state.get("query", "")
    pain_points = state.get("review_result", {}).get("pain_points", [])[:3]
    gaps = state.get("competitor_result", {}).get("gaps", [])[:3]
    reason_parts = [*gaps, *pain_points]
    reason = " / ".join(str(item) for item in reason_parts if item) or "derived from ecommerce research evidence"
    source_refs = ["review_result.pain_points", "competitor_result.gaps"]
    negative = "brand logo, medical claims, exaggerated promises, watermark, distorted product, unreadable text"
    if kind == "listing" and slot == "main_image":
        prompt = (
            f"Amazon main image draft for {query}. Pure white background, single product centered, "
            f"premium clean ecommerce product photography, clear shape and material, no text, no logo. "
            f"Design direction: {brief.get('design_direction', '')}. Avoid medical claims."
        )
    elif kind == "listing" and slot == "infographic":
        prompt = (
            f"Amazon listing infographic concept for {query}. Show simple visual callouts for key benefits: "
            f"{brief.get('design_direction', '')}. Use clean layout, minimal readable text, realistic product render, "
            f"no brand logo, no exaggerated claims."
        )
    elif kind == "listing" and slot == "lifestyle":
        prompt = (
            f"Lifestyle ecommerce scene for {query}. Show the product used by the target customer in a realistic daily scenario, "
            f"natural light, premium but believable, emphasize convenience and differentiation: {brief.get('design_direction', '')}."
        )
    elif slot == "detail":
        prompt = (
            f"Detailed product concept render for {query}. Focus on differentiated functional details: "
            f"{brief.get('design_direction', '')}. Macro product photography, clean background, realistic materials."
        )
    elif slot == "use_case":
        prompt = (
            f"Product use case concept image for {query}. Show the product in context with a realistic customer scenario, "
            f"clean modern ecommerce style, emphasize pain point solutions: {brief.get('design_direction', '')}."
        )
    else:
        prompt = (
            f"High quality ecommerce product concept render for {query}. "
            f"Design direction: {brief.get('design_direction', '')}. "
            f"Premium realistic product photography, clean background, no logo, no watermark."
        )
    return prompt, negative, reason, source_refs


def build_visual_prompts(
    state: EcommerceResearchState,
    *,
    image_count: int,
) -> list[dict[str, Any]]:
    brief = build_visual_brief(state)
    prompts: list[dict[str, Any]] = []
    for kind, slot, asset_id in _selected_slots(max(1, min(6, int(image_count)))):
        prompt, negative, reason, source_refs = _prompt_for_slot(
            state=state,
            kind=kind,
            slot=slot,
            brief=brief,
        )
        prompts.append(
            {
                "asset_id": asset_id,
                "kind": kind,
                "slot": slot,
                "prompt": prompt,
                "negative_prompt": negative,
                "reason": reason,
                "source_refs": source_refs,
            }
        )
    return prompts


def _asset_from_result(prompt_row: dict[str, Any], result: Any) -> dict[str, Any]:
    return {
        **prompt_row,
        "status": result.status,
        "remote_url": result.remote_url,
        "local_path": result.local_path,
        "mime_type": result.mime_type,
        "width": result.width,
        "height": result.height,
        "model": result.model,
        "duration_ms": result.duration_ms,
        "usage": result.usage,
        "warning": result.warning,
    }


def _failed_asset_from_exception(
    prompt_row: dict[str, Any],
    exc: Exception,
    *,
    model: str,
) -> dict[str, Any]:
    redacted = redact_secrets({"error": str(exc)})
    return {
        **prompt_row,
        "status": "failed",
        "remote_url": "",
        "local_path": "",
        "mime_type": "",
        "width": 0,
        "height": 0,
        "model": model,
        "duration_ms": 0,
        "usage": {},
        "warning": str(redacted.get("error", "")),
    }


async def run_visual_concept_agent(
    state: EcommerceResearchState,
    *,
    image_provider: ImageGenerationProvider | None = None,
    visual_enabled: bool = False,
    visual_model: str = DEFAULT_VISUAL_MODEL,
    visual_size: str = "2K",
    visual_watermark: bool = False,
    image_count: int = 6,
    output_dir: str | Path | None = None,
    progress_callback: ProgressFn | None = None,
) -> EcommerceResearchState:
    trace_idx = start_trace_node(
        state,
        node="visual",
        agent="VisualConceptAgent",
        input_summary={
            "query": state.get("query", ""),
            "model": visual_model,
            "requested_image_count": image_count,
            "trend_score": state.get("trend_result", {}).get("trend_score"),
            "overall_score": state.get("opportunity_score", {}).get("overall_score"),
        },
    )
    if not visual_enabled:
        state["visual_result"] = {
            "enabled": False,
            "status": "skipped",
            "visual_brief": {},
            "prompts": [],
            "assets": [],
            "warnings": [],
            "usage": {},
        }
        record = finish_trace_node(state, trace_idx, status="skipped", output_summary={"prompt_count": 0})
        await emit_trace(progress_callback, record)
        return state

    brief = build_visual_brief(state)
    prompts = build_visual_prompts(state, image_count=image_count)
    visual_dir = Path(output_dir or ".")
    provider = image_provider or VolcArkJimengProvider(output_dir=visual_dir)
    assets: list[dict[str, Any]] = []
    warnings: list[str] = []
    usage = {"generated_images": 0, "total_tokens": 0, "failed_images": 0}
    for prompt_row in prompts:
        try:
            result = await provider.generate(
                ImageGenerationRequest(
                    asset_id=prompt_row["asset_id"],
                    prompt=prompt_row["prompt"],
                    model=visual_model,
                    size=visual_size,
                    watermark=visual_watermark,
                )
            )
            asset = _asset_from_result(prompt_row, result)
        except Exception as exc:
            asset = _failed_asset_from_exception(prompt_row, exc, model=visual_model)
        assets.append(asset)
        if asset["status"] == "success":
            asset_usage = asset.get("usage", {})
            usage["generated_images"] += int(asset_usage.get("generated_images", 0) or 0)
            usage["total_tokens"] += int(asset_usage.get("total_tokens", 0) or 0)
        else:
            usage["failed_images"] += 1
            if asset.get("warning"):
                warnings.append(str(asset["warning"]))

    success_count = sum(1 for row in assets if row.get("status") == "success")
    status = "success" if success_count == len(assets) else ("partial" if success_count else "failed")
    state["visual_result"] = {
        "enabled": True,
        "status": status,
        "model": visual_model,
        "provider": "volcengine_ark_jimeng",
        "visual_brief": brief,
        "prompts": prompts,
        "assets": assets,
        "warnings": warnings,
        "usage": usage,
    }
    record = finish_trace_node(
        state,
        trace_idx,
        status=status,
        output_summary={
            "prompt_count": len(prompts),
            "generated_image_count": success_count,
            "failed_image_count": usage["failed_images"],
            "total_tokens": usage["total_tokens"],
        },
        warnings=warnings,
    )
    await emit_trace(progress_callback, record)
    return state
```

- [ ] **Step 4: Run visual agent tests**

Run:

```bash
C:/Users/lcmzz/.conda/envs/gpt-researcher-main/python.exe -m pytest tests/test_ecommerce_visual_agent.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add multi_agents/ecommerce/agents/visual_concept.py tests/test_ecommerce_visual_agent.py
git commit -m "feat(ecommerce): add visual concept agent"
```

---

### Task 4: Runner, Persistence, Run Store, And Evaluation Integration

**Files:**
- Modify: `multi_agents/ecommerce/runner.py`
- Modify: `multi_agents/ecommerce/runtime/run_store.py`
- Test: `tests/test_ecommerce_runner_visual.py`
- Test: `tests/test_ecommerce_human_review.py`

**Interfaces:**
- Consumes: `run_visual_concept_agent(...)`.
- Extends: `run_ecommerce_research(..., visual_enabled=False, visual_model="doubao-seedream-4-5-251128", visual_image_count=6, image_provider=None)`.
- Produces: `outputs/ecommerce/<slug>-visual/visual-assets.json`.
- Produces: `output_paths["visual_assets"]` and `output_paths["visual_dir"]` when visual generation is enabled.
- Produces: `load_run(run_id)["visual_result"]`.

- [ ] **Step 1: Write runner visual tests**

Create `tests/test_ecommerce_runner_visual.py`:

```python
import json
from pathlib import Path

import pytest

from multi_agents.ecommerce.runner import run_ecommerce_research
from multi_agents.ecommerce.tools.image_generation.base import (
    ImageGenerationRequest,
    ImageGenerationResult,
)


async def fake_search(query: str, max_results: int):
    return [
        {
            "title": f"Source for {query}",
            "href": "https://example.com/source",
            "body": "Customers complain about cleaning and leakage. Demand is growing.",
        }
    ]


class FakeImageProvider:
    async def generate(self, request: ImageGenerationRequest):
        return ImageGenerationResult(
            asset_id=request.asset_id,
            status="success",
            remote_url=f"https://example.com/{request.asset_id}.jpg",
            local_path=f"/tmp/{request.asset_id}.jpg",
            width=2048,
            height=2048,
            model=request.model,
            duration_ms=1,
            usage={"generated_images": 1, "total_tokens": 100},
            mime_type="image/jpeg",
        )


@pytest.mark.asyncio
async def test_runner_writes_visual_artifacts_when_enabled(tmp_path):
    result = await run_ecommerce_research(
        query="portable blender",
        output_dir=tmp_path,
        search_fn=fake_search,
        visual_enabled=True,
        visual_image_count=3,
        image_provider=FakeImageProvider(),
    )

    assert result["visual_result"]["status"] == "success"
    assert result["evaluation_summary"]["visual_asset_count"] == 3
    # [FIX-3] assert filename + parent dir name, not a forward-slash suffix:
    # runner stores str(Path(...)) which uses backslashes on Windows, so an
    # endswith("portable-blender-visual/visual-assets.json") would fail there.
    visual_path = Path(result["output_paths"]["visual_assets"])
    assert visual_path.name == "visual-assets.json"
    assert visual_path.parent.name == "portable-blender-visual"
    assert visual_path.exists()
    visual_payload = json.loads(visual_path.read_text(encoding="utf-8"))
    assert len(visual_payload["assets"]) == 3
    assert any(row["node"] == "visual" for row in result["agent_trace"])
    run_meta = json.loads(Path(result["output_paths"]["run"]).read_text(encoding="utf-8"))
    assert run_meta["evaluation_summary"]["visual_asset_count"] == 3


@pytest.mark.asyncio
async def test_runner_keeps_visual_skipped_when_disabled(tmp_path):
    result = await run_ecommerce_research(
        query="portable blender",
        output_dir=tmp_path,
        search_fn=fake_search,
        visual_enabled=False,
    )

    assert result["visual_result"]["status"] == "skipped"
    assert "visual_assets" not in result["output_paths"]
```

- [ ] **Step 2: Extend human review run-store test**

Add this test to `tests/test_ecommerce_human_review.py` (`json` is already imported at the top of that file, so no new import is needed):

```python
def test_load_run_reads_visual_result(tmp_path):
    from multi_agents.ecommerce.runtime.run_store import load_run

    run_id = "ecom_20260623090000_portable-blender_abc123"
    visual_path = tmp_path / "portable-blender-visual" / "visual-assets.json"
    visual_path.parent.mkdir()
    visual_path.write_text(
        json.dumps({"status": "success", "assets": [{"asset_id": "visual_product_01"}]}),
        encoding="utf-8",
    )
    run_path = tmp_path / "portable-blender-run.json"
    run_path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "output_paths": {"visual_assets": str(visual_path)},
                "evaluation_summary": {},
            }
        ),
        encoding="utf-8",
    )

    loaded = load_run(run_id, output_dir=tmp_path)

    assert loaded["visual_result"]["status"] == "success"
    assert loaded["visual_result"]["assets"][0]["asset_id"] == "visual_product_01"
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
C:/Users/lcmzz/.conda/envs/gpt-researcher-main/python.exe -m pytest tests/test_ecommerce_runner_visual.py tests/test_ecommerce_human_review.py::test_load_run_reads_visual_result -q
```

Expected: FAIL because runner does not accept visual args and run store does not load visual artifacts.

- [ ] **Step 4: Modify runner signature and visual stage [FIX-1]**

In `multi_agents/ecommerce/runner.py`, import:

```python
from multi_agents.ecommerce.agents.visual_concept import (
    DEFAULT_VISUAL_MODEL,
    run_visual_concept_agent,
)
from multi_agents.ecommerce.tools.image_generation.base import ImageGenerationProvider
```

Extend `run_ecommerce_research()` signature (inside the existing keyword-only group, after `mcp_search_fn`):

```python
    visual_enabled: bool = False,
    visual_model: str = DEFAULT_VISUAL_MODEL,
    visual_image_count: int = 6,
    image_provider: ImageGenerationProvider | None = None,
```

**Anchor the visual stage to the real runner structure.** The existing runner (section ④ 落盘) already computes, in this order: `output_path = Path(output_dir)` + `output_path.mkdir(...)`; `slug = slugify(query)`; the `<slug>-report.md` / `<slug>-audit.json` / … path variables built from `output_path` and `slug`; the report/audit/quality writes; **then** `evaluation_summary = build_evaluation_summary(final_state)`.

Insert the visual stage **after the quality write and before `evaluation_summary = build_evaluation_summary(final_state)`**, **reusing the already-declared `output_path` and `slug`** — do **not** re-declare them and do **not** delete anything (deleting the existing declarations would break the `<slug>-*` path variables that use them):

```python
    # [FIX-1] visual stage: reuse existing output_path / slug (declared above in ④).
    # Runs BEFORE build_evaluation_summary so visual_result flows into the summary.
    visual_dir = output_path / f"{slug}-visual"
    if visual_enabled:
        final_state = await run_visual_concept_agent(
            final_state,
            image_provider=image_provider,
            visual_enabled=True,
            visual_model=visual_model,
            image_count=max(1, min(6, int(visual_image_count))),
            output_dir=visual_dir,
            progress_callback=progress_callback,
        )
    else:
        final_state.setdefault(
            "visual_result",
            {
                "enabled": False,
                "status": "skipped",
                "visual_brief": {},
                "prompts": [],
                "assets": [],
                "warnings": [],
                "usage": {},
            },
        )
```

When building `final_state["output_paths"]`, add the visual paths and write the artifact only when enabled (this block goes where `final_state["output_paths"] = {...}` is assembled, after the evaluation/trace/human-review writes):

```python
    if visual_enabled:
        visual_assets_path = visual_dir / "visual-assets.json"
        visual_dir.mkdir(parents=True, exist_ok=True)
        _write_json(visual_assets_path, final_state.get("visual_result", {}))
        final_state["output_paths"]["visual_assets"] = str(visual_assets_path)
        final_state["output_paths"]["visual_dir"] = str(visual_dir)
```

Add `visual_result` to `run_metadata`:

```python
        "visual_result": final_state.get("visual_result", {}),
```

- [ ] **Step 5: Modify run_store to load visual artifacts**

In `multi_agents/ecommerce/runtime/run_store.py`, add to the `load_run()` return dict:

```python
        "visual_result": _read_json_path(
            paths.get("visual_assets"),
            metadata.get("visual_result", {}),
        ),
```

- [ ] **Step 6: Run runner/run-store tests**

Run:

```bash
C:/Users/lcmzz/.conda/envs/gpt-researcher-main/python.exe -m pytest tests/test_ecommerce_runner_visual.py tests/test_ecommerce_human_review.py -q
```

Expected: PASS.

- [ ] **Step 7: Run existing runner regression**

Run:

```bash
C:/Users/lcmzz/.conda/envs/gpt-researcher-main/python.exe -m pytest tests/test_ecommerce_runner.py tests/test_ecommerce_evaluation.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add multi_agents/ecommerce/runner.py multi_agents/ecommerce/runtime/run_store.py tests/test_ecommerce_runner_visual.py tests/test_ecommerce_human_review.py
git commit -m "feat(ecommerce): persist visual artifacts"
```

---

### Task 5: API And WebSocket Visual Controls

**Files:**
- Modify: `backend/server/ecommerce_api.py`
- Test: `tests/test_ecommerce_api.py`

**Interfaces:**
- Extends: `EcommerceRequest` with `visual_enabled`, `visual_model`, `visual_image_count`.
- Extends: POST `/api/ecommerce/research` passthrough.
- Extends: WS `/ws/ecommerce` passthrough.
- Extends: `_summarize(result)` with `visual_result` and `visual_assets`.

- [ ] **Step 1: Add failing API tests**

Add this test to `tests/test_ecommerce_api.py`:

```python
def test_ecommerce_research_passes_visual_fields(monkeypatch):
    received_kwargs = {}

    async def fake_run(**kwargs):
        received_kwargs.update(kwargs)
        return {
            "run_id": "ecom_20260623090000_portable-blender_abc123",
            "query": kwargs["query"],
            "target_market": kwargs["target_market"],
            "trend_result": {},
            "competitor_result": {},
            "review_result": {},
            "opportunity_score": {},
            "quality_check": {},
            "audit_log": [],
            "agent_trace": [],
            "evaluation_summary": {},
            "human_review": {"review_status": "pending"},
            "eval_result": {},
            "mcp_context": {},
            "visual_result": {"status": "success", "assets": [{"asset_id": "visual_product_01"}]},
            "final_report": "# Report",
            "output_paths": {"visual_assets": "visual-assets.json"},
        }

    monkeypatch.setattr(ecommerce_api, "run_ecommerce_research", fake_run)

    response = _client().post(
        "/api/ecommerce/research",
        json={
            "query": "portable blender",
            "visual_enabled": True,
            "visual_model": "doubao-seedream-4-5-251128",
            "visual_image_count": 3,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert received_kwargs["visual_enabled"] is True
    assert received_kwargs["visual_model"] == "doubao-seedream-4-5-251128"
    assert received_kwargs["visual_image_count"] == 3
    assert data["visual_result"]["status"] == "success"
    assert data["visual_assets"][0]["asset_id"] == "visual_product_01"
```

Extend `test_ecommerce_websocket_passes_mcp_fields` or add a separate test:

```python
def test_ecommerce_websocket_passes_visual_fields(monkeypatch):
    received_kwargs = {}

    async def fake_run(**kwargs):
        received_kwargs.update(kwargs)
        return {
            "run_id": "ecom_20260623090000_portable-blender_abc123",
            "query": kwargs["query"],
            "target_market": kwargs["target_market"],
            "trend_result": {},
            "competitor_result": {},
            "review_result": {},
            "opportunity_score": {},
            "quality_check": {},
            "audit_log": [],
            "agent_trace": [],
            "evaluation_summary": {},
            "human_review": {"review_status": "pending"},
            "eval_result": {},
            "mcp_context": {},
            "visual_result": {"status": "skipped", "assets": []},
            "final_report": "# Report",
            "output_paths": {},
        }

    monkeypatch.setattr(ecommerce_api, "run_ecommerce_research", fake_run)

    with _client().websocket_connect("/ws/ecommerce") as websocket:
        websocket.send_json(
            {
                "query": "portable blender",
                "visual_enabled": True,
                "visual_model": "doubao-seedream-4-5-251128",
                "visual_image_count": 1,
            }
        )
        message = websocket.receive_json()

    assert message["event"] == "done"
    assert received_kwargs["visual_enabled"] is True
    assert received_kwargs["visual_model"] == "doubao-seedream-4-5-251128"
    assert received_kwargs["visual_image_count"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
C:/Users/lcmzz/.conda/envs/gpt-researcher-main/python.exe -m pytest tests/test_ecommerce_api.py::test_ecommerce_research_passes_visual_fields tests/test_ecommerce_api.py::test_ecommerce_websocket_passes_visual_fields -q
```

Expected: FAIL because API schema and passthrough do not include visual fields.

- [ ] **Step 3: Modify EcommerceRequest and _summarize**

In `backend/server/ecommerce_api.py`, add to `EcommerceRequest`:

```python
    visual_enabled: bool = False
    visual_model: str = "doubao-seedream-4-5-251128"
    visual_image_count: int = 6
```

Add to `_summarize()`:

```python
        "visual_result": result.get("visual_result", {}),
        "visual_assets": result.get("visual_result", {}).get("assets", []),
```

- [ ] **Step 4: Pass visual fields in POST and WebSocket**

In `ecommerce_research()`, add:

```python
        visual_enabled=req.visual_enabled,
        visual_model=req.visual_model,
        visual_image_count=req.visual_image_count,
```

In `ecommerce_websocket()`, add:

```python
            visual_enabled=bool(data.get("visual_enabled", False)),
            visual_model=data.get("visual_model", "doubao-seedream-4-5-251128"),
            visual_image_count=int(data.get("visual_image_count", 6)),
```

- [ ] **Step 5: Run API tests**

Run:

```bash
C:/Users/lcmzz/.conda/envs/gpt-researcher-main/python.exe -m pytest tests/test_ecommerce_api.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/server/ecommerce_api.py tests/test_ecommerce_api.py
git commit -m "feat(ecommerce): expose visual generation api"
```

---

### Task 6: Static Frontend Visual Panels And Review Controls

**Files:**
- Modify: `frontend/ecommerce.html`
- Modify: `frontend/ecommerce-review.html`
- Modify: `frontend/ecommerce-eval.html`
- Test: `tests/test_ecommerce_frontend_visual.py`

**Interfaces:**
- Consumes API response fields `visual_result`, `visual_assets`, `evaluation_summary.visual_*`.
- Produces request JSON fields `visual_enabled`, `visual_model`, `visual_image_count`.
- Produces human review payload field `visual_reviews`.

> **[FIX-2] Scope note for `ecommerce.html`:** the existing `escWarn` in that file is a **local** `const` defined inside `renderTraceRow` — it is NOT visible to any other function. The new `renderVisualResult` must define its **own** local `esc` (shown below); do not reference the `escWarn` from `renderTraceRow`. (`ecommerce-review.html` has a **global** `esc`, so its renderer is unaffected.)

- [ ] **Step 1: Add static frontend tests**

Create `tests/test_ecommerce_frontend_visual.py`:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_ecommerce_page_contains_visual_controls_and_panel():
    html = (ROOT / "frontend" / "ecommerce.html").read_text(encoding="utf-8")

    assert 'id="visualEnabled"' in html
    assert 'id="visualImageCount"' in html
    assert 'id="visualCard"' in html
    assert "renderVisualResult" in html
    assert "visual_enabled" in html
    assert "visual_image_count" in html


def test_review_page_contains_visual_review_controls():
    html = (ROOT / "frontend" / "ecommerce-review.html").read_text(encoding="utf-8")

    assert 'id="visualReviewBody"' in html
    assert "visual_reviews" in html
    assert "approved" in html
    assert "needs_edit" in html


def test_eval_page_contains_visual_metrics():
    html = (ROOT / "frontend" / "ecommerce-eval.html").read_text(encoding="utf-8")

    assert "visual_asset_count" in html
    assert "visual_failed_asset_count" in html
    assert "visual_status" in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
C:/Users/lcmzz/.conda/envs/gpt-researcher-main/python.exe -m pytest tests/test_ecommerce_frontend_visual.py -q
```

Expected: FAIL because frontend files do not expose visual controls yet.

- [ ] **Step 3: Modify ecommerce.html controls**

In `frontend/ecommerce.html`, add visual controls in the existing `.checks` area:

```html
<label style="margin:0; display:flex; align-items:center; gap:6px;">
  <input type="checkbox" id="visualEnabled" style="width:auto;" /> 生成视觉概念图
</label>
<label style="margin:0; display:flex; align-items:center; gap:6px;">
  图片数量
  <select id="visualImageCount" style="width:auto; padding:6px 8px;">
    <option value="1">1</option>
    <option value="3">3</option>
    <option value="6" selected>6</option>
  </select>
</label>
<span class="pill">模型 doubao-seedream-4-5-251128</span>
```

Add visual styles:

```css
  .visual-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:14px; margin-top:12px; }
  .visual-item { background:#0b1220; border:1px solid var(--border); border-radius:8px; overflow:hidden; }
  .visual-item img { width:100%; display:block; aspect-ratio:1/1; object-fit:cover; background:#020617; }
  .visual-meta { padding:10px; font-size:12px; color:var(--mut); }
  .visual-meta details { margin-top:8px; }
```

Add this card after the result grid:

```html
<div class="card hidden" id="visualCard">
  <strong>Visual Concepts</strong>
  <span class="pill" id="visualStatus">-</span>
  <div class="visual-grid" id="visualGrid"></div>
</div>
```

When sending WebSocket JSON, add:

```javascript
      visual_enabled: $("visualEnabled").checked,
      visual_model: "doubao-seedream-4-5-251128",
      visual_image_count: Number($("visualImageCount").value)
```

Add render function — **note the local `esc` definition (FIX-2); do not call `escWarn` here, it is scoped to `renderTraceRow` and would throw `ReferenceError`**:

```javascript
function renderVisualResult(visual){
  // [FIX-2] local esc — ecommerce.html's escWarn lives inside renderTraceRow and is not in scope here.
  const esc = (s)=>(s==null?"":String(s)).replace(/[&<>"]/g, c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
  if(!visual || !visual.status || visual.status === "skipped") return;
  $("visualCard").classList.remove("hidden");
  $("visualStatus").textContent = visual.status;
  const assets = visual.assets || [];
  const prompts = visual.prompts || [];
  const rows = assets.length ? assets : prompts.map(p => ({...p, status:"prompt_only"}));
  $("visualGrid").innerHTML = rows.map(row => {
    const imageUrl = row.remote_url || row.local_path || "";
    const image = imageUrl ? `<img src="${esc(imageUrl)}" alt="${esc(row.asset_id || "visual asset")}" />` : "";
    return `
      <div class="visual-item">
        ${image}
        <div class="visual-meta">
          <div><span class="pill">${esc(row.kind || "-")}</span> <span class="pill">${esc(row.slot || "-")}</span></div>
          <div>Status: ${esc(row.status || "-")}</div>
          <div>${esc(row.reason || "")}</div>
          <details><summary>Prompt</summary><div>${esc(row.prompt || "")}</div></details>
          ${row.warning ? `<div class="warn">${esc(row.warning)}</div>` : ""}
        </div>
      </div>`;
  }).join("");
}
```

Call it inside `event === "done"`:

```javascript
      renderVisualResult(data.visual_result || {});
```

- [ ] **Step 4: Modify ecommerce-review.html**

Add visual review section inside `#reviewCard`:

```html
<h2>Visual Asset Review</h2>
<table>
  <thead><tr><th>Asset</th><th>Status</th><th>Tags</th><th>Reason</th></tr></thead>
  <tbody id="visualReviewBody"></tbody>
</table>
```

Add renderer (`esc` is already global on this page):

```javascript
function renderVisualReviews(run){
  const assets = ((run.visual_result || {}).assets || []);
  $("visualReviewBody").innerHTML = assets.map(asset => `
    <tr data-asset-id="${esc(asset.asset_id || "")}">
      <td>${esc(asset.asset_id || "-")}<br><span class="pill">${esc(asset.kind || "-")}/${esc(asset.slot || "-")}</span></td>
      <td>
        <select class="visualStatus">
          <option value="approved">approved</option>
          <option value="rejected">rejected</option>
          <option value="needs_edit">needs_edit</option>
        </select>
      </td>
      <td><input class="visualTags" placeholder="good_differentiation,text_artifact" /></td>
      <td><input class="visualReason" aria-label="Visual review reason" /></td>
    </tr>
  `).join("");
}
```

Call it in the load handler:

```javascript
  renderVisualReviews(currentRun);
```

Add visual reviews to `collectReview()` return:

```javascript
    visual_reviews: Array.from(document.querySelectorAll("#visualReviewBody tr")).map(row => ({
      asset_id: row.dataset.assetId,
      status: row.querySelector(".visualStatus").value,
      tags: row.querySelector(".visualTags").value.split(",").map(x => x.trim()).filter(Boolean),
      reason: row.querySelector(".visualReason").value.trim(),
    })),
```

- [ ] **Step 5: Modify ecommerce-eval.html**

Find the case summary rendering and add visual metrics where row summary fields are displayed:

```javascript
visual_status: row.summary && row.summary.visual_status,
visual_asset_count: row.summary && row.summary.visual_asset_count,
visual_failed_asset_count: row.summary && row.summary.visual_failed_asset_count,
```

Add visible labels containing these exact field names or rendered captions:

```html
<span class="pill">visual_status</span>
<span class="pill">visual_asset_count</span>
<span class="pill">visual_failed_asset_count</span>
```

If `ecommerce-eval.html` builds cards entirely in JavaScript, add the labels inside that template string instead of static HTML.

- [ ] **Step 6: Run frontend tests**

Run:

```bash
C:/Users/lcmzz/.conda/envs/gpt-researcher-main/python.exe -m pytest tests/test_ecommerce_frontend_visual.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/ecommerce.html frontend/ecommerce-review.html frontend/ecommerce-eval.html tests/test_ecommerce_frontend_visual.py
git commit -m "feat(ecommerce): show visual assets in frontend"
```

---

### Task 7: Manual Smoke Script And Final Regression

**Files:**
- Create: `scripts/smoke_jimeng_image_generation.py`
- Modify: `docs/superpowers/specs/2026-06-23-ecommerce-visual-concept-agent-design.md` only if implementation intentionally diverged from spec.

**Interfaces:**
- Consumes: `ARK_API_KEY` or `VOLCENGINE_ARK_API_KEY`.
- Consumes: `VolcArkJimengProvider`.
- Produces: one image in `outputs/ecommerce/smoke-jimeng/`.

- [ ] **Step 1: Create smoke script**

Create `scripts/smoke_jimeng_image_generation.py`:

```python
from __future__ import annotations

import asyncio
from pathlib import Path

from multi_agents.ecommerce.tools.image_generation.base import ImageGenerationRequest
from multi_agents.ecommerce.tools.image_generation.volc_ark_jimeng import (
    VolcArkJimengProvider,
)


async def main() -> None:
    output_dir = Path("outputs/ecommerce/smoke-jimeng")
    provider = VolcArkJimengProvider(output_dir=output_dir)
    result = await provider.generate(
        ImageGenerationRequest(
            asset_id="smoke_portable_blender",
            prompt=(
                "Minimal ecommerce product concept render of a portable blender on a pure white background, "
                "transparent cup, soft natural light, premium clean Amazon main image style, no logo, no text."
            ),
            model="doubao-seedream-4-5-251128",
            size="2K",
            watermark=False,
        )
    )
    print(
        {
            "status": result.status,
            "local_path": result.local_path,
            "remote_url": result.remote_url,
            "width": result.width,
            "height": result.height,
            "warning": result.warning,
            "usage": result.usage,
        }
    )


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Compile smoke script**

Run:

```bash
C:/Users/lcmzz/.conda/envs/gpt-researcher-main/python.exe -m py_compile scripts/smoke_jimeng_image_generation.py
```

Expected: PASS.

- [ ] **Step 3: Run full ecommerce regression**

Run:

```bash
C:/Users/lcmzz/.conda/envs/gpt-researcher-main/python.exe -m pytest tests/test_ecommerce_trace.py tests/test_ecommerce_graph_langgraph.py tests/test_ecommerce_runner.py tests/test_ecommerce_runner_visual.py tests/test_ecommerce_api.py tests/test_ecommerce_eval_runner.py tests/test_ecommerce_mcp_adapter.py tests/test_ecommerce_human_review.py tests/test_ecommerce_demo_export.py tests/test_ecommerce_evaluation.py tests/test_ecommerce_image_provider.py tests/test_ecommerce_visual_agent.py tests/test_ecommerce_frontend_visual.py -q
```

Expected: PASS.

- [ ] **Step 4: Run whitespace check**

Run:

```bash
git diff --check
```

Expected: no whitespace errors.

- [ ] **Step 5: Optional real API smoke**

Only run this manually when a valid key is set in the shell:

```powershell
$env:ARK_API_KEY="<your-rotated-key>"
& "C:\Users\lcmzz\.conda\envs\gpt-researcher-main\python.exe" scripts/smoke_jimeng_image_generation.py
```

Expected output contains:

```text
'status': 'success'
```

and `outputs/ecommerce/smoke-jimeng/` contains a downloaded image.

> **SDK-surface reminder:** the unit tests in Task 2 assert against a *guessed* Ark SDK shape (`client.images.generate(model, prompt, size, response_format, watermark, output_format)`, `response.data[0].url/size`, `usage.generated_images/output_tokens/total_tokens`). Only this manual smoke exercises the real SDK. If it fails opaquely, first re-check the method/parameter names against the current Volcengine Ark image-generation SDK docs before debugging the provider logic.

- [ ] **Step 6: Commit**

```bash
git add scripts/smoke_jimeng_image_generation.py
git commit -m "chore(ecommerce): add jimeng smoke script"
```

---

## Self-Review Checklist

- Spec coverage:
  - Provider abstraction and default model: Task 2.
  - VisualConceptAgent prompt generation: Task 3.
  - Runner artifacts and local persistence: Task 4.
  - Trace and evaluation integration: Tasks 1, 3, 4.
  - API and WebSocket passthrough: Task 5.
  - Frontend display and human review: Task 6.
  - Manual real-API smoke path: Task 7.
- Type consistency:
  - `visual_image_count` is API/runner input.
  - `image_count` is internal visual agent input.
  - `ImageGenerationRequest.asset_id` maps to `ImageGenerationResult.asset_id`.
  - `visual_result.assets` is the canonical frontend/API asset list.
- Safety:
  - No test calls the real Volcengine API by default.
  - No code stores API keys.
  - All Seedream models send `output_format="png"` ([FIX-9]).

---

## Revision Notes (v2 → v1)

v2 folds in five review findings. v1 is preserved unchanged. No other task scope changed.

- **FIX-1 (Task 4 Step 4) — runner insertion re-anchored to the real `runner.py`.** v1 said to declare `output_path`/`slug` fresh before `evaluation_summary` and "remove the later duplicate." The real runner declares them *before* the `<slug>-*` path variables (which depend on them) and *before* `evaluation_summary`; there is no later duplicate, and removing the existing declarations would `NameError` the path variables. v2 instead inserts the visual stage after the quality write / before `evaluation_summary`, **reusing** the existing `output_path`/`slug`, with explicit do-not-redeclare / do-not-delete guidance.

- **FIX-2 (Task 6 Step 3) — `escWarn` is not global in `ecommerce.html`.** v1's `renderVisualResult` called `escWarn(...)`, but `escWarn` is a `const` local to `renderTraceRow`; the new function would throw `ReferenceError` at runtime (a real break masked by the string-presence test, which still passes). v2 gives `renderVisualResult` its own local `esc`. `ecommerce-review.html` already has a global `esc`, so its renderer is unchanged.

- **FIX-3 (Task 4 Step 1) — Windows path separator in the runner test.** v1 asserted `result["output_paths"]["visual_assets"].endswith("portable-blender-visual/visual-assets.json")` (forward slash), but the runner stores `str(Path(...))` which is backslashes on Windows — the assertion fails on the actual Windows test env. (Existing tests only assert the filename component.) v2 asserts `Path(...).name == "visual-assets.json"` and `.parent.name == "portable-blender-visual"`.

- **FIX-4 (Task 2 Step 1) — Pillow pre-flight.** `volc_ark_jimeng.py` imports `from PIL import Image` at module top; a missing Pillow breaks collection of the provider, the visual agent, and the runner. Pillow is not in `requirements.txt` today. v2 adds an explicit pre-flight (`C:/Users/lcmzz/.conda/envs/gpt-researcher-main/python.exe -c "import PIL"`) with a `pip install` fallback before any Task 2 code is written.

- **FIX-5 (all "Run:" steps + Global Constraints) — `py` → the project conda-env interpreter.** Every `py -m pytest` / `py -m py_compile` / `py scripts/...` in v1 resolves to a C-drive Python 3.13 missing `mistune`/`langchain_community` and fails at collection. v2 points all Run steps at `C:/Users/lcmzz/.conda/envs/gpt-researcher-main/python.exe` (verified: imports `mistune`/`langchain_community`/`PIL`/`volcenginesdkarkruntime`) and records the constraint globally. *(Post-review P1 correction: an earlier draft used the conda-base `/d/conda/python.exe`, which both lacks `langchain_community` and is not a valid command in the user's PowerShell — corrected to the project env path.)*
- **FIX-7 (Task 7 Step 5) — smoke env var is PowerShell-native.** The draft wrote `set ARK_API_KEY=…` (cmd syntax), which is a silent no-op in PowerShell. v2 uses `$env:ARK_API_KEY="…"` and invokes the interpreter with the PowerShell call operator (`& "C:\Users\lcmzz\.conda\envs\gpt-researcher-main\python.exe" …`). The key is read from the env var only — never hardcoded into source or artifacts.
- **FIX-8 (Task 2 Step 5 + tests) — provider `_client()` moved inside `try`.** The draft called `client = self._client()` before the try, so an SDK import error or `Ark()` init failure escaped `generate()` as a raised exception — breaking the provider's "always return `ImageGenerationResult`" contract and crashing the smoke script instead of printing `status=failed`. v2 wraps `_client()` (and the missing-key short-circuit) in the try; a new test `test_provider_returns_failed_when_client_init_raises` pins it.
- **FIX-9 (Task 2 + Global Constraints + Self-Review) — `output_format` aligned to the official Ark SDK example.** The spec claimed `doubao-seedream-4-5-251128` does not support `output_format`, so the draft gated it behind `_supports_output_format(model)` (only true for `doubao-seedream-5-`) and a test asserted 4-5 omits it. The official example sends `output_format="png"` with `doubao-seedream-4-5-251128`, so v2 now sends `output_format="png"` for every Seedream model, removes the `_supports_output_format` branch, and flips the 4-5 test to assert `output_format == "png"`.

Non-blocking notes carried over (no plan change needed, flagged for execution): the Ark SDK call shape (`client.images.generate(...)` + `response.data[0].url`, including `output_format="png"` per FIX-9) now matches the official example — only the Task 7 manual smoke exercises the real endpoint; `visual_result` is also added to `EcommerceGraphState` (harmless, slightly beyond spec since the visual node runs post-graph); the `volcengine-python-sdk[ark]>=5.0.35` floor is an unverified pin that only affects the real smoke.
