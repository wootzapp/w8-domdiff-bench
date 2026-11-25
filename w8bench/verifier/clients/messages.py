"""Message and result types for verifier clients."""

import io
import base64
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

ToolSchema = Dict[str, Any]
Tool = ToolSchema


@dataclass
class LLMMessage:
    content: "str | List[Dict[str, Any]]"
    source: str = "user"
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class SystemMessage(LLMMessage):
    source: str = "system"


@dataclass
class UserMessage(LLMMessage):
    source: str = "user"


@dataclass
class AssistantMessage(LLMMessage):
    source: str = "assistant"


@dataclass
class ImageObj:
    """Screenshot image encoding and resizing."""

    image: Image.Image

    @classmethod
    def from_pil(cls, image: Image.Image) -> "ImageObj":
        return cls(image=image)

    @classmethod
    def from_base64(cls, b64: str) -> "ImageObj":
        return cls(image=Image.open(io.BytesIO(base64.b64decode(b64))))

    def to_base64(self) -> str:
        buffered = io.BytesIO()
        self.image.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode("utf-8")

    def resize(self, size: Tuple[int, int]) -> Image.Image:
        return self.image.resize(size)


@dataclass
class RequestUsage:
    """Token usage statistics for a single model call."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    num_calls: int = 1

    def __add__(self, other: "RequestUsage") -> "RequestUsage":
        return RequestUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            reasoning_tokens=self.reasoning_tokens + other.reasoning_tokens,
            num_calls=self.num_calls + other.num_calls,
        )

    def get_cost(self, prompt_price: float, completion_price: float) -> float:
        return (self.prompt_tokens * prompt_price) + (
            self.completion_tokens * completion_price
        )




@dataclass
class CreateResult:
    """Completion text, usage and the provider message."""

    content: Any
    usage: RequestUsage = field(default_factory=RequestUsage)
    finish_reason: Optional[str] = None
    cached: bool = False
    message: Any = None
    tool_calls: Optional[List[Any]] = None




def message_to_gemini_format(message: LLMMessage, *, evidence_mode="screenshot_verifier") -> Dict[str, Any]:
    """Convert a verifier message to native content parts."""
    if isinstance(message, dict):
        role = message.get("role", "user")
        content = message.get("content", message.get("parts", ""))
    else:
        role = "system" if isinstance(message, SystemMessage) else "model" if isinstance(message, AssistantMessage) else "user"
        content = message.content
    parts = []
    for item in content if isinstance(content, list) else [content]:
        if isinstance(item, str):
            parts.append({"text": item})
        elif evidence_mode == "screenshot_verifier" and isinstance(item, (ImageObj, Image.Image)):
            image = item if isinstance(item, ImageObj) else ImageObj.from_pil(item)
            parts.append({"inline_data": {"mime_type": "image/png", "data": base64.b64decode(image.to_base64())}})
        elif isinstance(item, dict):
            if item.get("type") == "text":
                parts.append({"text": item["text"]})
            elif item.get("type") == "image_url" and evidence_mode == "screenshot_verifier":
                url = item["image_url"]["url"]
                header, data = url.split(",", 1)
                parts.append({"inline_data": {"mime_type": header.split(":", 1)[1].split(";", 1)[0], "data": base64.b64decode(data)}})
            elif "text" in item or "inline_data" in item or "inlineData" in item:
                parts.append(item)
    return {"role": "model" if role == "assistant" else role, "parts": parts}
