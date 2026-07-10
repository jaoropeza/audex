from __future__ import annotations

from abc import ABC, abstractmethod


class SummarizationPort(ABC):
    @abstractmethod
    def summarize(self, transcript_path: str) -> None:
        """Read transcript_path, generate summary, write _summary.txt beside it."""
