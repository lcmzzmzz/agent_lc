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
