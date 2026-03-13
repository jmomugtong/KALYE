"""Claude Vision API — street walkability analysis.

Sends an uploaded street image to Claude claude-haiku-4-5 (fast + affordable)
and gets back structured walkability issue detections + a natural-language caption.

Replaces the heavy local CPU pipeline (YOLOv8 + SegFormer + BLIP) with a single
API call that is faster, more accurate, and requires no GPU/RAM.
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are KALYE, an AI assistant for Metro Manila walkability analysis.
Your job is to analyze street photographs and identify pedestrian infrastructure issues.

You MUST respond with ONLY valid JSON — no markdown, no explanation outside the JSON.

Response format:
{
  "status": "ok",
  "caption": "<one sentence describing the street scene>",
  "detections": [
    {
      "detection_type": "<type>",
      "confidence": <0.0-1.0>,
      "description": "<specific issue observed>",
      "bounding_box": {"x": 0, "y": 0, "w": 100, "h": 100}
    }
  ],
  "segmentation": {
    "sidewalk_coverage_pct": <0-100>,
    "road_coverage_pct": <0-100>
  },
  "walkability_score": <0-100>,
  "inference_source": "claude_vision"
}

Detection types (use ONLY these values):
- "pothole" — potholes or severe road damage
- "sidewalk_obstruction" — vehicles, vendors, or objects blocking sidewalk
- "missing_sign" — missing or damaged pedestrian/traffic signs
- "curb_ramp" — damaged or missing curb ramps
- "broken_sidewalk" — cracked, uneven, or broken sidewalk surface
- "flooding" — standing water or flood-prone areas
- "missing_ramp" — no wheelchair/accessibility ramp at crossing

Rules:
- Only report issues you can CLEARLY see in the image
- If the street looks clean and accessible, return an empty detections array
- Estimate sidewalk_coverage_pct: % of frame occupied by sidewalk/pavement
- walkability_score: 0=dangerous/inaccessible, 100=excellent/fully accessible
- bounding_box x/y are pixel offsets from top-left (approximate is fine)
"""

USER_PROMPT = "Analyze this Metro Manila street photo for walkability issues."


async def analyze_with_claude(
    image_bytes: bytes,
    media_type: str = "image/jpeg",
    model: str = "claude-haiku-4-5-20251001",
) -> Optional[dict]:
    """Send image to Claude Vision and return structured walkability analysis.

    Returns None if API key is not configured or on any error.
    """
    from src.config.settings import get_settings

    settings = get_settings()
    if not settings.anthropic_api_key:
        logger.debug("ANTHROPIC_API_KEY not set — skipping Claude Vision")
        return None

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

        image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

        message = client.messages.create(
            model=model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_b64,
                            },
                        },
                        {"type": "text", "text": USER_PROMPT},
                    ],
                }
            ],
        )

        raw = message.content[0].text.strip()
        # Strip markdown code fences if Claude wrapped the JSON
        if raw.startswith("```"):
            raw = raw.split("```", 2)[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        result = json.loads(raw)
        result["inference_source"] = "claude_vision"

        logger.info(
            "Claude Vision: %d detections, score=%s, caption=%s",
            len(result.get("detections", [])),
            result.get("walkability_score"),
            result.get("caption", "")[:80],
        )
        return result

    except json.JSONDecodeError as exc:
        logger.warning("Claude Vision returned non-JSON: %s", exc)
    except Exception as exc:
        logger.warning("Claude Vision error: %s", exc)

    return None
