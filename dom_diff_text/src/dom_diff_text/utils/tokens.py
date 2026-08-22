"""Token estimation extracted from the benchmarked compaction utilities."""

from __future__ import annotations


class TokenEstimator:
    """Local token estimator with an explicit conservative fallback."""

    def __init__(self, model: str = "gpt-5.2") -> None:
        self.model = model
        self._encoding = None
        self.name = "conservative-char-divisor-3"
        try:
            import tiktoken

            try:
                self._encoding = tiktoken.encoding_for_model(model)
            except KeyError:
                self._encoding = tiktoken.get_encoding("o200k_base")
            self.name = getattr(self._encoding, "name", "tiktoken")
        except (ImportError, OSError, ValueError):
            self._encoding = None

    def count(self, text: str) -> int:
        if self._encoding is not None:
            return len(self._encoding.encode(text))
        return max(1, (len(text) + 2) // 3)
