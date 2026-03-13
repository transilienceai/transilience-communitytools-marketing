"""
Storyboard scene planning using Gemini Vision.

Analyzes ALL captured website screenshots + storyline to produce a structured
scene plan. Gemini sees every capture and picks the best one per scene.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from src.ai.gemini_client import generate_with_images, generate_with_content_blocks, generate_text
from src.pipeline.veo_pipeline import VIDEO_STYLE_PROFILES

logger = logging.getLogger(__name__)


@dataclass
class StoryboardScene:
    """A single scene in the storyboard."""
    scene_number: int
    title: str
    voiceover_script: str
    image_description: str          # Imagen prompt
    best_capture_index: int         # Index of the best capture to use (-1 = none)
    best_capture_reason: str        # Why this capture was chosen


@dataclass
class Storyboard:
    """Complete storyboard plan."""
    url: str
    storyline: str
    scenes: List[StoryboardScene] = field(default_factory=list)
    product: str = ""
    tone: str = ""
    style: str = "marketing"


def plan_storyboard(
    storyline: str,
    url: str,
    captures: List[Path],
    capture_labels: List[str],
    num_scenes: int = 6,
    product: str = "",
    context: str = "",
    tone: str = "professional and engaging",
    style: str = "marketing",
    api_key: Optional[str] = None,
) -> Storyboard:
    """
    Plan a storyboard by showing Gemini ALL captured screenshots.

    Gemini sees every capture (labeled by index) and picks the best one
    for each scene, plus writes an Imagen prompt as fallback.

    Args:
        storyline: Narrative arc for the video.
        url: Website URL (for context).
        captures: List of paths to captured screenshot images.
        capture_labels: Label for each capture (e.g., "homepage_scroll_0").
        num_scenes: Number of scenes to plan.
        product: Product/service name.
        context: Additional context.
        tone: Script tone.
        style: Video style profile.
        api_key: Google API key.

    Returns:
        Storyboard with planned scenes.
    """
    profile = VIDEO_STYLE_PROFILES.get(style, VIDEO_STYLE_PROFILES["marketing"])
    product_line = f"Product/Service: {product}" if product else ""
    context_line = f"Additional context: {context}" if context else ""

    # Build content blocks: interleave labels and images
    # Limit to ~20 images to stay within Gemini's limits
    has_captures = len(captures) > 0
    if has_captures:
        max_images = min(len(captures), 20)
        step = max(1, len(captures) // max_images)
        selected_indices = list(range(0, len(captures), step))[:max_images]
    else:
        selected_indices = []

    content_blocks = []

    if has_captures:
        content_blocks.append(
            f"You are a storyboard director. Below are {len(selected_indices)} screenshots "
            f"captured from the website {url}. Each is labeled with its INDEX number.\n"
            f"Review ALL of them, then plan {num_scenes} video scenes.\n\n"
        )

        for i in selected_indices:
            cap_path = captures[i]
            label = capture_labels[i]
            img_bytes = cap_path.read_bytes()
            mime = "image/png" if cap_path.suffix.lower() == ".png" else "image/jpeg"
            content_blocks.append(f"\n--- CAPTURE INDEX {i}: {label} ---\n")
            content_blocks.append((img_bytes, mime))

        capture_instructions = (
            "For each scene, pick the BEST capture from the screenshots above (by index).\n"
            "Use DIFFERENT captures for different scenes — don't reuse the same capture.\n"
        )
    else:
        content_blocks.append(
            f"You are a storyboard director planning scenes for a video about {url}.\n"
            f"No screenshots are available — focus on the storyline and generate strong Imagen prompts.\n\n"
        )
        capture_instructions = (
            "No screenshots are available, so set best_capture_index to -1 for all scenes.\n"
        )

    content_blocks.append(f"""
{profile["persona"]}

VOICE GUIDELINES:
{profile["voice"]}

STRUCTURE:
{profile["structure"]}

TASK:
Plan exactly {num_scenes} scenes for a marketing video.
Storyline: "{storyline}"
{product_line}
{context_line}
Tone: {tone}

{capture_instructions}
Write a detailed Imagen image description for each scene.

Return ONLY a JSON array with exactly {num_scenes} objects. No markdown fences.

Each object:
- "scene_number": integer (1 to {num_scenes})
- "title": short scene title (2-4 words)
- "voiceover_script": narration (15-25 words, punchy)
- "best_capture_index": integer index of the best screenshot (-1 if none)
- "best_capture_reason": 1 sentence why this capture fits (or "no captures" if -1)
- "image_description": detailed Imagen prompt (2-3 sentences). Describe FUTURISTIC TECHNOLOGY in clean, minimal settings. Focus on the tech itself — holographic displays, transparent screens, floating data, AI interfaces — NOT environments like cities, corridors, or buildings. Occasionally (2-3 scenes max) include one person interacting with the tech. Must look completely DIFFERENT from website screenshots.

CRITICAL — FUTURISTIC TECHNOLOGY FOCUS:
Show the TECHNOLOGY, not the environment. Keep backgrounds clean and minimal.
- Technology: holographic dashboards, floating 3D data visualizations, transparent tablets, translucent data interfaces, digital whiteboards with AI diagrams, robotic arms, floating notification panels, real-time metric displays, holographic charts
- Settings (keep minimal): clean white desk, simple dark background, modern room with natural light, plain lab bench — the tech is the subject, not the room
- Occasional humans (2-3 scenes only): one person interacting with holographic interface, hands swiping data, person at a digital whiteboard
- Camera: close-up of tech detail, medium shot of floating display, top-down of digital surface, macro of interface interaction
- Lighting: soft ambient glow, warm golden tones, cool blue highlights, soft diffused white, subtle cyan accents

SCENE GUIDELINES:
- Scene 1: hook — striking shot of futuristic tech in action
- Last scene: CTA — bright, warm, inviting tone
- Middle scenes: alternate between wide tech shots and close-up details
- NO two consecutive scenes should show the same type of technology or color palette
- NEVER describe cities, corridors, server rooms, or building environments
- NEVER describe UI mockups, app screens, or website layouts — those come from screenshots
- {profile["avoid"]}
""")

    max_retries = 3
    last_error = None

    for attempt in range(max_retries):
        try:
            if has_captures:
                raw = generate_with_content_blocks(
                    blocks=content_blocks,
                    max_output_tokens=8192,
                    api_key=api_key,
                )
            else:
                # No images — use text-only call
                prompt_text = "\n".join(
                    b for b in content_blocks if isinstance(b, str)
                )
                raw = generate_text(
                    prompt=prompt_text,
                    max_output_tokens=8192,
                    api_key=api_key,
                )

            if not raw:
                last_error = "Gemini returned empty response"
                logger.warning("Attempt %d: %s", attempt + 1, last_error)
                continue

            # Strip markdown fences
            cleaned = raw.strip()
            if "```" in cleaned:
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
                cleaned = cleaned.strip()

            scenes_data = json.loads(cleaned)

            if not isinstance(scenes_data, list):
                last_error = f"Expected JSON array, got {type(scenes_data).__name__}"
                logger.warning("Attempt %d: %s", attempt + 1, last_error)
                continue

            scenes = []
            for item in scenes_data:
                cap_idx = int(item.get("best_capture_index", -1))
                # Validate index is in our selected set
                if cap_idx < 0 or cap_idx >= len(captures):
                    cap_idx = -1

                scenes.append(StoryboardScene(
                    scene_number=item.get("scene_number", len(scenes) + 1),
                    title=item.get("title", f"Scene {len(scenes) + 1}"),
                    voiceover_script=item.get("voiceover_script", ""),
                    image_description=item.get("image_description", ""),
                    best_capture_index=cap_idx,
                    best_capture_reason=item.get("best_capture_reason", ""),
                ))

            if len(scenes) < num_scenes // 2:
                last_error = f"Too few scenes: {len(scenes)}"
                logger.warning("Attempt %d: %s", attempt + 1, last_error)
                continue

            return Storyboard(
                url=url,
                storyline=storyline,
                scenes=scenes,
                product=product,
                tone=tone,
                style=style,
            )

        except json.JSONDecodeError as e:
            last_error = f"Invalid JSON: {e}"
            logger.warning("Attempt %d: %s. Raw: %.200s", attempt + 1, last_error, raw)
            continue
        except Exception as e:
            last_error = str(e)
            logger.warning("Attempt %d failed: %s", attempt + 1, last_error)
            continue

    raise ValueError(f"Failed to plan storyboard after {max_retries} attempts. Last error: {last_error}")


def write_storyboard_text(storyboard: Storyboard, output_path: Path) -> Path:
    """Write a human-readable storyboard text file."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append(f"STORYBOARD: {storyboard.product or storyboard.url}")
    lines.append(f"URL: {storyboard.url}")
    lines.append(f"Storyline: {storyboard.storyline}")
    lines.append(f"Style: {storyboard.style} | Tone: {storyboard.tone}")
    lines.append(f"Scenes: {len(storyboard.scenes)}")
    lines.append("=" * 60)
    lines.append("")

    for scene in storyboard.scenes:
        lines.append(f"SCENE {scene.scene_number}: {scene.title}")
        lines.append(f"  Script: {scene.voiceover_script}")
        lines.append(f"  Best capture: #{scene.best_capture_index} — {scene.best_capture_reason}")
        lines.append(f"  Imagen fallback: {scene.image_description}")
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Storyboard written to %s", output_path)
    return output_path
