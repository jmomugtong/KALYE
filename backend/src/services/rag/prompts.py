"""Prompt templates for the RAG pipeline."""

from __future__ import annotations

from typing import List

SYSTEM_PROMPT = (
    "You are KALYE AI, an urban planning assistant specializing in "
    "pedestrian walkability analysis for Metro Manila. You provide factual, "
    "data-driven answers about street infrastructure issues such as potholes, "
    "sidewalk obstructions, missing ramps, and accessibility hazards. "
    "Always cite specific detections when available. "
    "If the data is insufficient, state so clearly rather than speculating."
)

QUERY_TEMPLATE = """{system}

### Context
The following infrastructure detections were retrieved from the KALYE database:

{context}

### Question
{query}

### Instructions
Answer the question using ONLY the context above. Reference specific detections by their type, location, and confidence where relevant. If the context does not contain enough information, say so.

### Answer
"""


def build_context(detections: List[dict]) -> str:
    """Format a list of detection dicts into a numbered context block."""
    if not detections:
        return "No relevant detections found in the database."

    lines: list[str] = []
    for i, det in enumerate(detections, 1):
        det_type = det.get("detection_type", "unknown")
        confidence = det.get("confidence_score", 0.0)
        caption = det.get("caption", "No caption")
        lat = det.get("lat", "N/A")
        lon = det.get("lon", "N/A")
        created = det.get("created_at", "N/A")
        distance = det.get("distance")

        line = (
            f"[{i}] Type: {det_type} | Confidence: {confidence:.0%} | "
            f"Location: ({lat}, {lon}) | Date: {created}"
        )
        if caption:
            line += f"\n     Caption: {caption}"
        if distance is not None:
            line += f"\n     Relevance distance: {distance:.4f}"
        lines.append(line)

    return "\n\n".join(lines)
