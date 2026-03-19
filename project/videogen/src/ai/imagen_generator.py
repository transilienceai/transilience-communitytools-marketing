"""
Imagen 3.0 image generation wrapper.

Uses the google-genai SDK to generate images via Google's Imagen 3.0 model.
"""

import logging
from pathlib import Path
from typing import Optional

from google.genai import types

from src.ai.gemini_client import get_client

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "imagen-4.0-generate-001"


def generate_image(
    prompt: str,
    output_path: Path,
    aspect_ratio: str = "16:9",
    api_key: Optional[str] = None,
    model: str = DEFAULT_MODEL,
) -> Path:
    """
    Generate an image using Google Imagen.

    Args:
        prompt: Text description of the image to generate.
        output_path: Where to save the generated image (PNG).
        aspect_ratio: Aspect ratio (e.g., "16:9", "9:16", "1:1").
        api_key: Google API key (falls back to GOOGLE_API_KEY env var).
        model: Imagen model ID.

    Returns:
        Path to the saved image file.

    Raises:
        RuntimeError: If image generation fails or returns no images.
    """
    client = get_client(api_key)

    logger.info("Generating image with %s: %.100s...", model, prompt)

    try:
        response = client.models.generate_images(
            model=model,
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio=aspect_ratio,
            ),
        )
    except Exception as e:
        raise RuntimeError(f"Imagen API call failed: {e}") from e

    if not response.generated_images:
        raise RuntimeError("Imagen returned no images")

    generated = response.generated_images[0]
    image = generated.image

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Save image bytes — try known attributes
    image_data = None
    if hasattr(image, "image_bytes") and image.image_bytes:
        image_data = image.image_bytes
    elif hasattr(image, "data") and image.data:
        image_data = image.data
    elif hasattr(image, "_pil_image") and image._pil_image:
        image._pil_image.save(str(output_path))
        logger.info("Saved generated image to %s (via PIL)", output_path)
        return output_path

    if image_data:
        output_path.write_bytes(image_data)
        logger.info("Saved generated image to %s (%d bytes)", output_path, len(image_data))
        return output_path

    # Last resort: try to save via PIL if the SDK loaded it
    try:
        image.save(str(output_path))
        logger.info("Saved generated image to %s (via .save())", output_path)
        return output_path
    except Exception:
        pass

    raise RuntimeError(
        f"Could not extract image bytes. "
        f"Image type: {type(image)}, attrs: {[a for a in dir(image) if not a.startswith('__')]}"
    )
