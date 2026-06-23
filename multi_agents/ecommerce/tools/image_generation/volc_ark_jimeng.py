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
OUTPUT_FORMAT_MODELS = {"doubao-seedream-5-0-260128"}


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


def _supports_output_format(model: str) -> bool:
    return model in OUTPUT_FORMAT_MODELS


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
            kwargs: dict[str, Any] = {
                "model": request.model,
                "prompt": request.prompt,
                "size": request.size,
                "response_format": "url",
                "watermark": request.watermark,
            }
            if _supports_output_format(request.model):
                kwargs["output_format"] = "png"
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
