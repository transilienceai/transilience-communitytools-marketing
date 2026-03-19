"""
Bookend Generator — creates branded intro and outro frames for marketing videos.

Generates 3 options each for intro and outro using Gemini (creative direction)
and Imagen 4.0 (image generation), then animates the selected frame with Veo 3.1.
"""

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()
logger = logging.getLogger(__name__)

NUM_OPTIONS = 3


@dataclass
class BookendSuggestion:
    """A single intro or outro concept."""
    option_number: int
    title_text: str
    subtitle_text: str
    image_description: str
    veo_motion_prompt: str


def generate_bookend_suggestions(
    bookend_type: str,
    product: str = "",
    storyline: str = "",
    tone: str = "professional and engaging",
    style: str = "marketing",
    context: str = "",
    api_key: Optional[str] = None,
) -> List[BookendSuggestion]:
    """
    Use Gemini to generate 3 creative concepts for an intro or outro frame.

    Returns:
        List of 3 BookendSuggestion objects.
    """
    from ..ai.gemini_client import generate_text

    product_name = product or "the product"

    if bookend_type == "intro":
        role = "opening title card"
        text_guidance = (
            f"- title_text: The product name \"{product_name}\" or a bold opening statement\n"
            "- subtitle_text: A compelling tagline derived from the storyline (8-12 words max)\n"
        )
        visual_guidance = (
            "Describe a PROFESSIONAL branded background for a title card. "
            "Think: clean gradient, abstract shapes, subtle light effects, premium feel. "
            "The visual should evoke authority and set the tone for what's coming."
        )
    else:
        role = "closing CTA card"
        text_guidance = (
            "- title_text: A clear call-to-action (e.g., 'Get Started Today', 'Book a Demo', 'Try It Free')\n"
            f"- subtitle_text: Product name \"{product_name}\" with a closing line (e.g., website URL placeholder or tagline)\n"
        )
        visual_guidance = (
            "Describe a PROFESSIONAL closing background. "
            "Think: warm, inviting, bright tones, clean design, sense of completion and possibility. "
            "Should feel like a natural ending that encourages action."
        )

    prompt = f"""Generate exactly {NUM_OPTIONS} creative concepts for a video {role}.

Product: {product_name}
Storyline: {storyline or 'General marketing video'}
Tone: {tone}
Context: {context or 'Marketing video'}

For each concept provide:
{text_guidance}
- image_description: A detailed Imagen prompt for the visual background (2-3 sentences). DO NOT include any text or words in the image — text will be overlaid separately. Focus on abstract professional visuals, lighting, color palette, and mood.
- veo_motion_prompt: A detailed Veo video prompt for 5-second animation. MUST include: the product name "{product_name}", the visual style/tone "{tone}", and a cinematic camera motion. Example: "Elegant branded intro for {product_name}, {tone} style, slow zoom out revealing a glowing dashboard with subtle particle effects and premium lighting"

Each concept should feel DISTINCTLY different — vary the visual style, color palette, and mood.

Return ONLY a JSON array of {NUM_OPTIONS} objects. No markdown fences.
[
  {{"title_text": "...", "subtitle_text": "...", "image_description": "...", "veo_motion_prompt": "..."}},
  ...
]"""

    max_retries = 3
    for attempt in range(max_retries):
        try:
            raw = generate_text(prompt=prompt, max_output_tokens=2000, api_key=api_key, json_output=True)
            if not raw:
                continue

            cleaned = raw.strip()
            if "```" in cleaned:
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
                cleaned = cleaned.strip()

            data = json.loads(cleaned)
            if not isinstance(data, list) or len(data) < 1:
                continue

            suggestions = []
            for i, item in enumerate(data[:NUM_OPTIONS]):
                suggestions.append(BookendSuggestion(
                    option_number=i + 1,
                    title_text=item.get("title_text", product_name),
                    subtitle_text=item.get("subtitle_text", ""),
                    image_description=item.get("image_description", ""),
                    veo_motion_prompt=item.get("veo_motion_prompt", "slow elegant zoom out"),
                ))
            return suggestions

        except (json.JSONDecodeError, Exception) as e:
            logger.warning("Attempt %d for %s suggestions failed: %s", attempt + 1, bookend_type, e)
            continue

    raise ValueError(f"Failed to generate {bookend_type} suggestions after {max_retries} attempts")


def generate_bookend_images(
    suggestions: List[BookendSuggestion],
    output_dir: Path,
    bookend_type: str,
    aspect_ratio: str = "16:9",
    api_key: Optional[str] = None,
) -> List[Path]:
    """
    Generate images for all suggestions using Imagen 4.0.

    Returns:
        List of image paths (same length as suggestions).
    """
    from ..ai.imagen_generator import generate_image

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate all images in parallel
    results = [None] * len(suggestions)

    def _gen(idx, s):
        out_path = output_dir / f"{bookend_type}_option_{s.option_number}.png"
        try:
            generate_image(
                prompt=s.image_description,
                output_path=out_path,
                aspect_ratio=aspect_ratio,
                api_key=api_key,
            )
            console.print(f"  [green]✓[/green] {bookend_type.title()} option {s.option_number} generated")
            return out_path
        except Exception as e:
            logger.warning("Imagen failed for %s option %d: %s", bookend_type, s.option_number, e)
            return None

    with ThreadPoolExecutor(max_workers=len(suggestions)) as executor:
        futures = {executor.submit(_gen, i, s): i for i, s in enumerate(suggestions)}
        for future in as_completed(futures):
            idx = futures[future]
            results[idx] = future.result()

    return results


def present_bookend_choices(
    suggestions: List[BookendSuggestion],
    image_paths: List[Path],
    bookend_type: str,
    interactive: bool = True,
) -> int:
    """
    Show options to the user and get their selection.

    Returns:
        0-based index of the selected option.
    """
    table = Table(title=f"{bookend_type.title()} Options", show_header=True)
    table.add_column("#", style="cyan", width=3)
    table.add_column("Title", style="bold white")
    table.add_column("Subtitle", style="white")
    table.add_column("Image", style="dim")

    valid_options = []
    for i, (s, p) in enumerate(zip(suggestions, image_paths)):
        if p and Path(p).exists():
            table.add_row(str(i + 1), s.title_text, s.subtitle_text, str(p.name))
            valid_options.append(i)
        else:
            table.add_row(str(i + 1), s.title_text, s.subtitle_text, "[red]failed[/red]")

    console.print(table)

    if not valid_options:
        raise ValueError(f"No valid {bookend_type} images generated")

    if not interactive or len(valid_options) == 1:
        choice = valid_options[0]
        console.print(f"  Auto-selected option {choice + 1}")
        return choice

    while True:
        try:
            raw = console.input(f"\n  Select {bookend_type} option [bold][1-{NUM_OPTIONS}][/bold]: ")
            idx = int(raw.strip()) - 1
            if idx in valid_options:
                return idx
            console.print(f"  [yellow]Please pick from: {', '.join(str(v+1) for v in valid_options)}[/yellow]")
        except (ValueError, EOFError):
            return valid_options[0]


def animate_bookend(
    image_path: Path,
    suggestion: BookendSuggestion,
    output_path: Path,
    duration: int = 5,
    resolution: str = "1080p",
    api_key: Optional[str] = None,
    product: str = "",
    tone: str = "",
    style: str = "",
) -> Path:
    """
    Animate a bookend image using Veo 3.1.

    Falls back to a static ImageClip if Veo fails.
    """
    from ..ai.veo_generator import generate_video_veo

    # Build rich prompt with product, style, and motion context
    motion = suggestion.veo_motion_prompt
    product_name = product or suggestion.title_text or "the product"
    parts = []
    if product_name:
        parts.append(f"Branded video frame for \"{product_name}\"")
    if style:
        parts.append(f"{style} style")
    if tone:
        parts.append(f"{tone} tone")
    if motion:
        parts.append(motion)
    else:
        parts.append("slow elegant cinematic zoom out with subtle light effects")
    prompt = ", ".join(parts)

    # Generate 8s Veo video and keep full duration (no speed-up for bookends)
    veo_duration = 8

    try:
        generate_video_veo(
            prompt=prompt,
            output_path=output_path,
            image_path=image_path,
            duration=veo_duration,
            resolution=resolution,
            api_key=api_key,
        )
        console.print(f"  [green]✓[/green] Veo generated {output_path.name} ({veo_duration}s)")
        return output_path
    except Exception as e:
        logger.warning("Veo animation failed for bookend: %s — using static frame", e)
        console.print(f"  [yellow]⚠[/yellow] Veo failed, using static frame: {e}")

        # Fallback: static image as clip
        from moviepy import ImageClip
        clip = ImageClip(str(image_path), duration=duration)
        clip = clip.with_fps(30)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        clip.write_videofile(str(output_path), fps=30, codec='libx264', logger=None)
        clip.close()
        return output_path


def generate_bookends(
    product: str = "",
    storyline: str = "",
    tone: str = "professional and engaging",
    style: str = "marketing",
    context: str = "",
    output_dir: Path = None,
    resolution: str = "1080p",
    duration: int = 5,
    interactive: bool = True,
    generate_intro: bool = True,
    generate_outro: bool = True,
    api_key: Optional[str] = None,
) -> Tuple[Optional[Path], Optional[Path]]:
    """
    Generate branded intro and/or outro clips.

    Returns:
        (intro_clip_path, outro_clip_path) — either can be None if disabled or failed.
    """
    if output_dir is None:
        output_dir = Path(".temp_veo_pipeline") / "bookends"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    intro_path = None
    outro_path = None

    def _generate_one(bookend_type):
        console.print(f"\n[bold cyan]Generating {bookend_type} frame options...[/bold cyan]")

        # Step 1: Get 3 creative suggestions from Gemini
        suggestions = generate_bookend_suggestions(
            bookend_type=bookend_type,
            product=product,
            storyline=storyline,
            tone=tone,
            style=style,
            context=context,
            api_key=api_key,
        )
        console.print(f"  [green]✓[/green] {len(suggestions)} {bookend_type} concepts generated")

        # Step 2: Generate images with Imagen 4.0
        console.print(f"  Generating {bookend_type} images with Imagen 4.0...")
        image_paths = generate_bookend_images(
            suggestions, output_dir, bookend_type, api_key=api_key,
        )

        # Step 3: User picks one
        choice = present_bookend_choices(
            suggestions, image_paths, bookend_type, interactive=interactive,
        )
        selected = suggestions[choice]
        selected_image = image_paths[choice]

        console.print(f"  Selected: [bold]{selected.title_text}[/bold] — {selected.subtitle_text}")

        # Step 4: Animate with Veo
        clip_path = output_dir / f"{bookend_type}_animated.mp4"
        result = animate_bookend(
            image_path=selected_image,
            suggestion=selected,
            output_path=clip_path,
            duration=duration,
            resolution=resolution,
            api_key=api_key,
            product=product,
            tone=tone,
            style=style,
        )
        return bookend_type, result

    types_to_generate = [(t, e) for t, e in [("intro", generate_intro), ("outro", generate_outro)] if e]

    with ThreadPoolExecutor(max_workers=len(types_to_generate)) as executor:
        futures = {executor.submit(_generate_one, t): t for t, _ in types_to_generate}
        for future in as_completed(futures):
            bookend_type = futures[future]
            try:
                _, result = future.result()
                if bookend_type == "intro":
                    intro_path = result
                else:
                    outro_path = result
            except Exception as e:
                console.print(f"  [yellow]⚠[/yellow] {bookend_type.title()} generation failed: {e}")
                logger.warning("%s generation failed: %s", bookend_type, e)

    return intro_path, outro_path
