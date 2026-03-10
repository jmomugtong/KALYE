"""Post-processing utilities for cleaning and formatting raw model captions."""

from __future__ import annotations

import re
from typing import List


class CaptionFormatter:
    """Cleans and normalises raw captions produced by vision-language models.

    The ``format_caption`` method orchestrates the full pipeline:
    artifact removal, capitalisation, and punctuation.
    """

    # Patterns that commonly appear in raw transformer output.
    _ARTIFACT_PATTERNS: List[re.Pattern[str]] = [
        re.compile(r"<unk>", re.IGNORECASE),
        re.compile(r"\[UNK\]", re.IGNORECASE),
        re.compile(r"<pad>", re.IGNORECASE),
        re.compile(r"\[PAD\]", re.IGNORECASE),
        re.compile(r"<s>", re.IGNORECASE),
        re.compile(r"</s>", re.IGNORECASE),
    ]

    # ------------------------------------------------------------------
    # Individual transformations
    # ------------------------------------------------------------------

    @staticmethod
    def remove_artifacts(caption: str) -> str:
        """Remove common model output artifacts and repeated phrases.

        Strips ``<unk>``, ``[UNK]``, padding tokens, and collapses
        consecutive duplicate phrases.
        """
        for pattern in CaptionFormatter._ARTIFACT_PATTERNS:
            caption = pattern.sub("", caption)

        # Collapse repeated consecutive phrases (greedy, 2-6 word spans).
        # E.g. "a man walking a man walking" -> "a man walking"
        caption = re.sub(
            r"\b((?:\S+\s+){1,5}\S+)\s+\1\b",
            r"\1",
            caption,
        )

        # Collapse multiple spaces left over from artifact removal.
        caption = re.sub(r"\s{2,}", " ", caption).strip()
        return caption

    @staticmethod
    def capitalize_properly(caption: str) -> str:
        """Ensure the first character of the caption is uppercase."""
        if not caption:
            return caption
        return caption[0].upper() + caption[1:]

    @staticmethod
    def add_period_if_missing(caption: str) -> str:
        """Append a period if the caption does not end with sentence punctuation."""
        if not caption:
            return caption
        if caption[-1] not in (".", "!", "?"):
            caption += "."
        return caption

    # ------------------------------------------------------------------
    # Full pipeline
    # ------------------------------------------------------------------

    def format_caption(self, caption: str) -> str:
        """Run the complete formatting pipeline on a raw caption.

        Steps:
            1. Remove model artifacts and repeated phrases.
            2. Capitalise the first letter.
            3. Ensure trailing punctuation.
        """
        caption = self.remove_artifacts(caption)
        caption = self.capitalize_properly(caption)
        caption = self.add_period_if_missing(caption)
        return caption
