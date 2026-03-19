"""
Gemini API wrapper for vision and text generation.

Provides a thin abstraction over the google-genai SDK, replacing all
Anthropic/Claude calls with Google Gemini (gemini-2.5-flash).
"""

import os
import logging
from typing import List, Optional, Tuple

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-2.5-flash"


def get_client(api_key: Optional[str] = None) -> genai.Client:
    """Create a Gemini client using the given or environment API key."""
    api_key = api_key or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not set")
    return genai.Client(api_key=api_key)


def _extract_text(response) -> str:
    """Extract text from Gemini response, logging the reason if empty or truncated."""
    if response.text:
        # Check if the response was truncated (hit max_output_tokens)
        if hasattr(response, "candidates") and response.candidates:
            finish_reason = getattr(response.candidates[0], "finish_reason", None)
            if finish_reason and str(finish_reason) not in ("STOP", "FinishReason.STOP", "stop", "1"):
                logger.warning("Gemini response may be truncated: finish_reason=%s", finish_reason)
        return response.text.strip()
    # Diagnose why there's no text
    reasons = []
    if hasattr(response, "prompt_feedback") and response.prompt_feedback:
        reasons.append(f"prompt_feedback={response.prompt_feedback}")
    if hasattr(response, "candidates") and response.candidates:
        for i, c in enumerate(response.candidates):
            if hasattr(c, "finish_reason") and c.finish_reason:
                reasons.append(f"candidate[{i}].finish_reason={c.finish_reason}")
            if hasattr(c, "safety_ratings") and c.safety_ratings:
                blocked = [r for r in c.safety_ratings if hasattr(r, "blocked") and r.blocked]
                if blocked:
                    reasons.append(f"candidate[{i}].blocked_safety={blocked}")
    else:
        reasons.append("no candidates returned")
    logger.warning("Gemini returned no text: %s", "; ".join(reasons) or "unknown reason")
    return ""


def generate_with_images(
    prompt: str,
    images: List[Tuple[bytes, str]],
    max_output_tokens: int = 8192,
    api_key: Optional[str] = None,
    model: str = DEFAULT_MODEL,
) -> str:
    """
    Vision call: one or more images + a text prompt.

    Args:
        prompt: Text prompt to send alongside the images.
        images: List of (raw_bytes, mime_type) tuples, e.g. [(b"...", "image/png")].
        max_output_tokens: Maximum tokens in the response.
        api_key: Google API key (falls back to GOOGLE_API_KEY env var).
        model: Gemini model ID.

    Returns:
        The model's text response, stripped of whitespace.
    """
    client = get_client(api_key)

    contents = []
    for image_bytes, mime_type in images:
        contents.append(types.Part.from_bytes(data=image_bytes, mime_type=mime_type))
    contents.append(prompt)

    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(max_output_tokens=max_output_tokens),
    )
    return _extract_text(response)


def generate_text(
    prompt: str,
    max_output_tokens: int = 8192,
    api_key: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    json_output: bool = False,
) -> str:
    """
    Text-only generation call.

    Args:
        prompt: The text prompt.
        max_output_tokens: Maximum tokens in the response.
        api_key: Google API key.
        model: Gemini model ID.
        json_output: If True, force JSON output via response_mime_type.

    Returns:
        The model's text response, stripped of whitespace.
    """
    client = get_client(api_key)

    config = types.GenerateContentConfig(max_output_tokens=max_output_tokens)
    if json_output:
        config.response_mime_type = "application/json"

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=config,
    )
    return _extract_text(response)


def generate_with_content_blocks(
    blocks: list,
    max_output_tokens: int = 2000,
    api_key: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    json_output: bool = False,
) -> str:
    """
    Complex multi-image call using interleaved text and image blocks.

    Args:
        blocks: List of content items. Each item is either:
            - a str (text block)
            - a tuple of (raw_bytes, mime_type) for an image
        max_output_tokens: Maximum tokens in the response.
        api_key: Google API key.
        model: Gemini model ID.
        json_output: If True, force JSON output via response_mime_type.

    Returns:
        The model's text response, stripped of whitespace.
    """
    client = get_client(api_key)

    contents = []
    for block in blocks:
        if isinstance(block, str):
            contents.append(block)
        elif isinstance(block, tuple) and len(block) == 2:
            image_bytes, mime_type = block
            contents.append(types.Part.from_bytes(data=image_bytes, mime_type=mime_type))
        else:
            raise ValueError(f"Unexpected block type: {type(block)}")

    config = types.GenerateContentConfig(max_output_tokens=max_output_tokens)
    if json_output:
        config.response_mime_type = "application/json"

    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=config,
    )
    return _extract_text(response)
