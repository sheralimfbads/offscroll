"""Deterministic source context; no LLM account, requests, or factual assertions."""

import hashlib
import json
from dataclasses import dataclass
from typing import Protocol

from offscroll.ranking import Candidate


@dataclass(frozen=True)
class Summary:
    text: str
    model: str
    prompt_version: str
    input_hash: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_estimate: float = 0.0


class Summarizer(Protocol):
    def summarize(self, item: Candidate) -> Summary: ...


class TemplateSummarizer:
    """Label this as source context, never as an AI-generated summary."""

    def summarize(self, item: Candidate) -> Summary:
        # A title is hashed as data, never executed or interpreted as instructions.
        payload = json.dumps(
            {
                "source": item.source,
                "title": item.title,
                "domain": item.domain,
                "model": "template",
                "prompt_version": "source-context-v1",
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        text = (
            "Follow the original story and Hacker News discussion for context."
            if item.source == "hackernews"
            else "Open the Wikipedia article for background and its cited sources."
        )
        return Summary(
            text, "template", "source-context-v1", hashlib.sha256(payload.encode()).hexdigest()
        )
