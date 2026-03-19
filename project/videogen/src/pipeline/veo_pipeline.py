"""
Veo 3.1 Marketing Video Pipeline
Complete pipeline that uses Google Veo 3.1 for high-quality video generation.

Pipeline:
1. Analyze images with Claude Vision → Generate engaging scripts
2. Generate video from each image using Veo 3.1 (with motion, effects)
3. Add voiceover synced with video (ElevenLabs/Edge TTS)
4. Add background music
5. Combine into final marketing video

Features:
- AI-powered script generation
- Veo 3.1 image-to-video with cinematic motion
- Voice cloning support (Smritika, etc.)
- Background music integration
- Professional transitions
"""

import os
import re
import asyncio
import shutil
import time
from pathlib import Path
from typing import List, Optional, Tuple
from dataclasses import dataclass
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.panel import Panel
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

console = Console()

# Style profiles for different video types
VIDEO_STYLE_PROFILES = {
    "marketing": {
        "persona": "You are a world-class pitch strategist who has written decks that closed Series A rounds and enterprise deals. You write scripts that SELL.",
        "voice": (
            "- Write as a PITCH — every sentence should move the viewer closer to saying YES\n"
            "- Open with a bold, provocative statement that creates urgency\n"
            "- Name the PAIN specifically — make the viewer feel it (\"Your team wastes 40 hours a month on manual compliance checks\")\n"
            "- Present the product as the inevitable answer — not optional, necessary\n"
            "- Use proof: numbers, outcomes, credibility signals (\"trusted by 200+ enterprises\")\n"
            "- Build momentum — each scene should raise the stakes higher\n"
            "- Use power contrasts: chaos vs clarity, manual vs automated, risk vs protection\n"
            "- Speak with absolute confidence — no hedging, no \"might\", no \"could\"\n"
            "- End every section with a line that makes them NEED to see the next one"
        ),
        "structure": (
            "1. Scene 1: HOOK — Bold claim or shocking stat that creates instant urgency\n"
            "2. Early scenes: PROBLEM — Paint the pain so vividly they feel it personally\n"
            "3. Middle scenes: SOLUTION — Introduce the product as the answer, show it in action\n"
            "4. Later scenes: PROOF — Features, dashboards, case studies, compliance, trust signals\n"
            "5. Final scene: CTA — Clear, confident call-to-action with urgency (\"Start today\", \"Book a demo\")"
        ),
        "avoid": "Avoid weak language: no \"revolutionary\", \"cutting-edge\", \"seamless\", \"robust\", \"leverage\", \"might\", \"could\", \"try\". Be DEFINITIVE.",
    },
    "feature-explainer": {
        "persona": "You are a senior product expert who makes features feel exciting and essential. You combine technical clarity with compelling storytelling — like a developer advocate who also closes deals.",
        "voice": (
            "- Lead with WHAT the feature does in one punchy sentence, then WHY it matters\n"
            "- Reference actual UI elements, buttons, and workflows visible on screen\n"
            "- Show the before/after: \"Before this, teams had to... Now, with one click...\"\n"
            "- Use specific examples and scenarios: \"Say you're a compliance officer reviewing 200 documents...\"\n"
            "- Explain the WHY behind each feature — connect it to a real pain point\n"
            "- Use phrases like \"notice how\", \"here's what's powerful about this\", \"this is where it gets interesting\"\n"
            "- Quantify the impact: time saved, errors eliminated, steps reduced\n"
            "- Build excitement through capability stacking — each feature makes the previous one even more powerful\n"
            "- Sound like a smart colleague showing you something impressive, not a salesperson"
        ),
        "structure": (
            "1. Scene 1: The big picture — what problem does this feature set solve?\n"
            "2. Early scenes: Core feature — walk through the primary capability with a real scenario\n"
            "3. Middle scenes: Supporting features — show how they work together, highlight key differentiators\n"
            "4. Later scenes: Advanced capabilities — power-user features, integrations, automation\n"
            "5. Final scene: Full picture — recap the transformation and invite them to explore"
        ),
        "avoid": "Avoid vague claims without showing the feature. No marketing fluff — let the product speak. No \"game-changer\", \"revolutionary\". Be specific and grounded.",
    },
    "tutorial-explainer": {
        "persona": "You are a patient, knowledgeable instructor who makes complex workflows feel simple. Think friendly mentor meets clear documentation — warm, practical, zero fluff.",
        "voice": (
            "- Start by setting context: what will the viewer learn and why it matters\n"
            "- Give clear, actionable instructions: \"First, navigate to settings. Then, select the API tab.\"\n"
            "- Reference specific UI elements visible on screen by name — buttons, menus, panels\n"
            "- Explain concepts as you go — assume the viewer is smart but new to this\n"
            "- Use analogies to make abstract ideas concrete: \"Think of this like a filter for your data...\"\n"
            "- Anticipate confusion: \"You might notice X appears here — that's normal, it means...\"\n"
            "- Celebrate progress: \"Great, you've just configured the core integration.\"\n"
            "- Add practical tips: \"Pro tip: you can also do this with a keyboard shortcut...\" \"A common mistake here is...\"\n"
            "- Keep a steady, calm pace — this is educational, not a hype video\n"
            "- Connect each step to the bigger goal so the viewer never loses context"
        ),
        "structure": (
            "1. Scene 1: Overview — what we're going to accomplish and what you'll need\n"
            "2. Early scenes: Setup — prerequisites, initial configuration, getting started\n"
            "3. Middle scenes: Core workflow — step-by-step walkthrough, one action per scene\n"
            "4. Later scenes: Customization — options, settings, and how to adapt it to your needs\n"
            "5. Final scene: Summary — recap what was accomplished, common next steps, and where to learn more"
        ),
        "avoid": "Avoid skipping steps. No assuming the viewer already knows how. No marketing language or hype. No jargon without explanation.",
    },
}


@dataclass
class SceneData:
    """Data for a single scene in the video."""
    image_path: Path
    script: str
    extracted_text: str = ""  # OCR text from image
    text_regions: List[dict] = None  # Bounding boxes for text overlay
    video_path: Optional[Path] = None
    audio_path: Optional[Path] = None
    duration: float = 8.0
    is_video: bool = False  # True for video input scenes (skip Vision/Veo)
    preserve_audio: bool = False  # True = keep original audio, mix voiceover on top (screen recordings)
    last_image_path: Optional[Path] = None  # Second image for paired Veo transitions
    last_extracted_text: str = ""  # OCR text from last image

    def __post_init__(self):
        if self.text_regions is None:
            self.text_regions = []


def extract_image_text(
    image_path: Path,
    api_key: Optional[str] = None,
) -> str:
    """
    Extract all visible text from an image using Gemini Vision (OCR only).

    Args:
        image_path: Path to the image
        api_key: Google API key

    Returns:
        Extracted text string
    """
    from ..ai.gemini_client import generate_with_images

    api_key = api_key or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not set")

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    ext = image_path.suffix.lower()
    media_type = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(ext, "image/png")

    ocr_prompt = """Extract ALL text visible in this image exactly as it appears.
Include:
- Headlines and titles
- Button labels
- Menu items
- Any text content, numbers, labels
- Preserve the exact spelling and formatting

Return ONLY the extracted text, nothing else. List each text element on a new line."""

    return generate_with_images(
        prompt=ocr_prompt,
        images=[(image_bytes, media_type)],
        max_output_tokens=500,
        api_key=api_key,
    )


def generate_pitch_from_storyline(
    storyline: str,
    num_scenes: int = 5,
    num_images: int = 0,
    context: str = "",
    tone: str = "bold, confident, high-stakes, enterprise-focused",
    product: str = "",
    api_key: Optional[str] = None,
) -> str:
    """
    Generate a pitch script from a storyline, scaled to the number of scenes.
    Knows the exact shortlisted image count and scene count for precise word budgeting.

    Returns:
        Pitch script with exactly num_scenes sentences (~15 words each = 6s per scene).
    """
    from ..ai.gemini_client import generate_text

    api_key = api_key or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not set")

    total_words = num_scenes * 15  # 15 words ≈ 6 seconds per scene at 2.5 words/sec
    duration_secs = num_scenes * 6

    product_line = f"\nProduct/Company: {product}" if product else ""
    context_line = f"\nContext: {context}" if context else ""
    image_line = f"\nVisual assets: {num_images} shortlisted images forming {num_scenes} scenes (2 images per scene transition)" if num_images else ""

    # Build dynamic structure — distribute 5 beats across N scenes
    structure_lines = []
    for i in range(num_scenes):
        if i == 0:
            beat = "HOOK"
        elif i == num_scenes - 1:
            beat = "CTA"
        else:
            mid_pos = (i - 1) / max(num_scenes - 2, 1)
            if mid_pos < 0.33:
                beat = "PAIN"
            elif mid_pos < 0.66:
                beat = "SOLUTION"
            else:
                beat = "PROOF"
        structure_lines.append(f"{i+1}. [{beat}] <write 12-15 words here>")
    structure_block = "\n".join(structure_lines)

    prompt = f"""Convert this storyline into a numbered list of {num_scenes} pitch sentences.

STORYLINE (your ONLY source — use its exact terms, product names, and concepts):
\"\"\"{storyline}\"\"\"
{product_line}{context_line}

Use the EXACT keywords and terminology from the storyline verbatim. Do NOT substitute generic phrases.

Each sentence: 12-15 words, ending with . ! or ?
Tone: {tone}

Write exactly this format — fill in each line:
{structure_block}

Return ONLY the numbered list."""

    import re

    max_retries = 5
    best_sentences = []

    for attempt in range(max_retries):
        pitch = generate_text(
            prompt=prompt,
            max_output_tokens=4000,
            api_key=api_key,
        )

        if not pitch or not pitch.strip():
            console.print(f"  [yellow]⚠[/yellow] Attempt {attempt+1}: empty response, retrying...")
            continue

        # Parse numbered lines: "1. sentence" or "1) sentence" or just sentences
        lines = pitch.strip().split("\n")
        sentences = []
        for line in lines:
            # Strip numbering: "1. text", "1) text", "1: text"
            cleaned = re.sub(r'^\d+[\.\)\:]\s*', '', line.strip())
            # Strip beat labels: "[HOOK]", "(PAIN)", etc.
            cleaned = re.sub(r'^\[?\(?(HOOK|PAIN|SOLUTION|PROOF|CTA|DEMO)\)?\]?\s*[-:—]?\s*', '', cleaned, flags=re.IGNORECASE)
            cleaned = cleaned.strip()
            if cleaned and len(cleaned.split()) >= 5:
                # Ensure ends with punctuation
                if cleaned[-1] not in '.!?':
                    cleaned += '.'
                sentences.append(cleaned)

        # Keep track of best attempt
        if len(sentences) > len(best_sentences):
            best_sentences = sentences

        if len(sentences) == num_scenes:
            # Check evenness
            word_counts = [len(s.split()) for s in sentences]
            console.print(f"[green]✓[/green] Pitch generated: {sum(word_counts)} words, {len(sentences)} sentences ({', '.join(str(wc) for wc in word_counts)} words each)")
            for i, s in enumerate(sentences):
                console.print(f"[dim]  {i+1}. {s}[/dim]")
            return "\n".join(sentences)

        console.print(f"  [yellow]⚠[/yellow] Attempt {attempt+1}: got {len(sentences)} sentences (need {num_scenes}), retrying...")

    # All retries failed — return best attempt or empty (caller will fall back to AI generation)
    if len(best_sentences) >= num_scenes:
        # Trim to exact count
        best_sentences = best_sentences[:num_scenes]
        console.print(f"[yellow]⚠[/yellow] Using best attempt: {len(best_sentences)} sentences")
        return "\n".join(best_sentences)
    elif best_sentences:
        console.print(f"[yellow]⚠[/yellow] Pitch only got {len(best_sentences)}/{num_scenes} sentences — falling back to AI scene generation")
        return ""  # Return empty so caller skips pitch path
    else:
        console.print(f"[yellow]⚠[/yellow] Pitch generation failed completely — falling back to AI scene generation")
        return ""


def generate_unified_narrative(
    scenes: List[dict],
    context: str = "",
    tone: str = "professional and engaging",
    storyline: str = "",
    product: str = "",
    target_duration: int = 60,
    style: str = "marketing",
    pitch_script: str = "",
    api_key: Optional[str] = None,
) -> List[str]:
    """
    Generate a cohesive narrative across ALL scenes in a single Claude call.

    If pitch_script is provided (from generate_pitch_from_storyline), it splits
    that pitch across scenes matched to images. Otherwise generates from scratch.

    Each scene dict should have:
        - image_path: Path to the image (used as thumbnail)
        - extracted_text: OCR text from the image
        - is_video: bool
        - position: int (0-based)
        - fixed_script: optional str (for video scenes with existing polished transcripts)

    Args:
        target_duration: Total narration duration in seconds (default: 60).
            Word budget is split across scenes (~5 words/sec).

    Returns:
        List[str] — one script per scene, in order. Fixed scripts are returned as-is.
    """
    from ..ai.gemini_client import generate_with_content_blocks as gemini_generate
    import json

    api_key = api_key or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not set")

    num_scenes = len(scenes)
    if num_scenes == 0:
        return []

    # Build content blocks: thumbnail + metadata for each scene
    content_blocks = []
    for i, scene in enumerate(scenes):
        label_parts = [f"Scene {i + 1} of {num_scenes}"]
        if scene.get("fixed_script"):
            label_parts.append("(VIDEO — script is FIXED, do not rewrite)")
        label = " ".join(label_parts)

        content_blocks.append(f"--- {label} ---")

        # Add thumbnail image
        img_path = Path(scene["image_path"])
        if img_path.exists() and img_path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}:
            with open(img_path, "rb") as f:
                image_bytes = f.read()
            ext = img_path.suffix.lower()
            media_type = {
                ".png": "image/png", ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg", ".webp": "image/webp",
                ".gif": "image/gif", ".bmp": "image/bmp",
            }.get(ext, "image/png")
            content_blocks.append((image_bytes, media_type))

        # Add OCR text and any fixed script
        meta = f"Visible text: {scene.get('extracted_text', '(none)')}"
        if scene.get("fixed_script"):
            meta += f"\nFIXED SCRIPT (do NOT change this): {scene['fixed_script']}"
        content_blocks.append(meta)

    # Build the narrative prompt
    storyline_line = ""  # handled separately as the pitch backbone
    context_line = f"\nContext: {context}" if context else ""
    product_line = f"\nProduct: {product}" if product else ""

    fixed_indices = [i for i, s in enumerate(scenes) if s.get("fixed_script")]
    fixed_note = ""
    if fixed_indices:
        fixed_labels = ", ".join(str(i + 1) for i in fixed_indices)
        fixed_note = (
            f"\n\nIMPORTANT: Scene(s) {fixed_labels} have FIXED scripts (from video transcripts). "
            "Return those scripts EXACTLY as provided — do not modify them. "
            "Write the surrounding scene scripts so they flow naturally into and out of the fixed scripts."
        )

    # Calculate word budget: ~5 words/sec speaking pace
    # Use per-scene duration when available, otherwise split evenly
    fixed_word_count = sum(
        len(s["fixed_script"].split()) for s in scenes if s.get("fixed_script")
    )

    # Calculate per-scene word targets based on each scene's duration
    scene_word_targets = []
    for s in scenes:
        if s.get("fixed_script"):
            scene_word_targets.append(len(s["fixed_script"].split()))
        elif s.get("duration") and s["duration"] > 0:
            scene_word_targets.append(int(s["duration"] * 2.5))
        else:
            # Static scenes: use target_duration split evenly
            flexible_scenes = max(1, num_scenes - len(fixed_indices))
            remaining_words = max(int(target_duration * 2.5) - fixed_word_count, 30)
            scene_word_targets.append(int(remaining_words / flexible_scenes))

    total_words = sum(scene_word_targets)
    words_per_scene = total_words // max(num_scenes, 1)

    console.print(f"[dim]Narrative budget: {total_words} words total, ~{words_per_scene} words/scene avg[/dim]")

    # Get style profile
    profile = VIDEO_STYLE_PROFILES.get(style, VIDEO_STYLE_PROFILES["marketing"])

    if pitch_script:
        # Pitch already generated from storyline — split deterministically in Python
        # Pitch is newline-separated (one sentence per line) from generate_pitch_from_storyline
        pitch_sentences = [s.strip() for s in pitch_script.strip().split("\n") if s.strip()]

        # Identify fixed (video) scenes vs flexible scenes
        flexible_indices = [i for i in range(num_scenes) if not scenes[i].get("fixed_script")]
        fixed_idx_set = set(range(num_scenes)) - set(flexible_indices)

        # Distribute sentences across flexible scenes — 1:1 mapping
        scripts = [""] * num_scenes

        # Place fixed scripts first
        for i in fixed_idx_set:
            scripts[i] = scenes[i]["fixed_script"]

        n_flex = len(flexible_indices)
        if n_flex > 0 and len(pitch_sentences) > 0:
            if len(pitch_sentences) >= n_flex:
                # More sentences than scenes — merge extras evenly
                per_scene = len(pitch_sentences) // n_flex
                remainder = len(pitch_sentences) % n_flex
                sent_idx = 0
                for j, scene_idx in enumerate(flexible_indices):
                    count = per_scene + (1 if j >= n_flex - remainder else 0)
                    merged = " ".join(pitch_sentences[sent_idx:sent_idx + count])
                    scripts[scene_idx] = merged
                    sent_idx += count
            else:
                # Fewer sentences than scenes — assign what we have, leave rest empty
                for j, sent in enumerate(pitch_sentences):
                    if j < n_flex:
                        scripts[flexible_indices[j]] = sent

        console.print(f"[dim]Split pitch ({len(pitch_sentences)} sentences) across {n_flex} flexible scenes[/dim]")
    else:
        content_blocks.append(f"""{profile["persona"]}

You're writing the voiceover for a {num_scenes}-scene {style} video.
Each scene is shown above with its image and any text visible on screen.
{context_line}{product_line}
Tone: {tone}

TOTAL NARRATION TARGET: approximately {total_words} words (~{int(total_words / 2.5)} seconds when spoken at ~2.5 words/sec).

PER-SCENE WORD TARGETS (based on each scene's video duration):
{chr(10).join(f"  Scene {i+1}: ~{scene_word_targets[i]} words ({scene_word_targets[i] // 5}s)" + (" [FIXED — return as-is]" if scenes[i].get("fixed_script") else "") for i in range(num_scenes))}

Write a TIGHT MARKETING PITCH in {num_scenes} segments (one per scene).

{"STORYLINE — THIS IS YOUR PITCH ARC:" + chr(10) + storyline + chr(10) + "Every segment must advance this story. Images are evidence for the story." if storyline else ""}

PITCH STRUCTURE — assign each scene a role:
- HOOK: Bold one-liner that grabs attention instantly
- PAIN POINT: Name the problem the viewer feels
- SOLUTION: Show how the product fixes it
- DEMO/PROOF: Point at what's on screen as evidence
- CTA: Tell them exactly what to do next
Distribute these roles across the {num_scenes} scenes in order.

RULES:
- Each segment MUST match its word target above. This is CRITICAL — the voiceover must fill each scene's duration.
- Every segment MUST be a complete, closed sentence ending in . ! or ?
- Write like ad copy — punchy, direct, zero filler
- Speak to "you" — the viewer is the hero
- SELL, don't describe. Not "This shows a dashboard" → "Your whole operation, one glance."
- {profile["avoid"]}

Return a JSON array of {num_scenes} strings, one per scene. Example:
["Scene 1 script here...", "Scene 2 script here...", ...]

Return ONLY the JSON array, no other text.""")

    if not pitch_script:
        # No pitch — generate scripts via AI call
        # Token budget: ~10 words/scene but Gemini needs headroom for JSON structure
        token_budget = max(2000, num_scenes * 150)
        raw = gemini_generate(
            blocks=content_blocks,
            max_output_tokens=token_budget,
            api_key=api_key,
        )

        # Parse JSON — handle markdown fences
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        try:
            scripts = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"Gemini returned invalid JSON: {e}. Raw response: {raw[:200]}")

        if not isinstance(scripts, list) or len(scripts) != num_scenes:
            raise ValueError(
                f"Expected {num_scenes} scripts, got {len(scripts) if isinstance(scripts, list) else 'non-list'}. Raw: {raw[:200]}"
            )

        # Ensure fixed scripts are preserved exactly
        for i, scene in enumerate(scenes):
            if scene.get("fixed_script"):
                scripts[i] = scene["fixed_script"]

    # Validate minimum script length — each scene must be at least ~6s of voiceover
    min_words = 13  # 13 words ≈ 5-6 seconds at 2.5 words/sec
    for i, script in enumerate(scripts):
        if scenes[i].get("fixed_script"):
            continue
        word_count = len(script.split())
        if word_count < min_words:
            console.print(
                f"  [yellow]⚠[/yellow] Scene {i+1} script is only {word_count} words "
                f"(minimum ~{min_words}), padding with context"
            )
            # Pad short scripts so TTS generates a reasonable voiceover
            ocr = scenes[i].get("extracted_text", "").strip()
            if ocr:
                scripts[i] = f"{script} {ocr}"
            else:
                # Generic filler that references the scene position
                if i == 0:
                    scripts[i] = f"{script} Let's take a closer look at what makes this possible."
                elif i == num_scenes - 1:
                    scripts[i] = f"{script} That's the full picture — and this is just the beginning."
                else:
                    scripts[i] = f"{script} Here's where things get interesting — watch how it all comes together."

    # Ensure every script ends with a complete sentence (proper closing punctuation)
    for i, script in enumerate(scripts):
        stripped = script.rstrip()
        if stripped and stripped[-1] not in ".!?":
            # Incomplete sentence — close it with a period
            scripts[i] = stripped + "."
            console.print(f"  [dim]Scene {i+1}: closed trailing sentence[/dim]")

    return scripts


def analyze_image_for_script_and_text(
    image_path: Path,
    context: str = "",
    tone: str = "professional and engaging",
    storyline: str = "",
    api_key: Optional[str] = None
) -> Tuple[str, str]:
    """
    Analyze an image with Claude Vision and generate:
    1. A voiceover script
    2. Extracted text from the image (OCR)

    Args:
        image_path: Path to the image
        context: Additional context about the product/service
        tone: Desired tone for the script
        storyline: Narrative storyline to guide the voiceover script
        api_key: Anthropic API key

    Returns:
        Tuple of (voiceover_script, extracted_text)
    """
    from ..ai.gemini_client import generate_with_images

    api_key = api_key or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not set")

    # Read image bytes
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    ext = image_path.suffix.lower()
    media_type = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(ext, "image/png")

    # First, extract all text from the image (OCR)
    ocr_prompt = """Extract ALL text visible in this image exactly as it appears.
Include:
- Headlines and titles
- Button labels
- Menu items
- Any text content, numbers, labels
- Preserve the exact spelling and formatting

Return ONLY the extracted text, nothing else. List each text element on a new line."""

    extracted_text = generate_with_images(
        prompt=ocr_prompt,
        images=[(image_bytes, media_type)],
        max_output_tokens=500,
        api_key=api_key,
    )

    # Now generate the voiceover script
    storyline_section = f"\nStoryline: {storyline}\nIMPORTANT: The voiceover script MUST follow and advance this storyline. Tie what's visible in the image back to this narrative." if storyline else ""

    script_prompt = f"""Write a ~10 word pitch line for this scene of a marketing video.

Context: {context if context else "Product/service marketing video."}
Tone: {tone}{storyline_section}

Rules:
- EXACTLY ~10 words. One or two short punchy sentences.
- Must be a complete sentence ending in . ! or ?
- SELL, don't describe. Not "This shows X" → "Your X, solved."
- Speak to "you" — the viewer is the hero.
- No filler, no clichés, no "revolutionary/cutting-edge/seamless".
{f"- Advance this storyline: {storyline}" if storyline else ""}
Return ONLY the pitch line, nothing else."""

    script = generate_with_images(
        prompt=script_prompt,
        images=[(image_bytes, media_type)],
        max_output_tokens=200,
        api_key=api_key,
    )

    return script, extracted_text


def analyze_video_for_script(
    video_path: Path,
    duration: float,
    context: str = "",
    tone: str = "professional and engaging",
    storyline: str = "",
    temp_dir: Optional[Path] = None,
    api_key: Optional[str] = None
) -> str:
    """
    Analyze a silent video's keyframes with Claude Vision to generate a voiceover script.

    Used when a video input has no spoken audio (empty transcription).
    Extracts keyframes proportional to duration, sends them to Claude Vision,
    and generates a voiceover script.

    Args:
        video_path: Path to the video file
        duration: Video duration in seconds
        context: Product/service context
        tone: Desired script tone
        storyline: Narrative storyline to guide the script
        temp_dir: Directory for temporary keyframe files
        api_key: Anthropic API key

    Returns:
        Voiceover script string, or "" if analysis fails
    """
    from ..ai.gemini_client import generate_with_content_blocks as gemini_generate
    from ..processing.video_extractors import extract_keyframes

    api_key = api_key or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        console.print("  [yellow]⚠[/yellow] GOOGLE_API_KEY not set, cannot analyze video")
        return ""

    # Frame count proportional to duration: 2-8 frames
    num_frames = min(8, max(2, int(duration / 5)))
    target_words = int(duration * 2.5)

    # Extract keyframes
    keyframe_dir = (temp_dir or Path(".temp_veo_pipeline")) / f"keyframes_{video_path.stem}"
    keyframe_dir.mkdir(parents=True, exist_ok=True)

    try:
        keyframes = extract_keyframes(video_path, keyframe_dir, max_frames=num_frames)
    except Exception as e:
        console.print(f"  [yellow]⚠[/yellow] Keyframe extraction failed: {e}")
        return ""

    if not keyframes:
        console.print("  [yellow]⚠[/yellow] No keyframes extracted from video")
        return ""

    console.print(f"  [cyan]Analyzing {len(keyframes)} keyframes with Gemini Vision...[/cyan]")

    # Build content blocks for Gemini Vision
    content_blocks = []
    for i, kf in enumerate(keyframes):
        with open(kf, "rb") as f:
            image_bytes = f.read()

        ext = kf.suffix.lower()
        media_type = {
            ".png": "image/png", ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg", ".webp": "image/webp"
        }.get(ext, "image/jpeg")

        content_blocks.append(f"[Visual reference {i+1}/{len(keyframes)}]")
        content_blocks.append((image_bytes, media_type))

    storyline_section = f"\nStoryline: {storyline}\nIMPORTANT: The voiceover script MUST follow and advance this storyline." if storyline else ""

    content_blocks.append(f"""You're a top marketing copywriter. Analyze these {len(keyframes)} keyframes from a screen recording and write a voiceover script that makes people want to try this product NOW.

Context: {context if context else "This is a product/service screen recording for a marketing video."}
Tone: {tone}{storyline_section}
Video duration: {duration:.1f} seconds

Requirements:
1. Write like a human — natural, conversational, with personality and energy
2. Describe what's happening on screen but make it EXCITING, not just descriptive
3. Use humor, rhetorical questions, or relatable pain points to hook the viewer
4. You MUST write exactly {target_words} words — no fewer. The voiceover must fill {duration:.0f} seconds of video at ~2.5 words/sec. Count your words.
5. Every sentence MUST be complete — no cut-off phrases. Write for the EAR — short punchy sentences, conversational rhythm
6. Do NOT invent features that aren't visible in the keyframes
7. Use contrast: paint the painful "before" then the delightful "after"
8. Avoid clichés: no "revolutionary", "cutting-edge", "seamless", "robust"
9. Do NOT mention "keyframe", "frame", or "screenshot" in the script — the viewer doesn't know these exist. Describe what's on screen naturally.
{f"10. Align the script with the provided storyline — this scene is part of a larger narrative" if storyline else ""}

Return ONLY the voiceover script text, nothing else.""")

    try:
        script = gemini_generate(
            blocks=content_blocks,
            max_output_tokens=4096,
            api_key=api_key,
        )
        console.print(f"  [green]✓[/green] Vision script generated ({len(script.split())} words): \"{script[:60]}...\"")
        return script
    except Exception as e:
        console.print(f"  [yellow]⚠[/yellow] Vision analysis failed: {e}")
        return ""


def reorder_items_with_vision(
    ordered_items: List[Tuple[Path, str]],
    context: str = "",
    tone: str = "professional and engaging",
    storyline: str = "",
    pitch_script: str = "",
    api_key: Optional[str] = None,
) -> List[Tuple[Path, str]]:
    """
    Use Gemini Vision to analyze thumbnails and reorder items to match the pitch.

    If pitch_script is provided, images are ordered to visually support each
    sentence of the pitch in sequence. Otherwise falls back to generic
    pitch-deck ordering.

    Returns the reordered list. On any failure, returns the original order.
    """
    from ..ai.gemini_client import generate_with_content_blocks as gemini_generate
    import json
    from io import BytesIO
    from .screenshot_handler import get_video_thumbnail

    api_key = api_key or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        console.print("[yellow]⚠[/yellow] No API key for Vision reordering, keeping original order")
        return ordered_items

    ordering_mode = "pitch script" if pitch_script else "narrative flow"
    console.print(f"\n[bold cyan]AI Content Ordering: Ranking {len(ordered_items)} items to match {ordering_mode}...[/bold cyan]")

    try:
        content_blocks = []
        for i, (item_path, item_type) in enumerate(ordered_items):
            content_blocks.append(f"--- Item {i}: {item_path.name} ({item_type}) ---")

            if item_type == "video":
                thumbnail = get_video_thumbnail(item_path)
                buf = BytesIO()
                thumbnail.save(buf, format="PNG")
                image_bytes = buf.getvalue()
                media_type = "image/png"
            else:
                with open(item_path, "rb") as f:
                    image_bytes = f.read()
                ext = item_path.suffix.lower()
                media_type = {
                    ".png": "image/png", ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg", ".webp": "image/webp",
                    ".gif": "image/gif", ".bmp": "image/bmp",
                }.get(ext, "image/png")

            content_blocks.append((image_bytes, media_type))

        context_hint = f"\nContext: {context}" if context else ""

        if pitch_script:
            content_blocks.append(f"""You are ordering {len(ordered_items)} images to visually support a voiceover pitch script.

Each item is labelled with its index (0-based).{context_hint}

HERE IS THE PITCH SCRIPT (read it sentence by sentence):
\"\"\"{pitch_script}\"\"\"

Your job: order the images so each one appears on screen while the matching part of the pitch is spoken.
- First image = HOOK sentence (most attention-grabbing visual)
- Next images = PAIN POINT and SOLUTION sentences
- Later images = PROOF / DEMO sentences
- Last image = CTA sentence (call-to-action, signup, contact screen)

Match each image to the pitch sentence it best supports visually.
Never place two similar-looking images next to each other.

Return ONLY a JSON array of the original indices in your recommended order.
Example for 4 items: [2, 0, 3, 1]

Return ONLY the JSON array, no other text.""")
        else:
            storyline_hint = f"\nStoryline: {storyline}" if storyline else ""
            content_blocks.append(f"""You are a pitch deck expert assembling a marketing video from the {len(ordered_items)} content items shown above.
Each item is labelled with its index (0-based).{context_hint}
Tone: {tone}{storyline_hint}

Order these items as a COMPELLING MARKETING PITCH:
1. HOOK — Most attention-grabbing, visually striking image
2. PROBLEM — Pain point or chaos the audience faces
3. SOLUTION — Introduce the product/platform as the answer
4. PROOF — Features, dashboards, case studies, credibility signals
5. CTA — Contact, signup, or call-to-action screen

Rules:
- Never place two similar-looking images next to each other
- {"Follow the storyline: " + storyline if storyline else "Build a natural sales narrative"}

Return ONLY a JSON array of the original indices in your recommended order.
Example for 4 items: [2, 0, 3, 1]

Return ONLY the JSON array, no other text.""")

        raw = gemini_generate(
            blocks=content_blocks,
            max_output_tokens=200,
            api_key=api_key,
        )
        # Extract JSON array from response (handle markdown fences)
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        new_order = json.loads(raw)

        # Validate: must be a permutation of range(len(ordered_items))
        if sorted(new_order) != list(range(len(ordered_items))):
            console.print("[yellow]⚠[/yellow] Vision returned invalid ordering, keeping original order")
            return ordered_items

        reordered = [ordered_items[i] for i in new_order]
        if new_order != list(range(len(ordered_items))):
            console.print(f"[green]✓[/green] AI reordered content: {[ordered_items[i][0].name for i in new_order]}")
        else:
            console.print("[green]✓[/green] AI confirmed original order is optimal")
        return reordered

    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] Vision reordering failed ({e}), keeping original order")
        return ordered_items


def shortlist_scenes_with_vision(
    ordered_items: List[Tuple[Path, str]],
    max_scenes: int,
    context: str = "",
    tone: str = "professional and engaging",
    storyline: str = "",
    api_key: Optional[str] = None,
) -> List[Tuple[Path, str]]:
    """
    Use Claude Vision to select the best N images from a larger pool.

    When the user requests a short video (e.g. --script-duration 60) but has
    many images (e.g. 49), this function picks the most impactful, diverse
    subset that best tells the story.

    Returns a shortlisted list of (path, type) tuples. On failure, returns
    the first max_scenes items as a simple fallback.
    """
    from ..ai.gemini_client import generate_with_content_blocks as gemini_generate
    import json
    from io import BytesIO
    from .screenshot_handler import get_video_thumbnail

    total = len(ordered_items)
    if total <= max_scenes:
        return ordered_items

    # Video items are always kept — only images are shortlisted
    video_items = [(i, p, t) for i, (p, t) in enumerate(ordered_items) if t == "video"]
    image_items = [(i, p, t) for i, (p, t) in enumerate(ordered_items) if t == "image"]

    # Budget for images = max_scenes minus video slots
    image_budget = max(1, max_scenes - len(video_items))

    if len(image_items) <= image_budget:
        return ordered_items

    console.print(f"\n[bold cyan]Shortlisting: Selecting best {image_budget} images from {len(image_items)} (target: {max_scenes} scenes)...[/bold cyan]")

    api_key = api_key or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        console.print("[yellow]⚠[/yellow] No API key — taking first {image_budget} images")
        keep_indices = {idx for idx, _, _ in image_items[:image_budget]}
        keep_indices.update(idx for idx, _, _ in video_items)
        return [(p, t) for i, (p, t) in enumerate(ordered_items) if i in keep_indices]

    try:
        content_blocks = []
        for seq, (orig_idx, item_path, item_type) in enumerate(image_items):
            content_blocks.append(f"--- Image {seq} (file: {item_path.name}) ---")

            with open(item_path, "rb") as f:
                image_bytes = f.read()
            ext = item_path.suffix.lower()
            media_type = {
                ".png": "image/png", ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg", ".webp": "image/webp",
                ".gif": "image/gif", ".bmp": "image/bmp",
            }.get(ext, "image/png")

            content_blocks.append((image_bytes, media_type))

        storyline_hint = f"\nStoryline: {storyline}" if storyline else ""
        context_hint = f"\nContext: {context}" if context else ""

        content_blocks.append(f"""You are curating a marketing video from the {len(image_items)} images shown above.
You must select exactly {image_budget} images for the final video.{context_hint}
Tone: {tone}{storyline_hint}

Selection criteria:
- Pick the most visually diverse and impactful images (avoid near-duplicates)
- Prefer hero/banner images over plain text pages
- Ensure the selection covers a complete narrative: intro → value → features → proof → CTA
- If there are similar screenshots of the same page, pick only the best version
- Prioritize images that would grab attention in a marketing video

Return ONLY a JSON array of {image_budget} image indices (0-based, from the numbering above) in narrative order.
Example: [3, 0, 7, 12, 5]

Return ONLY the JSON array, no other text.""")

        raw = gemini_generate(
            blocks=content_blocks,
            max_output_tokens=300,
            api_key=api_key,
        )
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        selected_indices = json.loads(raw)

        # Validate
        if not isinstance(selected_indices, list) or len(selected_indices) != image_budget:
            raise ValueError(f"Expected {image_budget} indices, got {len(selected_indices) if isinstance(selected_indices, list) else 'non-list'}")
        if any(i < 0 or i >= len(image_items) for i in selected_indices):
            raise ValueError("Index out of range")

        # Map back to original ordered_items indices
        keep_orig_indices = set()
        for seq_idx in selected_indices:
            orig_idx = image_items[seq_idx][0]
            keep_orig_indices.add(orig_idx)
        # Always keep video items
        keep_orig_indices.update(idx for idx, _, _ in video_items)

        # Rebuild in the order Claude returned (for images), preserving video positions
        result = []
        selected_image_order = [image_items[si][0] for si in selected_indices]
        img_iter = iter(selected_image_order)

        # Interleave: walk original order, keep videos in place, replace images with selected order
        for orig_idx, (p, t) in enumerate(ordered_items):
            if t == "video":
                result.append((p, t))
            elif orig_idx in keep_orig_indices:
                result.append((p, t))

        # If the above doesn't preserve Claude's recommended order well enough,
        # rebuild purely from the selection order
        if len(result) != max_scenes:
            result = []
            for idx, _, _ in video_items:
                result.append(ordered_items[idx])
            for si in selected_indices:
                orig_idx = image_items[si][0]
                result.append(ordered_items[orig_idx])

        selected_names = [p.name for p, _ in result]
        console.print(f"[green]✓[/green] Selected {len(result)} scenes: {selected_names}")
        return result

    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] Vision shortlisting failed ({e}), taking first {image_budget} images")
        keep_indices = {idx for idx, _, _ in image_items[:image_budget]}
        keep_indices.update(idx for idx, _, _ in video_items)
        return [(p, t) for i, (p, t) in enumerate(ordered_items) if i in keep_indices]


def analyze_image_for_script(
    image_path: Path,
    context: str = "",
    tone: str = "professional and engaging",
    api_key: Optional[str] = None
) -> str:
    """
    Analyze an image with Claude Vision and generate a voiceover script.
    (Legacy function - use analyze_image_for_script_and_text for OCR support)
    """
    script, _ = analyze_image_for_script_and_text(image_path, context, tone, api_key)
    return script


def generate_motion_prompt(image_path: Path, script: str) -> str:
    """
    Generate a motion prompt for Veo based on the image and script.
    This tells Veo how to animate the image.
    """
    # Analyze script for motion cues
    script_lower = script.lower()

    motion_elements = []

    # Add base cinematic quality
    motion_elements.append("smooth cinematic camera movement")

    # Detect content type and add appropriate motion
    if any(word in script_lower for word in ["dashboard", "data", "chart", "graph", "analytics"]):
        motion_elements.append("subtle zoom into key data points")
        motion_elements.append("gentle pan across the interface")
    elif any(word in script_lower for word in ["button", "click", "feature", "tool"]):
        motion_elements.append("cursor movement highlighting features")
        motion_elements.append("zoom into interactive elements")
    elif any(word in script_lower for word in ["team", "people", "user", "customer"]):
        motion_elements.append("subtle motion on faces")
        motion_elements.append("natural micro-expressions")
    elif any(word in script_lower for word in ["product", "design", "interface", "app"]):
        motion_elements.append("smooth 3D perspective shift")
        motion_elements.append("professional product showcase motion")
    else:
        motion_elements.append("gentle zoom and pan")
        motion_elements.append("professional presentation style")

    # Add quality modifiers
    motion_elements.append("high production value")
    motion_elements.append("8K quality render")

    return ", ".join(motion_elements)


def detect_text_regions_with_ai(
    image_path: Path,
    api_key: Optional[str] = None
) -> List[dict]:
    """
    Use Claude Vision to detect text regions and their bounding boxes.
    Returns list of {"text": str, "x": int, "y": int, "width": int, "height": int}
    """
    from ..ai.gemini_client import generate_with_images
    import json

    api_key = api_key or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return []

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    ext = image_path.suffix.lower()
    media_type = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(ext, "image/png")

    prompt = """Analyze this image and identify ALL text regions with their approximate bounding boxes.

For each text element, provide:
- text: the exact text content
- x: approximate x position (0-100, percentage from left)
- y: approximate y position (0-100, percentage from top)
- width: approximate width (0-100, percentage of image width)
- height: approximate height (0-100, percentage of image height)

Return ONLY a JSON array like this:
[
  {"text": "Dashboard", "x": 5, "y": 2, "width": 15, "height": 5},
  {"text": "Settings", "x": 80, "y": 2, "width": 10, "height": 5}
]

Return ONLY the JSON array, no other text."""

    try:
        result_text = generate_with_images(
            prompt=prompt,
            images=[(image_bytes, media_type)],
            max_output_tokens=1000,
            api_key=api_key,
        )
        # Parse JSON
        if result_text.startswith("["):
            return json.loads(result_text)
    except Exception as e:
        console.print(f"[dim]Text detection failed: {e}[/dim]")

    return []


def overlay_original_text_on_video(
    video_path: Path,
    original_image_path: Path,
    text_regions: List[dict],
    output_path: Path
) -> Path:
    """
    Overlay original image's text regions onto the Veo video.
    This preserves the exact original text while keeping Veo's motion.

    Uses heavy feathering to prevent flickering and blend smoothly.
    """
    import subprocess
    from PIL import Image, ImageDraw, ImageFilter
    import shutil

    if not text_regions:
        shutil.copy(video_path, output_path)
        return output_path

    # Get video dimensions using ffprobe
    try:
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0",
            str(video_path)
        ]
        result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            video_width, video_height = map(int, result.stdout.strip().split(','))
        else:
            video_width, video_height = 1920, 1080
    except Exception:
        video_width, video_height = 1920, 1080

    # Load original image
    original_img = Image.open(original_image_path).convert("RGBA")
    img_width, img_height = original_img.size

    # Scale original image to match video resolution
    if (img_width, img_height) != (video_width, video_height):
        original_img = original_img.resize((video_width, video_height), Image.Resampling.LANCZOS)
        img_width, img_height = video_width, video_height

    # Create a mask with heavily feathered edges to prevent flickering
    # Use a larger canvas for the blur, then crop back
    blur_radius = 15  # Heavy blur for smooth blending
    padding_for_blur = blur_radius * 2

    mask = Image.new("L", (img_width, img_height), 0)
    draw = ImageDraw.Draw(mask)

    for region in text_regions:
        # Convert percentage to pixels
        x = int(region.get("x", 0) * img_width / 100)
        y = int(region.get("y", 0) * img_height / 100)
        w = int(region.get("width", 10) * img_width / 100)
        h = int(region.get("height", 5) * img_height / 100)

        # Add generous padding around text regions
        padding = 12
        x = max(0, x - padding)
        y = max(0, y - padding)
        w = min(img_width - x, w + 2 * padding)
        h = min(img_height - y, h + 2 * padding)

        # Draw white rectangle on mask (white = visible)
        draw.rectangle([x, y, x + w, y + h], fill=255)

    # Apply heavy Gaussian blur for smooth feathered edges (prevents flickering)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=blur_radius))

    # Boost the center opacity while keeping soft edges
    # This ensures text is fully opaque in center but blends at edges
    import numpy as np
    mask_array = np.array(mask, dtype=np.float32)
    # Apply sigmoid-like curve to sharpen center while keeping soft edges
    mask_array = np.clip(mask_array * 1.5, 0, 255).astype(np.uint8)
    mask = Image.fromarray(mask_array, mode="L")

    # Create text overlay image
    text_overlay = original_img.copy()
    text_overlay.putalpha(mask)

    temp_overlay = output_path.parent / "temp_text_overlay.png"
    text_overlay.save(temp_overlay, "PNG")

    # Use FFmpeg with proper pixel format to avoid flickering
    # format=rgb ensures consistent color handling
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(temp_overlay),
        "-filter_complex",
        f"[1:v]scale={video_width}:{video_height}:flags=lanczos,format=rgba[ovr];"
        f"[0:v]format=rgba[base];"
        f"[base][ovr]overlay=0:0:format=auto,format=yuv420p",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-c:a", "copy",
        str(output_path)
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            console.print(f"[yellow]Text overlay failed: {result.stderr[:200]}[/yellow]")
            shutil.copy(video_path, output_path)
    except Exception as e:
        console.print(f"[yellow]Text overlay error: {e}[/yellow]")
        shutil.copy(video_path, output_path)

    # Cleanup
    if temp_overlay.exists():
        temp_overlay.unlink()

    return output_path


def _polish_chunk(
    chunk: str,
    context: str,
    tone: str,
    storyline: str,
    position_context: str,
    word_count: int,
    api_key: str,
    video_frames: Optional[List[Path]] = None,
) -> str:
    """Polish a single chunk of transcript, optionally with video frame context."""
    from ..ai.gemini_client import generate_text, generate_with_content_blocks

    chunk_words = len(chunk.split())
    expanding = word_count > chunk_words * 1.2  # target is significantly more than source

    if expanding:
        video_seconds = int(word_count / 2.5)
        expand_instruction = (
            f"CRITICAL: The original transcript is only {chunk_words} words but this voiceover must fill {video_seconds} seconds of video "
            f"(~{word_count} words at 2.5 words/sec). The video will play at its original speed and the voiceover MUST cover most of it. "
            f"EXPAND to ~{word_count} words by: narrating what's visible on screen, elaborating on each point with context and examples, "
            f"adding transitions between topics, and describing UI elements and actions shown in the video. "
            f"Do NOT pad with filler — every added sentence must be substantive."
        )
    else:
        expand_instruction = f"MATCH the original length — output MUST be ~{word_count} words. Do NOT shorten or summarize. Do NOT cut content."

    frames_instruction = ""
    if video_frames:
        frames_instruction = (
            "\n10. Use the video frames above as visual context — describe what's happening on screen "
            "to make the voiceover match the visuals. Reference UI elements, actions, and changes you see."
            "\n11. Do NOT mention 'keyframe', 'frame', or 'screenshot' in the script — the viewer doesn't know these exist."
        )

    prompt_text = f"""You're a top marketing copywriter. Rewrite this raw video transcript into a polished, engaging voiceover script that grabs attention.

RAW TRANSCRIPT ({chunk_words} words — your output MUST be ~{word_count} words):
{chunk}

{f"Context: {context}" if context else ""}{f"{chr(10)}Storyline: {storyline}" if storyline else ""}{position_context}

Rules:
1. EVERY point, fact, feature, name, number, and detail from the original MUST appear — do NOT drop or skip anything
2. Remove filler words (um, uh, like, you know, so, basically, right)
3. Fix grammar and awkward phrasing
4. Make it sound {tone} — but also natural, like a real person talking, not a corporate script
5. Add personality: humor, wit, rhetorical questions, relatable moments where they fit naturally
6. {expand_instruction}
7. Do NOT add introductions, conclusions, or calls to action that weren't in the original
8. Preserve the original order of topics — do NOT rearrange
{f"9. Align the polished script with the provided storyline — ensure narrative coherence" if storyline else ""}{frames_instruction}
Return ONLY the polished script, nothing else."""

    # Use multimodal API when video frames are available
    if video_frames:
        content_blocks = []
        for i, frame_path in enumerate(video_frames):
            if frame_path.exists():
                with open(frame_path, "rb") as f:
                    image_bytes = f.read()
                ext = frame_path.suffix.lower()
                media_type = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}.get(ext, "image/jpeg")
                content_blocks.append(f"[Visual reference {i+1}/{len(video_frames)}]")
                content_blocks.append((image_bytes, media_type))
        content_blocks.append(prompt_text)
        return generate_with_content_blocks(
            blocks=content_blocks,
            max_output_tokens=8192,
            api_key=api_key,
        )

    return generate_text(
        prompt=prompt_text,
        max_output_tokens=8192,
        api_key=api_key,
    )


def polish_transcript(
    raw_transcript: str,
    context: str = "",
    tone: str = "professional and engaging",
    storyline: str = "",
    scene_number: Optional[int] = None,
    total_scenes: Optional[int] = None,
    preceding_script: Optional[str] = None,
    following_topic: Optional[str] = None,
    api_key: Optional[str] = None,
    target_duration: Optional[float] = None,
    video_frames: Optional[List[Path]] = None,
) -> str:
    """
    Polish a raw video transcript into a clean voiceover script.
    Keeps the same meaning and key points but removes filler words,
    fixes grammar, and makes it sound professional.

    For long transcripts (>400 words), splits into chunks and polishes
    each separately to avoid truncation.
    """
    api_key = api_key or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return raw_transcript

    # Build scene position context
    position_context = ""
    if scene_number is not None and total_scenes is not None:
        position_context = f"\nThis is scene {scene_number} of {total_scenes} in a multi-scene video."
        if preceding_script:
            position_context += f"\nThe PREVIOUS scene's script ends with: \"{preceding_script[-150:]}\""
            position_context += "\nEnsure your polished script flows naturally from where the previous scene left off — avoid repeating what was just said."
        if following_topic:
            position_context += f"\nThe NEXT scene will cover: \"{following_topic[:150]}\""
            position_context += "\nEnd in a way that leads naturally into the next topic."

    words = raw_transcript.split()
    total_words = len(words)

    # If target_duration is provided, compute target word count (~2.5 words/sec for TTS)
    # so the voiceover fills the video duration instead of speeding up the video
    target_words = total_words
    if target_duration and target_duration > 0:
        duration_based_words = int(target_duration * 2.5)
        if duration_based_words > total_words:
            console.print(f"  [dim]Expanding script from ~{total_words} to ~{duration_based_words} words to fill {target_duration:.0f}s video[/dim]")
            target_words = duration_based_words

    # Short transcript — polish in one call
    if total_words <= 400:
        try:
            return _polish_chunk(
                raw_transcript, context, tone, storyline,
                position_context, target_words, api_key,
                video_frames=video_frames,
            )
        except Exception as e:
            console.print(f"  [yellow]Polish failed, using raw transcript: {e}[/yellow]")
            return raw_transcript

    # Long transcript — split into ~300-word chunks at sentence boundaries
    console.print(f"  [dim]Long transcript ({total_words} words) — polishing in chunks to avoid truncation[/dim]")
    sentences = re.split(r'(?<=[.!?])\s+', raw_transcript)
    chunks = []
    current_chunk = []
    current_words = 0

    for sentence in sentences:
        sw = len(sentence.split())
        if current_words + sw > 350 and current_chunk:
            chunks.append(" ".join(current_chunk))
            current_chunk = [sentence]
            current_words = sw
        else:
            current_chunk.append(sentence)
            current_words += sw

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    # Scale factor for expanding chunks proportionally when target_words > total_words
    word_scale = target_words / total_words if total_words > 0 else 1.0

    # Distribute video frames across chunks proportionally
    chunk_frames_list = [None] * len(chunks)
    if video_frames:
        frames_per_chunk = max(1, len(video_frames) // len(chunks))
        for i in range(len(chunks)):
            start = i * frames_per_chunk
            end = start + frames_per_chunk if i < len(chunks) - 1 else len(video_frames)
            chunk_frames_list[i] = video_frames[start:end] if start < len(video_frames) else None

    # Polish each chunk
    polished_parts = []
    for i, chunk in enumerate(chunks):
        chunk_words = len(chunk.split())
        chunk_target = int(chunk_words * word_scale)
        chunk_position = position_context
        if i > 0 and polished_parts:
            # Give context from previous chunk
            chunk_position += f"\nPrevious section ended with: \"{polished_parts[-1][-150:]}\""
        try:
            polished = _polish_chunk(
                chunk, context, tone, storyline,
                chunk_position, chunk_target, api_key,
                video_frames=chunk_frames_list[i],
            )
            polished_parts.append(polished)
            console.print(f"  [dim]Chunk {i+1}/{len(chunks)}: {chunk_words}w → {len(polished.split())}w[/dim]")
        except Exception as e:
            console.print(f"  [yellow]Chunk {i+1} failed, using raw: {e}[/yellow]")
            polished_parts.append(chunk)

    result = " ".join(polished_parts)
    console.print(f"  [dim]Polish complete: {total_words}w → {len(result.split())}w[/dim]")
    return result


def estimate_speech_duration(text: str, words_per_minute: int = 150) -> float:
    """
    Estimate how long it will take to speak the text.
    Average speaking rate is ~150 words per minute.
    Always returns 8 — Veo produces better motion with 8-second clips.
    """
    return 8


def estimate_script_duration(text: str, words_per_minute: int = 150) -> float:
    """
    Estimate actual spoken duration of the script (unclamped).
    Used for logging/comparison with Veo video duration.
    """
    word_count = len(text.split())
    return (word_count / words_per_minute) * 60


def generate_veo_video(
    image_path: Path,
    output_path: Path,
    motion_prompt: str,
    script_text: str = "",
    api_key: Optional[str] = None,
    last_image_path: Optional[Path] = None
) -> Path:
    """
    Generate video from image using Veo 3.1.
    Duration is estimated from script length for better sync.
    """
    from ..ai.veo_generator import generate_video_veo

    # Estimate duration based on script length
    if script_text:
        duration = int(estimate_speech_duration(script_text))
    else:
        duration = 8  # Default Veo duration

    console.print(f"[dim]Veo video duration: {duration}s (based on script length)[/dim]")

    return generate_video_veo(
        prompt=motion_prompt,
        output_path=output_path,
        image_path=image_path,
        last_image_path=last_image_path,
        duration=duration,
        aspect_ratio="16:9",
        resolution="1080p",
        model="veo-3.1-generate-preview",  # Best quality
        api_key=api_key,
        enable_audio=True  # Keep sound effects; any accidental speech is buried under TTS voiceover
    )


def enhance_script_for_tts(script: str, api_key: Optional[str] = None) -> str:
    """
    Add delivery cues to a script for natural-sounding TTS.
    Does NOT add new words — only reformats existing text with pauses and emphasis.
    """
    import re

    if not script or not script.strip():
        return script

    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', script.strip()) if s.strip()]
    if not sentences:
        return script

    enhanced = []
    for i, sentence in enumerate(sentences):
        # Add a pause dash before the last sentence (CTA) for dramatic beat
        if i == len(sentences) - 1 and len(sentences) > 2:
            sentence = "— " + sentence

        # Add ellipsis pause after the first sentence (hook lands, then beat)
        if i == 0 and len(sentences) > 1:
            # Replace the ending punctuation with ...  then restore it
            if sentence.endswith('.'):
                sentence = sentence[:-1] + "..."
            elif sentence.endswith('!'):
                sentence = sentence[:-1] + "...!"

        enhanced.append(sentence)

    return " ".join(enhanced)


def generate_voiceover(
    script: str,
    output_path: Path,
    engine: str = "elevenlabs",
    voice: str = "Smritika",
    api_key: Optional[str] = None,
    speed: float = 1.0,
) -> Tuple[Path, float]:
    """
    Generate voiceover for the script.

    Args:
        speed: Speech rate multiplier (1.0 = normal, 1.2 = 20% faster)

    Returns:
        Tuple of (audio_path, duration)
    """
    from ..ai.tts_engine import generate_tts_elevenlabs, generate_tts_edge

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if engine == "elevenlabs":
        duration = generate_tts_elevenlabs(script, output_path, voice, api_key, speed=speed)
    else:
        import asyncio
        duration = asyncio.run(generate_tts_edge(script, output_path, voice, speed=speed))

    return output_path, duration


def combine_video_with_audio(
    video_path: Path,
    audio_path: Path,
    output_path: Path,
    audio_volume: float = 5.0,  # Boosted voice volume
    original_audio_volume: float = 0.3,  # Veo sound effects mixed underneath voiceover
    no_speed_adjust: bool = False,  # True = keep video at original speed, just overlay voiceover
) -> Path:
    """
    Combine video with voiceover audio, preserving the original video audio.
    The original video audio is mixed at a lower volume underneath the voiceover.

    no_speed_adjust: if True, video won't be sped up. If voiceover is shorter,
    video plays at original speed with the rest unnarrated. If voiceover is
    longer, video is slowed down to match.
    """
    import subprocess
    import shutil
    from moviepy import VideoFileClip, AudioFileClip

    video = VideoFileClip(str(video_path))
    audio = AudioFileClip(str(audio_path))

    console.print(f"[dim]Video duration: {video.duration:.2f}s, Audio duration: {audio.duration:.2f}s[/dim]")

    video_duration = video.duration
    audio_duration = audio.duration
    has_original_audio = video.audio is not None

    video.close()
    audio.close()

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Calculate speed factor
    speed_factor = video_duration / audio_duration

    # no_speed_adjust: don't speed UP the video (voiceover short → video plays at original pace)
    # but DO slow DOWN if voiceover is longer (speed_factor < 1 means video needs to stretch)
    if no_speed_adjust and speed_factor > 1.0:
        console.print(f"[dim]Keeping video at original speed (voiceover covers {audio_duration:.0f}s of {video_duration:.0f}s)[/dim]")
        speed_factor = 1.0

    if speed_factor != 1.0 and abs(video_duration - audio_duration) > 0.5:
        console.print(f"[dim]Adjusting video speed by {speed_factor:.2f}x using FFmpeg[/dim]")

        temp_video = output_path.parent / f"temp_speed_{output_path.name}"
        pts_factor = 1 / speed_factor

        # Adjust video speed, keeping original audio (slowed to match)
        # atempo adjusts audio speed to match the video speed change
        if has_original_audio:
            # atempo range is 0.5-2.0, chain for values outside
            atempo_filters = []
            remaining = speed_factor  # same factor to slow audio proportionally
            while remaining > 2.0:
                atempo_filters.append("atempo=2.0")
                remaining /= 2.0
            while remaining < 0.5:
                atempo_filters.append("atempo=0.5")
                remaining *= 2.0
            atempo_filters.append(f"atempo={remaining:.4f}")
            atempo_str = ",".join(atempo_filters)

            cmd = [
                "ffmpeg", "-y", "-i", str(video_path),
                "-filter:v", f"setpts={pts_factor}*PTS",
                "-filter:a", atempo_str,
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "18",
                "-r", "30",
                "-c:a", "aac",
                str(temp_video)
            ]
        else:
            cmd = [
                "ffmpeg", "-y", "-i", str(video_path),
                "-filter:v", f"setpts={pts_factor}*PTS",
                "-an",
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "18",
                "-r", "30",
                str(temp_video)
            ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                console.print(f"[yellow]FFmpeg speed adjustment failed, using simple method[/yellow]")
                temp_video = video_path
        except Exception as e:
            console.print(f"[yellow]FFmpeg error: {e}, using simple method[/yellow]")
            temp_video = video_path
    else:
        temp_video = video_path

    # Mix original video audio with voiceover
    if has_original_audio and original_audio_volume >= 1.0:
        # Preserve system audio mode (screen recordings):
        # Use sidechain compression to duck system audio when voiceover is speaking.
        # System audio plays at full volume during silent parts of voiceover,
        # and automatically lowers when voice is detected.
        console.print(f"[dim]Ducking system audio under voiceover (sidechain compression)[/dim]")
        cmd = [
            "ffmpeg", "-y",
            "-i", str(temp_video),
            "-i", str(audio_path),
            "-filter_complex",
            # voice: boost voiceover volume
            f"[1:a]volume={audio_volume}[voice];"
            # sidechaincompress: use voiceover to duck system audio
            # threshold=0.008: triggers ducking at low voice levels
            # ratio=6: strong ducking (system audio drops to ~1/6 when voice is active)
            # attack=100: duck quickly when voice starts (100ms)
            # release=800: bring system audio back smoothly after voice stops (800ms)
            f"[0:a][voice]sidechaincompress=threshold=0.008:ratio=6:attack=100:release=800:level_in=1:level_sc=1[ducked];"
            # Mix ducked system audio + voiceover
            f"[ducked][voice]amix=inputs=2:duration=longest:dropout_transition=2:normalize=0[aout]",
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            str(output_path)
        ]
    elif has_original_audio:
        # Normal mode: original audio quiet, voiceover loud (Veo animations etc.)
        cmd = [
            "ffmpeg", "-y",
            "-i", str(temp_video),
            "-i", str(audio_path),
            "-filter_complex",
            f"[0:a]volume={original_audio_volume}[orig];"
            f"[1:a]volume={audio_volume}[voice];"
            f"[orig][voice]amix=inputs=2:duration=longest:dropout_transition=2[aout]",
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            str(output_path)
        ]
    else:
        # No original audio, just add voiceover
        # Pad voiceover with silence to match video duration so the full video is preserved
        adjusted_video_dur = video_duration / speed_factor if speed_factor > 1 else video_duration
        cmd = [
            "ffmpeg", "-y",
            "-i", str(temp_video),
            "-i", str(audio_path),
            "-filter_complex",
            f"[1:a]volume={audio_volume},apad=whole_dur={adjusted_video_dur:.2f}[voice]",
            "-map", "0:v",
            "-map", "[voice]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(output_path)
        ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            console.print(f"[red]FFmpeg merge failed: {result.stderr[:200]}[/red]")
            raise ValueError("Failed to merge video and audio")
    except subprocess.TimeoutExpired:
        raise ValueError("FFmpeg merge timed out")

    # Cleanup temp file
    if temp_video != video_path and Path(temp_video).exists():
        Path(temp_video).unlink()

    console.print(f"[green]✓ Combined video with audio: {output_path.name}[/green]")
    return output_path


def add_background_music_to_file(
    video_path: Path,
    music_path: Path,
    output_path: Path,
    music_volume: float = 0.03
) -> Path:
    """
    Add background music to video file (path-based version for veo_pipeline).
    This version writes a new file, unlike audio_utils.add_background_music which modifies a clip.
    """
    from moviepy import VideoFileClip, AudioFileClip, CompositeAudioClip, concatenate_audioclips
    from moviepy.audio.fx import AudioFadeOut

    video = VideoFileClip(str(video_path))
    music = AudioFileClip(str(music_path))

    # Loop music if needed
    if music.duration < video.duration:
        loops_needed = int(video.duration / music.duration) + 1
        music = concatenate_audioclips([music] * loops_needed)

    # Trim and adjust volume
    music = music.subclipped(0, video.duration)
    music = music.with_volume_scaled(music_volume)
    music = music.with_effects([AudioFadeOut(2.0)])

    # Mix with existing audio
    if video.audio:
        final_audio = CompositeAudioClip([video.audio, music])
    else:
        final_audio = music

    final = video.with_audio(final_audio)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    final.write_videofile(
        str(output_path),
        fps=30,
        codec='libx264',
        audio_codec='aac',
        preset='medium',
        threads=4
    )

    video.close()
    music.close()

    return output_path


def _extract_final_audio(video_path: Path, audio_output_path: Path) -> Path:
    """Extract audio from the final video as a high-quality MP3."""
    import subprocess

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vn", "-acodec", "libmp3lame",
        "-ar", "44100", "-ac", "2", "-b:a", "192k",
        str(audio_output_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Audio extraction failed: {result.stderr[-300:]}")

    console.print(f"[green]✓ Audio extracted:[/green] {audio_output_path.name}")
    return audio_output_path


def _save_pipeline_manifest(
    output_video: Path,
    pre_music_video: Optional[Path],
    music_path: Optional[Path],
    voice_volume: float,
    music_volume: float,
    voice_speed: float,
):
    """Save JSON manifest alongside output for post-processing.

    Records paths to intermediate files so `cli.py post` can remix
    voice/music volumes without re-running the full pipeline.
    """
    import json

    manifest_path = output_video.with_name(
        output_video.stem + "_manifest.json"
    )
    manifest = {
        "output_video": str(output_video),
        "pre_music_video": str(pre_music_video) if pre_music_video else None,
        "music_file": str(music_path) if music_path else None,
        "voice_volume": voice_volume,
        "music_volume": music_volume,
        "voice_speed": voice_speed,
    }
    try:
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        console.print(f"[green]✓ Manifest saved:[/green] {manifest_path.name}")
    except OSError as e:
        console.print(f"[yellow]⚠ Could not save manifest: {e}[/yellow]")


async def _generate_veo_scene(
    scene: SceneData,
    index: int,
    temp_dir: Path,
    semaphore: asyncio.Semaphore,
    next_image_path: Optional[Path] = None,
    next_extracted_text: str = "",
    storyline: str = "",
    scene_duration: int = 4,
) -> None:
    """Generate a single Veo scene, respecting the concurrency semaphore.
    For paired scenes (scene.last_image_path set), Veo transitions between
    first and last image. The 8s output is then sped up to ~3s."""
    async with semaphore:
        # Use the scene's own last_image_path (from pairing) if available,
        # otherwise fall back to next_image_path (legacy behavior)
        effective_last_image = scene.last_image_path or next_image_path
        effective_last_text = scene.last_extracted_text or next_extracted_text

        if effective_last_image:
            console.print(f"  [cyan]⏳[/cyan] Starting Veo: {scene.image_path.name} → {effective_last_image.name} (paired transition)...")
        else:
            console.print(f"  [cyan]⏳[/cyan] Starting Veo: {scene.image_path.name} (single image)...")

        has_text = scene.extracted_text and scene.extracted_text.strip()

        if not has_text:
            console.print(f"  [dim]No OCR text for {scene.image_path.name} — Veo will animate without text constraints[/dim]")

        # Build last frame text section if available
        last_frame_section = ""
        if effective_last_image and effective_last_text and effective_last_text.strip():
            last_frame_section = f"""

LAST FRAME TEXT (must appear exactly as shown at the end of the video):
{effective_last_text.strip()}"""

        storyline_section = ""

        # Build text preservation block only if OCR found text
        if has_text:
            text_block = f"""
CRITICAL - TEXT PRESERVATION:
All text in both frames MUST remain exactly as shown. Do not alter, rephrase, remove, or distort any text.

FIRST FRAME TEXT (must appear exactly as shown at the start of the video):
{scene.extracted_text.strip()}{last_frame_section}

Create a cinematic video with:
- Very subtle and slow zoom effects
- Minimal animation near text areas - keep text regions calm and stable
- Gentle background animations only
- Text must remain static, sharp, and easy to read

IMPORTANT: Keep animations subtle where text is present. Prioritize readability. Never modify any text."""
        else:
            text_block = """
Create a cinematic video with:
- Smooth camera movements: zoom, pan, drift
- Dynamic but professional motion
- High production value cinematography"""

        video_prompt = f"""{scene.script}
{storyline_section}{text_block}

AUDIO: SFX only. No voice. No music. No narration. No speech. Generate only SFX — clicks, whooshes, swooshes, UI taps, digital bleeps, ambient hums. Voiceover and music are added in post-production."""

        # Save prompt to file for review
        prompt_file = temp_dir / f"prompt_{index:03d}_{scene.image_path.stem}.txt"
        prompt_file.write_text(video_prompt)
        console.print(f"  [dim]Prompt saved: {prompt_file}[/dim]")

        video_output = temp_dir / f"veo_scene_{index:03d}.mp4"

        try:
            raw_video_output = temp_dir / f"veo_raw_{index:03d}.mp4"
            await asyncio.to_thread(
                generate_veo_video,
                scene.image_path,
                raw_video_output,
                video_prompt,
                script_text=scene.script,
                last_image_path=effective_last_image,
            )

            # Speed up scenes based on --scene-duration (8s Veo → target duration)
            sd = max(2, min(8, scene_duration))
            if sd < 8:
                import subprocess
                sped_output = temp_dir / f"veo_sped_{index:03d}.mp4"
                speed_factor = round(8 / sd, 2)
                subprocess.run(
                    ["ffmpeg", "-y", "-i", str(raw_video_output),
                     "-filter:v", f"setpts={1/speed_factor}*PTS",
                     "-filter:a", f"atempo={min(speed_factor, 2.0)}",
                     "-c:v", "libx264", "-preset", "fast",
                     "-c:a", "aac",
                     str(sped_output)],
                    capture_output=True, text=True, timeout=120
                )
                if sped_output.exists() and sped_output.stat().st_size > 0:
                    sped_output.rename(video_output)
                    scene.duration = sd
                    console.print(f"  [green]✓[/green] Generated + sped up ({speed_factor}x): {video_output.name} ({sd}s)")
                else:
                    raw_video_output.rename(video_output)
                    console.print(f"  [yellow]⚠[/yellow] Speedup failed, using 8s original: {video_output.name}")
            else:
                raw_video_output.rename(video_output)
                console.print(f"  [green]✓[/green] Generated: {video_output.name}")

            scene.video_path = video_output
        except Exception as e:
            console.print(f"  [yellow]⚠[/yellow] Veo failed for {scene.image_path.name}, using static image: {e}")
            from moviepy import ImageClip
            clip = ImageClip(str(scene.image_path)).with_duration(8)
            clip.write_videofile(str(video_output), fps=30, codec='libx264')
            scene.video_path = video_output
            clip.close()


async def _generate_veo_scenes_parallel(
    scenes: List[SceneData],
    temp_dir: Path,
    max_concurrent: int = 3,
    storyline: str = "",
    scene_duration: int = 4,
) -> None:
    """Generate all Veo scenes in parallel with a concurrency cap.
    Paired scenes already have last_image_path set from the pairing step."""
    semaphore = asyncio.Semaphore(max_concurrent)
    tasks = [
        _generate_veo_scene(
            scene, i, temp_dir, semaphore,
            storyline=storyline,
            scene_duration=scene_duration,
        )
        for i, scene in enumerate(scenes)
    ]
    await asyncio.gather(*tasks)


def create_marketing_video_veo(
    input_path: Path,
    output_path: Path,
    tts_engine: str = "elevenlabs",
    voice: str = "Smritika",
    music_path: Optional[Path] = None,
    music_volume: float = 0.03,
    voice_volume: float = 5.0,
    context: str = "",
    tone: str = "professional and engaging",
    resolution: str = "1080p",
    max_concurrent_veo: int = 3,
    voice_speed: float = 1.0,
    storyline: str = "",
    script_duration: int = 60,
    scene_duration: int = 4,
    style: str = "marketing",
    ai_order: bool = True,
    generate_intro: bool = False,
    generate_outro: bool = False,
    product: str = "",
    intro_image_path: Optional[Path] = None,
    outro_image_path: Optional[Path] = None,
    intro_veo_prompt: str = "",
    outro_veo_prompt: str = "",
    no_voiceover_files: Optional[List[str]] = None,
) -> Path:
    """
    Create a complete marketing video using Veo 3.1.

    Pipeline:
    1. Analyze images with Claude Vision
    2. Generate scripts for each image
    3. Generate Veo videos from images (parallel with concurrency cap)
    4. Add voiceovers
    4.5. Generate intro/outro bookend clips (if enabled)
    5. Add background music
    6. Combine into final video

    Args:
        input_path: Directory with images or single image
        output_path: Where to save final video
        tts_engine: "elevenlabs" or "edge"
        voice: Voice name (e.g., "Smritika")
        music_path: Optional background music file
        music_volume: Background music volume (0.0-1.0)
        voice_volume: Voiceover volume multiplier
        context: Context about the product/service
        tone: Desired tone for scripts
        resolution: Video resolution
        max_concurrent_veo: Max parallel Veo API calls (default: 3)
        voice_speed: Speech rate multiplier (1.0 = normal, 1.2 = 20% faster)
        storyline: Narrative storyline to guide scripts and animation
        generate_intro: Generate a branded intro frame
        generate_outro: Generate a branded outro/CTA frame
        product: Product name for bookend text

    Returns:
        Path to final video
    """
    import subprocess
    from moviepy import VideoFileClip, concatenate_videoclips
    from .screenshot_handler import extract_pptx_slides, PPTX_EXTENSIONS, VIDEO_EXTENSIONS

    IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp'}

    # Get image and video files
    input_path = Path(input_path)
    # ordered_items: list of (path, "image"|"video") in filename order
    ordered_items: List[Tuple[Path, str]] = []

    if input_path.is_file():
        if input_path.suffix.lower() in PPTX_EXTENSIONS:
            console.print(f"[cyan]Extracting slides from {input_path.name}...[/cyan]")
            temp_slides_dir = Path(".temp_veo_slides")
            temp_slides_dir.mkdir(exist_ok=True)
            slides = extract_pptx_slides(input_path, temp_slides_dir)
            ordered_items.extend((s, "image") for s in slides)
            console.print(f"[green]✓ Extracted {len(slides)} slides[/green]")
        elif input_path.suffix.lower() in VIDEO_EXTENSIONS:
            ordered_items.append((input_path, "video"))
        else:
            ordered_items.append((input_path, "image"))
    else:
        # Collect all supported files from directory
        all_files = sorted([
            f for f in input_path.iterdir()
            if not f.name.startswith('.')
        ])

        temp_slides_dir = None
        for f in all_files:
            if f.suffix.lower() in PPTX_EXTENSIONS:
                if temp_slides_dir is None:
                    temp_slides_dir = Path(".temp_veo_slides")
                    temp_slides_dir.mkdir(exist_ok=True)
                console.print(f"[cyan]Extracting slides from {f.name}...[/cyan]")
                slides = extract_pptx_slides(f, temp_slides_dir)
                ordered_items.extend((s, "image") for s in slides)
                console.print(f"[green]✓ Extracted {len(slides)} slides[/green]")
            elif f.suffix.lower() in IMAGE_EXTENSIONS:
                ordered_items.append((f, "image"))
            elif f.suffix.lower() in VIDEO_EXTENSIONS:
                # Skip mic-recording files — they're companion tracks, not standalone videos
                if f.name.startswith("mic-recording-"):
                    console.print(f"[dim]Skipping mic track: {f.name} (will be used with its screen recording)[/dim]")
                    continue
                ordered_items.append((f, "video"))

    if not ordered_items:
        raise ValueError(f"No images, PPTX, or video files found in {input_path}")

    # Calculate scene budget
    sd = max(2, min(8, scene_duration))  # clamp 2-8
    speed_factor = round(8 / sd, 2) if sd < 8 else 1.0
    num_pairs = max(1, script_duration // sd)
    max_images = num_pairs * 2  # 2 images per Veo call

    # Pitch is generated later once we know exact scene count
    pitch_script = ""

    # AI-powered reordering — rank images using storyline (pitch comes after scene count is known)
    if ai_order and len(ordered_items) > 1:
        ordered_items = reorder_items_with_vision(ordered_items, context, tone, storyline)
    elif not ai_order:
        console.print("[dim]AI ordering disabled — using filename order[/dim]")

    console.print(f"[dim]Scene duration: {sd}s (8s Veo × {speed_factor}x speed) | {num_pairs} pairs | {max_images} images max[/dim]")

    # Count how many are images vs videos
    image_count = sum(1 for _, t in ordered_items if t == "image")
    video_count = sum(1 for _, t in ordered_items if t == "video")

    if image_count > max_images:
        console.print(f"[dim]{image_count} images found, --script-duration {script_duration}s → {num_pairs} pairs × 2 = {max_images} images needed[/dim]")
        ordered_items = shortlist_scenes_with_vision(
            ordered_items, max_images,
            context=context, tone=tone, storyline=storyline,
        )
        # Re-rank the shortlisted subset for optimal pitch flow
        if ai_order and len(ordered_items) > 1:
            console.print(f"\n[bold cyan]Re-ranking {len(ordered_items)} shortlisted scenes for pitch flow...[/bold cyan]")
            ordered_items = reorder_items_with_vision(ordered_items, context, tone, storyline)
    else:
        console.print(f"[dim]{image_count} images fits within --script-duration {script_duration}s ({max_images} max images)[/dim]")

    # Copy ranked files into a visible folder for further processing
    ranked_dir = input_path / "ranked" if input_path.is_dir() else input_path.parent / "ranked"
    if ranked_dir.exists():
        shutil.rmtree(str(ranked_dir))
    ranked_dir.mkdir(exist_ok=True)

    ranked_items: List[Tuple[Path, str]] = []
    for i, (p, t) in enumerate(ordered_items):
        dest = ranked_dir / f"{i:03d}_{p.name}"
        shutil.copy(p, dest)
        ranked_items.append((dest, t))

    ordered_items = ranked_items
    console.print(f"[green]✓[/green] {len(ordered_items)} ranked files copied to {ranked_dir}/")

    # Separate image and video items
    image_items = [(p, t) for p, t in ordered_items if t == "image"]
    video_items = [(p, t) for p, t in ordered_items if t == "video"]

    num_images = len(image_items)
    num_videos = len(video_items)
    # Images are paired (2 per Veo call) → scene count
    import math
    num_image_scenes = math.ceil(num_images / 2)
    num_total_scenes = num_image_scenes + num_videos
    console.print(f"[dim]Collected {num_images} images ({num_image_scenes} scenes) + {num_videos} videos = {num_total_scenes} total scenes[/dim]")

    # Generate pitch from storyline — NOW we know exact image count and scene count
    if storyline and not pitch_script:
        console.print(f"\n[bold cyan]Generating pitch: {num_images} images, {num_total_scenes} scenes, 6s each = {num_total_scenes * 6}s total...[/bold cyan]")
        try:
            pitch_script = generate_pitch_from_storyline(
                storyline=storyline, num_scenes=num_total_scenes,
                num_images=num_images,
                context=context, tone=tone, product=context.split(". ")[0] if "Product:" in context else "",
            )
        except Exception as e:
            console.print(f"  [yellow]⚠[/yellow] Pitch generation failed ({e})")

    console.print(Panel.fit(
        "[bold blue]🎬 Veo 3.1 Marketing Video Creator[/bold blue]\n"
        f"Images: {num_images} | Scenes: {num_total_scenes} | Videos: {num_videos} | Voice: {voice} | Resolution: {resolution}",
        border_style="blue"
    ))

    # Create temp directory
    temp_dir = Path(".temp_veo_pipeline")
    temp_dir.mkdir(exist_ok=True)

    scenes: List[SceneData] = []

    # Step 0: Process video inputs (clean + transcribe)
    if num_videos > 0:
        from ..processing.video_cleaner import clean_video
        from ..ai.tts_engine import transcribe_video
        from ..core.video_utils import get_duration

        console.print(f"\n[bold cyan]Step 0: Processing {num_videos} video input(s)...[/bold cyan]")

    # Build scenes list: pair consecutive images for Veo transitions, process videos inline
    video_counter = 0
    static_images = [(p, i) for i, (p, t) in enumerate(ordered_items) if t == "image"]
    total_items = len(ordered_items)

    # Create paired image scenes: (1,2), (3,4), (5,6)...
    paired_image_indices = set()  # track which ordered_items indices are consumed by pairs
    image_pair_scenes: List[Tuple[int, SceneData]] = []  # (insert_position, scene)
    for pair_idx in range(0, len(static_images) - 1, 2):
        first_path, first_ord_idx = static_images[pair_idx]
        second_path, second_ord_idx = static_images[pair_idx + 1]
        scene = SceneData(
            image_path=first_path,
            last_image_path=second_path,
            script="",  # filled in Step 1
        )
        image_pair_scenes.append((first_ord_idx, scene))
        paired_image_indices.add(first_ord_idx)
        paired_image_indices.add(second_ord_idx)
        console.print(f"  [dim]Paired: {first_path.name} + {second_path.name}[/dim]")

    # Handle odd remaining image (unpaired)
    if len(static_images) % 2 == 1:
        last_path, last_ord_idx = static_images[-1]
        scene = SceneData(
            image_path=last_path,
            script="",  # filled in Step 1
        )
        image_pair_scenes.append((last_ord_idx, scene))
        paired_image_indices.add(last_ord_idx)
        console.print(f"  [dim]Unpaired (single): {last_path.name}[/dim]")

    num_pairs = sum(1 for _, s in image_pair_scenes if s.last_image_path)
    num_singles = sum(1 for _, s in image_pair_scenes if not s.last_image_path)
    console.print(f"[dim]Image scenes: {num_pairs} pairs + {num_singles} singles = {num_pairs * 2 + num_singles} images in {num_pairs + num_singles} Veo calls[/dim]")

    # Now build the final scenes list in order, interleaving video and paired-image scenes
    for item_idx, (item_path, item_type) in enumerate(ordered_items):
        if item_type == "video":
            video_counter += 1
            console.print(f"  [cyan]Processing video {video_counter}/{num_videos}: {item_path.name}[/cyan]")

            # Check if user marked this file as "no voiceover" (keep original audio only)
            _no_vo_files = no_voiceover_files or []
            skip_voiceover = item_path.name in _no_vo_files

            # Check for companion mic file (screen recording with separate voiceover)
            # e.g. screen-recording-2026-03-18.webm + mic-recording-2026-03-18.webm
            has_separate_mic = False
            mic_file_path = None
            if not skip_voiceover and item_path.name.startswith("screen-recording-"):
                # Look for matching mic file with same timestamp
                timestamp_part = item_path.stem.replace("screen-recording-", "")
                candidate = item_path.parent / f"mic-recording-{timestamp_part}{item_path.suffix}"
                if candidate.exists():
                    mic_file_path = candidate
                    has_separate_mic = True
                    console.print(f"  [green]✓[/green] Found companion mic track: {candidate.name}")
                    console.print(f"  [dim]System audio will be preserved, voiceover from mic track[/dim]")
                else:
                    # Also check for any mic-recording file with .webm extension
                    for sibling in item_path.parent.iterdir():
                        if sibling.name.startswith("mic-recording-") and sibling.suffix in ('.webm', '.mp3', '.wav', '.m4a'):
                            mic_file_path = sibling
                            has_separate_mic = True
                            console.print(f"  [green]✓[/green] Found mic track: {sibling.name}")
                            console.print(f"  [dim]System audio will be preserved, voiceover from mic track[/dim]")
                            break

            # Get original video duration (before cleaning) for script length targeting
            try:
                original_vid_duration = get_duration(item_path)
                console.print(f"  [dim]Original video duration: {original_vid_duration:.1f}s[/dim]")
            except Exception:
                original_vid_duration = None

            # Skip voiceover: keep original audio, no transcription/TTS
            if skip_voiceover:
                console.print(f"  [yellow]⊘[/yellow] No voiceover — keeping original audio intact")
                vid_duration = original_vid_duration or 8.0
                scenes.append(SceneData(
                    image_path=item_path,
                    script="",
                    video_path=item_path,
                    duration=vid_duration,
                    is_video=True,
                    preserve_audio=True,
                ))
                continue

            if not skip_voiceover:
                console.print(f"  [dim]Target ~{int((original_vid_duration or 8) * 2.5)} words[/dim]")

            # Extract frames every 3 seconds for visual context
            from ..processing.video_extractors import extract_keyframes
            frame_interval = 3  # seconds
            num_frames = max(2, int((original_vid_duration or 30) / frame_interval))
            keyframe_dir = temp_dir / f"keyframes_{item_path.stem}"
            try:
                video_frames = extract_keyframes(item_path, keyframe_dir, max_frames=num_frames)
                console.print(f"  [green]✓[/green] Extracted {len(video_frames)} frames (1 every {frame_interval}s)")
            except Exception as e:
                console.print(f"  [yellow]⚠[/yellow] Frame extraction failed: {e}")
                video_frames = []

            # Transcribe audio — use mic track if available, otherwise video audio
            try:
                if has_separate_mic and mic_file_path:
                    transcribed_text = transcribe_video(mic_file_path)
                    console.print(f"  [green]✓[/green] Transcribed mic track: \"{transcribed_text[:60]}...\"")
                else:
                    transcribed_text = transcribe_video(item_path)
                    console.print(f"  [green]✓[/green] Transcribed: \"{transcribed_text[:60]}...\"")
            except Exception as e:
                console.print(f"  [yellow]⚠[/yellow] Transcription failed: {e}")
                transcribed_text = ""

            # Polish the raw transcript with scene position context + video frames
            if transcribed_text.strip():
                console.print(f"  [cyan]Polishing transcript with {len(video_frames)} frames...[/cyan]")
                # Gather preceding script for narrative flow
                preceding_script = None
                if scenes:
                    for prev in reversed(scenes):
                        if prev.script and prev.script.strip():
                            preceding_script = prev.script
                            break
                transcribed_text = polish_transcript(
                    transcribed_text, context=context, tone=tone, storyline=storyline,
                    scene_number=item_idx + 1, total_scenes=total_items,
                    preceding_script=preceding_script,
                    target_duration=original_vid_duration,
                    video_frames=video_frames,
                )
                console.print(f"  [green]✓[/green] Polished: \"{transcribed_text[:60]}...\"")
            else:
                # Silent video — analyze keyframes visually to generate a voiceover script
                console.print(f"  [cyan]No speech detected — analyzing video visually...[/cyan]")
                try:
                    vid_dur_for_analysis = get_duration(item_path)
                except Exception:
                    vid_dur_for_analysis = 30.0
                transcribed_text = analyze_video_for_script(
                    item_path, vid_dur_for_analysis,
                    context=context, tone=tone, storyline=storyline,
                    temp_dir=temp_dir
                )

            # Validate script length against video duration — retry if way too short
            if original_vid_duration and transcribed_text.strip():
                target_words = int(original_vid_duration * 2.5)
                actual_words = len(transcribed_text.split())
                if actual_words < target_words * 0.5:
                    console.print(f"  [yellow]⚠ Script too short: {actual_words} words vs target {target_words} for {original_vid_duration:.0f}s video — retrying...[/yellow]")
                    transcribed_text = analyze_video_for_script(
                        item_path, original_vid_duration,
                        context=context, tone=tone, storyline=storyline,
                        temp_dir=temp_dir
                    )
                    actual_words = len(transcribed_text.split())
                    console.print(f"  [dim]Retry result: {actual_words} words[/dim]")

            # Clean video (remove still frames) — after transcription so no speech is lost
            cleaned_output = temp_dir / f"cleaned_{item_path.stem}.mp4"
            try:
                cleaned_path, segments = clean_video(item_path, cleaned_output)
                console.print(f"  [green]✓[/green] Cleaned: {cleaned_path.name}")
            except Exception as e:
                console.print(f"  [yellow]⚠[/yellow] Cleaning failed, using original: {e}")
                cleaned_path = item_path

            # Get cleaned video duration
            try:
                vid_duration = get_duration(cleaned_path)
            except Exception:
                vid_duration = original_vid_duration or 8.0

            # Strip original audio — unless we're preserving system audio
            if has_separate_mic:
                # Keep system audio intact — voiceover will be mixed on top
                video_for_scene = cleaned_path
                console.print(f"  [green]✓[/green] Preserving system audio (voiceover will be layered on top)")
            else:
                # No separate mic — strip all audio, TTS will replace it entirely
                import subprocess
                muted_path = temp_dir / f"muted_{item_path.stem}.mp4"
                try:
                    result = subprocess.run(
                        ["ffmpeg", "-y", "-i", str(cleaned_path),
                         "-an", "-c:v", "copy", str(muted_path)],
                        capture_output=True, text=True, timeout=120
                    )
                    if result.returncode == 0:
                        video_for_scene = muted_path
                        console.print(f"  [green]✓[/green] Stripped original audio")
                    else:
                        video_for_scene = cleaned_path
                        console.print(f"  [yellow]⚠[/yellow] Audio strip failed, original audio will remain")
                except Exception:
                    video_for_scene = cleaned_path

            # Use first extracted frame as thumbnail (for unified narrative visual context)
            scene_thumbnail = video_frames[0] if video_frames else item_path
            scenes.append(SceneData(
                image_path=scene_thumbnail,
                script=transcribed_text,
                video_path=video_for_scene,
                duration=vid_duration,
                is_video=True,
                preserve_audio=has_separate_mic,
            ))
        else:
            # Insert paired image scene at this position (only for the first image of each pair)
            for pair_ord_idx, pair_scene in image_pair_scenes:
                if pair_ord_idx == item_idx:
                    scenes.append(pair_scene)
                    break

    # Step 1a: Extract text (OCR) from each static image
    static_scenes = [s for s in scenes if not s.is_video]
    if static_scenes:
        console.print(f"\n[bold cyan]Step 1a: Extracting text from {len(static_scenes)} images (OCR)...[/bold cyan]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            console=console
        ) as progress:
            task = progress.add_task("Extracting text...", total=len(static_scenes))

            for scene in static_scenes:
                progress.update(task, description=f"OCR: {scene.image_path.name}...")
                try:
                    scene.extracted_text = extract_image_text(scene.image_path)
                    if scene.extracted_text:
                        console.print(f"  [green]✓[/green] OCR {scene.image_path.name}: \"{scene.extracted_text[:50]}...\"")
                    else:
                        console.print(f"  [yellow]⚠[/yellow] OCR {scene.image_path.name}: no text returned (image may have been blocked by safety filter)")
                except Exception as e:
                    console.print(f"  [yellow]⚠[/yellow] OCR failed for {scene.image_path.name}: {e}")
                    scene.extracted_text = ""
                # Also OCR the last image if this is a paired scene
                if scene.last_image_path:
                    progress.update(task, description=f"OCR: {scene.last_image_path.name}...")
                    try:
                        scene.last_extracted_text = extract_image_text(scene.last_image_path)
                        if scene.last_extracted_text:
                            console.print(f"  [green]✓[/green] OCR {scene.last_image_path.name}: \"{scene.last_extracted_text[:50]}...\"")
                        else:
                            console.print(f"  [yellow]⚠[/yellow] OCR {scene.last_image_path.name}: no text returned (image may have been blocked by safety filter)")
                    except Exception as e:
                        console.print(f"  [yellow]⚠[/yellow] OCR failed for {scene.last_image_path.name}: {e}")
                        scene.last_extracted_text = ""
                progress.advance(task)

    # Step 1b: Assign scripts to scenes (pitch was already generated after shortlisting)
    if len(scenes) > 0:
        if pitch_script:
            # Split by line breaks — each line of the pitch = one scene
            pitch_lines = [s.strip() for s in pitch_script.strip().split("\n") if s.strip()]
            flexible_scenes = [i for i, s in enumerate(scenes) if not (s.is_video and s.script and s.script.strip())]
            console.print(f"\n[bold cyan]Step 1b: Splitting pitch across {len(scenes)} scenes...[/bold cyan]")
            console.print(f"  [dim]Pitch has {len(pitch_lines)} lines for {len(flexible_scenes)} scenes[/dim]")

            # 1:1 mapping — each line goes to one scene
            for idx, scene_idx in enumerate(flexible_scenes):
                if idx < len(pitch_lines):
                    scenes[scene_idx].script = pitch_lines[idx]
                # If fewer lines than scenes, leave script empty (will use fallback)

        else:
            # No pitch — use AI to generate per-scene scripts
            console.print(f"\n[bold cyan]Step 1b: Generating scripts for {len(scenes)} scenes...[/bold cyan]")

            all_scene_info = []
            for i, scene in enumerate(scenes):
                info = {
                    "image_path": str(scene.image_path),
                    "extracted_text": scene.extracted_text or "",
                    "is_video": scene.is_video,
                    "position": i,
                    "duration": scene.duration,
                }
                if scene.is_video and scene.script and scene.script.strip():
                    info["fixed_script"] = scene.script
                all_scene_info.append(info)

            try:
                scripts = generate_unified_narrative(
                    all_scene_info, context=context, tone=tone,
                    storyline=storyline, product=context.split(". ")[0] if "Product:" in context else "",
                    target_duration=script_duration, style=style,
                )
                for i, scene in enumerate(scenes):
                    if scene.is_video and scene.script and scene.script.strip():
                        pass
                    else:
                        scene.script = scripts[i]
            except Exception as e:
                console.print(f"  [yellow]⚠[/yellow] Unified narrative failed ({e}), falling back to per-scene generation")
                for scene in static_scenes:
                    if not scene.script or not scene.script.strip():
                        try:
                            script, extracted_text = analyze_image_for_script_and_text(
                                scene.image_path, context, tone, storyline=storyline
                            )
                            scene.script = script
                            if not scene.extracted_text:
                                scene.extracted_text = extracted_text
                            console.print(f"  [green]✓[/green] {scene.image_path.name}: \"{script[:50]}...\"")
                        except Exception as inner_e:
                            console.print(f"  [yellow]⚠[/yellow] {scene.image_path.name}: Using default script ({inner_e})")
                            scene.script = "Discover the amazing features of our innovative solution."

        # Print full script breakdown
        total_words = sum(len(s.script.split()) for s in scenes if s.script)
        console.print(f"\n[bold green]{'─' * 60}[/bold green]")
        console.print(f"[bold green]SCRIPT ({total_words} words, ~{int(total_words / 5)}s)[/bold green]")
        console.print(f"[bold green]{'─' * 60}[/bold green]")
        for i, scene in enumerate(scenes):
            word_count = len(scene.script.split()) if scene.script else 0
            console.print(f"  [bold]Scene {i+1}[/bold] ({word_count}w, ~{int(word_count / 5)}s): {scene.script}")
        console.print(f"[bold green]{'─' * 60}[/bold green]\n")

    # Step 2: Generate Veo videos from static images (parallel)
    veo_scenes = [s for s in scenes if not s.is_video]
    if veo_scenes:
        console.print(f"\n[bold cyan]Step 2: Generating videos with Veo 3.1 ({max_concurrent_veo} concurrent)...[/bold cyan]")
        asyncio.run(_generate_veo_scenes_parallel(veo_scenes, temp_dir, max_concurrent_veo, storyline=storyline, scene_duration=sd))
    else:
        console.print("\n[bold cyan]Step 2: No static images — skipping Veo generation[/bold cyan]")

    # Step 3: Generate voiceovers
    console.print("\n[bold cyan]Step 3: Generating voiceovers...[/bold cyan]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        console=console
    ) as progress:
        task = progress.add_task("Recording...", total=len(scenes))

        for i, scene in enumerate(scenes):
            progress.update(task, description=f"Recording voiceover {i+1}/{len(scenes)}...")

            # Skip TTS if scene has no script (e.g. video with failed transcription)
            if not scene.script or not scene.script.strip():
                console.print(f"  [dim]Skipping voiceover {i+1}: no script[/dim]")
                progress.advance(task)
                continue

            audio_output = temp_dir / f"voiceover_{i:03d}.mp3"

            try:
                # Enhance script with TTS delivery cues (emphasis, pauses, energy)
                tts_script = enhance_script_for_tts(scene.script)
                word_count = len(tts_script.split())
                console.print(f"  [dim]Scene {i+1} TTS input ({word_count} words): \"{tts_script[:80]}...\"[/dim]")
                if word_count < 13:
                    console.print(f"  [yellow]⚠[/yellow] Scene {i+1} script too short ({word_count} words) — TTS may be under 6s")
                audio_path, tts_duration = generate_voiceover(
                    tts_script,
                    audio_output,
                    engine=tts_engine,
                    voice=voice,
                    speed=voice_speed,
                )
                scene.audio_path = audio_path
                # For video scenes, keep the original video duration
                if not scene.is_video:
                    scene.duration = tts_duration
                console.print(f"  [green]✓[/green] Voiceover {i+1}: {tts_duration:.1f}s ({word_count} words)")
            except Exception as e:
                console.print(f"  [yellow]⚠[/yellow] TTS failed: {e}")
                scene.audio_path = None

            progress.advance(task)

    # Step 4: Combine videos with voiceovers
    console.print("\n[bold cyan]Step 4: Combining video and audio...[/bold cyan]")

    final_clips = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        console=console
    ) as progress:
        task = progress.add_task("Combining...", total=len(scenes))

        for i, scene in enumerate(scenes):
            progress.update(task, description=f"Processing scene {i+1}...")

            combined_output = temp_dir / f"combined_{i:03d}.mp4"

            if scene.video_path and scene.audio_path:
                # preserve_audio: keep system audio at full volume, layer voiceover on top
                orig_vol = 1.0 if scene.preserve_audio else 0.3
                combine_video_with_audio(
                    scene.video_path,
                    scene.audio_path,
                    combined_output,
                    audio_volume=voice_volume,
                    original_audio_volume=orig_vol,
                    no_speed_adjust=scene.is_video,  # Video inputs: keep original pace, voiceover covers what it covers
                )
            elif scene.video_path:
                # No audio, just use video
                shutil.copy(scene.video_path, combined_output)

            if combined_output.exists():
                clip = VideoFileClip(str(combined_output))
                scene.duration = clip.duration  # Update to actual duration after speed adjustment
                final_clips.append(clip)

            progress.advance(task)

    # Step 4.5: Generate intro/outro bookend clips (in parallel)
    if generate_intro or generate_outro:
        console.print("\n[bold cyan]Step 4.5: Generating intro/outro bookends...[/bold cyan]")
        try:
            from .bookend_generator import animate_bookend, BookendSuggestion
            from concurrent.futures import ThreadPoolExecutor, as_completed

            bookend_dir = temp_dir / "bookends"
            bookend_dir.mkdir(parents=True, exist_ok=True)
            intro_result_path = None
            outro_result_path = None

            bookend_tasks = {}

            def _animate_intro():
                if intro_image_path and Path(intro_image_path).exists():
                    console.print("  Animating pre-selected intro frame...")
                    return animate_bookend(
                        image_path=Path(intro_image_path),
                        suggestion=BookendSuggestion(
                            option_number=1, title_text=product or "Intro",
                            subtitle_text="", image_description="",
                            veo_motion_prompt=intro_veo_prompt or "slow elegant zoom out with subtle light effects",
                        ),
                        output_path=bookend_dir / "intro_animated.mp4",
                        duration=sd, resolution=resolution,
                        product=product, tone=tone, style=style,
                    )
                else:
                    from .bookend_generator import generate_bookends
                    path, _ = generate_bookends(
                        product=product, storyline=storyline, tone=tone, style=style,
                        context=context, output_dir=bookend_dir, resolution=resolution,
                        duration=sd, interactive=True, generate_intro=True, generate_outro=False,
                    )
                    return path

            def _animate_outro():
                if outro_image_path and Path(outro_image_path).exists():
                    console.print("  Animating pre-selected outro frame...")
                    return animate_bookend(
                        image_path=Path(outro_image_path),
                        suggestion=BookendSuggestion(
                            option_number=1, title_text="Get Started",
                            subtitle_text=product or "", image_description="",
                            veo_motion_prompt=outro_veo_prompt or "gentle drift right with warm light rays expanding",
                        ),
                        output_path=bookend_dir / "outro_animated.mp4",
                        duration=sd, resolution=resolution,
                        product=product, tone=tone, style=style,
                    )
                else:
                    from .bookend_generator import generate_bookends
                    _, path = generate_bookends(
                        product=product, storyline=storyline, tone=tone, style=style,
                        context=context, output_dir=bookend_dir, resolution=resolution,
                        duration=sd, interactive=True, generate_intro=False, generate_outro=True,
                    )
                    return path

            with ThreadPoolExecutor(max_workers=2) as executor:
                if generate_intro:
                    bookend_tasks["intro"] = executor.submit(_animate_intro)
                if generate_outro:
                    bookend_tasks["outro"] = executor.submit(_animate_outro)

                for key, future in bookend_tasks.items():
                    try:
                        result_path = future.result()
                        if key == "intro":
                            intro_result_path = result_path
                        else:
                            outro_result_path = result_path
                    except Exception as e:
                        console.print(f"  [yellow]⚠[/yellow] {key.title()} bookend failed: {e}")

            if intro_result_path and intro_result_path.exists():
                intro_clip = VideoFileClip(str(intro_result_path))
                final_clips.insert(0, intro_clip)
                console.print(f"  [green]✓[/green] Intro clip added ({intro_clip.duration:.1f}s)")
            if outro_result_path and outro_result_path.exists():
                outro_clip = VideoFileClip(str(outro_result_path))
                final_clips.append(outro_clip)
                console.print(f"  [green]✓[/green] Outro clip added ({outro_clip.duration:.1f}s)")
        except Exception as e:
            console.print(f"  [yellow]⚠[/yellow] Bookend generation failed: {e}")

    # Step 5: Concatenate all scenes using FFmpeg (much faster than MoviePy)
    console.print("\n[bold cyan]Step 5: Creating final video...[/bold cyan]")

    if not final_clips:
        raise ValueError("No clips were created")

    import subprocess

    target_size = {"720p": (1280, 720), "1080p": (1920, 1080), "4k": (3840, 2160)}.get(resolution, (1920, 1080))
    target_w, target_h = target_size

    # Step 5a: Normalize each clip to target resolution + consistent format via FFmpeg
    normalized_paths = []
    for idx, clip in enumerate(final_clips):
        clip_path_attr = getattr(clip, 'filename', None)
        clip.close()

        if not clip_path_attr or not Path(clip_path_attr).exists():
            console.print(f"  [yellow]⚠[/yellow] Clip {idx} has no file path, skipping")
            continue

        src = Path(clip_path_attr)
        norm_path = temp_dir / f"norm_{idx:03d}.mp4"

        # Scale + pad to target resolution, normalize audio to stereo 44.1kHz
        cmd = [
            "ffmpeg", "-y", "-i", str(src),
            "-vf", f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:black",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
            "-r", "30",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
            "-shortest",
            str(norm_path)
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode == 0 and norm_path.exists():
                normalized_paths.append(norm_path)
                console.print(f"  [green]✓[/green] Normalized clip {idx + 1}/{len(final_clips)}")
            else:
                # Fallback: use source directly
                console.print(f"  [yellow]⚠[/yellow] Normalize failed for clip {idx}, using source")
                normalized_paths.append(src)
        except Exception as e:
            console.print(f"  [yellow]⚠[/yellow] Normalize error: {e}, using source")
            normalized_paths.append(src)

    # Close remaining clips
    for clip in final_clips:
        try:
            clip.close()
        except Exception:
            pass

    if not normalized_paths:
        raise ValueError("No clips were normalized")

    # Step 5b: Concatenate using FFmpeg concat demuxer (fast, no re-encode needed)
    concat_list = temp_dir / "concat_list.txt"
    with open(concat_list, "w") as f:
        for p in normalized_paths:
            f.write(f"file '{p}'\n")

    concat_output = temp_dir / "concat_output.mp4" if (music_path and Path(music_path).exists()) else output_path
    concat_output.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_list),
        "-c", "copy",
        str(concat_output)
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            console.print(f"  [yellow]⚠ Concat copy failed, re-encoding...[/yellow]")
            # Fallback: re-encode if stream copy fails (format mismatch)
            cmd = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", str(concat_list),
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
                "-c:a", "aac", "-b:a", "192k",
                str(concat_output)
            ]
            subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        raise ValueError("FFmpeg concatenation timed out")

    console.print(f"  [green]✓[/green] Concatenated {len(normalized_paths)} clips")

    # Add background music if provided
    if music_path and Path(music_path).exists():
        console.print("  Adding background music...")
        add_background_music_to_file(
            concat_output,
            Path(music_path),
            output_path,
            music_volume=music_volume
        )

        # Save background music as a separate output file
        music_output_path = output_path.with_name(output_path.stem + "_music.mp3")
        try:
            shutil.copy(str(music_path), str(music_output_path))
            console.print(f"[green]✓ Background music saved:[/green] {music_output_path.name}")
        except Exception as e:
            console.print(f"[yellow]⚠ Could not save music file: {e}[/yellow]")

    console.print(f"  [green]✓[/green] Final video created")

    # Save script to text file
    script_output_path = output_path.with_suffix('.txt')
    try:
        with open(script_output_path, 'w') as f:
            if pitch_script:
                f.write("PITCH:\n")
                f.write(pitch_script + "\n\n")
            f.write(f"SCRIPT ({len(scenes)} scenes):\n")
            f.write("=" * 50 + "\n")
            for i, scene in enumerate(scenes):
                word_count = len(scene.script.split())
                f.write(f"\nScene {i+1} ({word_count} words, ~{int(word_count / 5)}s):\n")
                f.write(f"{scene.script}\n")
            f.write("\n" + "=" * 50 + "\n")
            total_words = sum(len(s.script.split()) for s in scenes)
            f.write(f"Total: {total_words} words, ~{int(total_words / 5)}s\n")
        console.print(f"[green]✓[/green] Script saved to {script_output_path}")
    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] Script save failed: {e}")

    # Extract audio as separate file
    audio_output_path = output_path.with_suffix('.mp3')
    try:
        _extract_final_audio(output_path, audio_output_path)
    except Exception as e:
        console.print(f"[yellow]⚠ Audio extraction failed: {e}[/yellow]")
        audio_output_path = None

    # Save manifest for post-processing
    pre_music_video = temp_dir / "with_music.mp4" if (music_path and Path(music_path).exists()) else None
    _save_pipeline_manifest(
        output_video=output_path,
        pre_music_video=pre_music_video,
        music_path=music_path,
        voice_volume=voice_volume,
        music_volume=music_volume,
        voice_speed=voice_speed,
    )

    # Calculate total duration
    total_duration = sum(s.duration for s in scenes if s.duration)

    static_count = sum(1 for s in scenes if not s.is_video)
    video_count = sum(1 for s in scenes if s.is_video)
    scenes_summary = f"🎬 Scenes: {len(scenes)} ({static_count} static, {video_count} video)" if video_count else f"🎬 Scenes: {len(scenes)}"

    audio_line = f"\n🔊 Audio: {audio_output_path.absolute()}" if audio_output_path else ""
    music_output_path = output_path.with_name(output_path.stem + "_music.mp3")
    music_line = f"\n🎵 Music file: {music_output_path.absolute()}" if (music_path and music_output_path.exists()) else ""
    console.print(Panel.fit(
        f"[bold green]✓ Marketing video created![/bold green]\n\n"
        f"📁 Video: {output_path.absolute()}{audio_line}{music_line}\n"
        f"⏱️  Duration: {total_duration:.1f}s\n"
        f"{scenes_summary}\n"
        f"🎤 Voice: {voice}\n"
        f"🎵 Music: {'Yes' if music_path else 'No'}",
        border_style="green"
    ))

    return output_path


def create_marketing_video_static(
    input_path: Path,
    output_path: Path,
    tts_engine: str = "elevenlabs",
    voice: str = "Smritika",
    music_path: Optional[Path] = None,
    music_volume: float = 0.03,
    voice_volume: float = 5.0,
    context: str = "",
    tone: str = "professional and engaging"
) -> Path:
    """
    Create marketing video using STATIC images with cursor/highlight animations.
    No Veo - no text distortion. Images remain pixel-perfect.

    Uses the text_animator module for cursor movement and highlights.
    """
    from moviepy import VideoFileClip, concatenate_videoclips, AudioFileClip
    from .text_animator import create_animated_scene

    IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp'}

    input_path = Path(input_path)
    if input_path.is_file():
        image_files = [input_path]
    else:
        image_files = sorted([
            f for f in input_path.iterdir()
            if f.suffix.lower() in IMAGE_EXTENSIONS and not f.name.startswith('.')
        ])

    if not image_files:
        raise ValueError(f"No images found in {input_path}")

    console.print(Panel.fit(
        "[bold blue]🎬 Static Animation Video Creator[/bold blue]\n"
        f"Images: {len(image_files)} | Voice: {voice}\n"
        "Mode: Cursor + Highlights (pixel-perfect, no distortion)",
        border_style="blue"
    ))

    temp_dir = Path(".temp_static_pipeline")
    temp_dir.mkdir(exist_ok=True)

    scenes: List[SceneData] = []

    # Step 1: Analyze images
    console.print("\n[bold cyan]Step 1: Analyzing images...[/bold cyan]")
    for i, image_path in enumerate(image_files):
        try:
            script, extracted_text = analyze_image_for_script_and_text(image_path, context, tone)
            scenes.append(SceneData(
                image_path=image_path,
                script=script,
                extracted_text=extracted_text
            ))
            console.print(f"  [green]✓[/green] {image_path.name}: \"{script[:50]}...\"")
        except Exception as e:
            console.print(f"  [yellow]⚠[/yellow] {image_path.name}: {e}")
            scenes.append(SceneData(
                image_path=image_path,
                script="Discover the amazing features of our solution."
            ))

    # Step 2: Generate voiceovers
    console.print("\n[bold cyan]Step 2: Generating voiceovers...[/bold cyan]")
    for i, scene in enumerate(scenes):
        audio_output = temp_dir / f"voiceover_{i:03d}.mp3"
        try:
            scene.audio_path, scene.duration = generate_voiceover(
                scene.script, audio_output, engine=tts_engine, voice=voice,
            )
            console.print(f"  [green]✓[/green] Voiceover {i+1}: {scene.duration:.1f}s")
        except Exception as e:
            console.print(f"  [yellow]⚠[/yellow] TTS failed: {e}")
            scene.duration = 8.0

    # Step 3: Create animated scenes (cursor + highlights)
    console.print("\n[bold cyan]Step 3: Creating animated scenes...[/bold cyan]")
    for i, scene in enumerate(scenes):
        video_output = temp_dir / f"scene_{i:03d}.mp4"
        try:
            create_animated_scene(
                image_path=scene.image_path,
                script_text=scene.script,
                audio_path=scene.audio_path,
                output_path=video_output,
                fps=30
            )
            scene.video_path = video_output
            console.print(f"  [green]✓[/green] Scene {i+1} animated")
        except Exception as e:
            console.print(f"  [yellow]⚠[/yellow] Animation failed: {e}")
            # Fallback to static
            from moviepy import ImageClip
            clip = ImageClip(str(scene.image_path)).with_duration(scene.duration)
            if scene.audio_path:
                clip = clip.with_audio(AudioFileClip(str(scene.audio_path)))
            clip.write_videofile(str(video_output), fps=30, codec='libx264', audio_codec='aac')
            scene.video_path = video_output
            clip.close()

    # Step 4: Combine all scenes
    console.print("\n[bold cyan]Step 4: Combining scenes...[/bold cyan]")
    clips = []
    for scene in scenes:
        if scene.video_path and scene.video_path.exists():
            clips.append(VideoFileClip(str(scene.video_path)))

    if not clips:
        raise ValueError("No clips created")

    final = concatenate_videoclips(clips, method="compose")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Add background music if provided
    if music_path and Path(music_path).exists():
        console.print("  Adding background music...")
        temp_no_music = temp_dir / "temp_no_music.mp4"
        final.write_videofile(
            str(temp_no_music),
            fps=30,
            codec='libx264',
            audio_codec='aac',
            preset='medium',
            threads=4
        )
        final.close()
        for clip in clips:
            clip.close()
        add_background_music_to_file(temp_no_music, Path(music_path), output_path, music_volume)
    else:
        final.write_videofile(
            str(output_path),
            fps=30,
            codec='libx264',
            audio_codec='aac',
            preset='medium',
            threads=4
        )
        for clip in clips:
            clip.close()
        final.close()

    total_duration = sum(s.duration for s in scenes if s.duration)

    console.print(Panel.fit(
        f"[bold green]✓ Video created![/bold green]\n\n"
        f"📁 Output: {output_path.absolute()}\n"
        f"⏱️  Duration: {total_duration:.1f}s\n"
        f"🎬 Scenes: {len(scenes)}\n"
        f"🎤 Voice: {voice}",
        border_style="green"
    ))

    return output_path
