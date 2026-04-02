# Gemini Client — `src/ai/gemini_client.py`

## Description

Thin wrapper over the google-genai SDK for Gemini Vision and text generation (gemini-2.5-flash).

## Functions

### `get_client(api_key=None) -> genai.Client`
Create a Gemini client. Falls back to `GOOGLE_API_KEY` env var.

### `generate_with_images(prompt, images, max_output_tokens=8192, api_key=None, model="gemini-2.5-flash") -> str`
Vision call: one or more images + text prompt. `images` is a list of `(raw_bytes, mime_type)` tuples. Returns stripped text response.

### `generate_text(prompt, max_output_tokens=8192, api_key=None, model="gemini-2.5-flash") -> str`
Text-only generation call. Returns stripped text response.

### `generate_with_content_blocks(blocks, max_output_tokens=2000, api_key=None, model="gemini-2.5-flash") -> str`
Complex multi-image call with interleaved text and image blocks. `blocks` is a list where each item is either a `str` (text) or a `(raw_bytes, mime_type)` tuple (image). Returns stripped text response.

## Internal

### `_extract_text(response) -> str`
Extracts text from Gemini response. Logs warnings for truncation (non-STOP finish_reason), blocked safety ratings, or empty candidates.

## Dependencies
- `google-genai` SDK (`google.genai`, `google.genai.types`)
- Requires `GOOGLE_API_KEY` env var

## Usage
```python
from src.ai.gemini_client import generate_with_images, generate_text, generate_with_content_blocks

# Vision
text = generate_with_images("Describe this image", [(img_bytes, "image/png")])

# Text only
text = generate_text("Write a marketing script for...")

# Interleaved content
result = generate_with_content_blocks([
    "Analyze these screenshots:",
    (img1_bytes, "image/png"),
    "Compare with:",
    (img2_bytes, "image/jpeg"),
])
```
