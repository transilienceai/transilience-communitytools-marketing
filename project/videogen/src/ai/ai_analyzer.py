"""
AI Vision Analysis and Script Generation
Uses Gemini to analyze screenshots/videos and generate marketing scripts.
"""

import os
import base64
from pathlib import Path
from typing import List, Dict, Any, Union
from dataclasses import dataclass
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..pipeline.screenshot_handler import (
    resize_image_for_api, resize_pil_image_for_api,
    get_video_thumbnail, MediaFile, MediaType,
    IMAGE_EXTENSIONS, VIDEO_EXTENSIONS
)
from .gemini_client import generate_with_content_blocks

console = Console()


@dataclass
class SceneScript:
    """Script for a single scene (image or video clip)."""
    media_path: Path
    description: str
    voiceover: str
    caption: str
    duration: float  # in seconds
    is_video: bool = False

    # Legacy alias for backward compatibility
    @property
    def image_path(self) -> Path:
        return self.media_path


@dataclass
class VideoScript:
    """Complete video script with all scenes."""
    title: str
    scenes: List[SceneScript]
    tone: str
    target_audience: str


def analyze_media_files(
    media_files: List[MediaFile],
    product_name: str = "",
    tone: str = "professional and engaging",
    target_audience: str = "general audience",
    additional_context: str = ""
) -> VideoScript:
    """
    Analyze all media files (images and videos) and generate a cohesive marketing script.
    For videos, extracts a representative frame for analysis.
    """
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Analyzing media with AI...", total=None)

        # Build the content blocks for Gemini
        content = []

        # Add all media (images/slides directly, videos as thumbnails)
        for i, media_file in enumerate(media_files):
            if media_file.media_type == MediaType.IMAGE:
                base64_data, media_type = resize_image_for_api(media_file.path)
                image_bytes = base64.standard_b64decode(base64_data)
                content.append((image_bytes, media_type))
                content.append(f"[Image {i + 1}: {media_file.path.name}]")
            elif media_file.media_type == MediaType.POWERPOINT:
                base64_data, media_type = resize_image_for_api(media_file.path)
                image_bytes = base64.standard_b64decode(base64_data)
                content.append((image_bytes, media_type))
                pptx_name = media_file.original_pptx.name if media_file.original_pptx else "presentation"
                content.append(f"[Slide {media_file.slide_index + 1} from {pptx_name}]")
            else:
                # For videos, extract a thumbnail frame
                thumbnail = get_video_thumbnail(media_file.path)
                base64_data, media_type = resize_pil_image_for_api(thumbnail)
                image_bytes = base64.standard_b64decode(base64_data)
                content.append((image_bytes, media_type))
                content.append(f"[Video Clip {i + 1}: {media_file.path.name} - Duration: {media_file.duration:.1f}s] (showing representative frame)")

        # Build media description for prompt
        media_desc = []
        for i, mf in enumerate(media_files):
            if mf.media_type == MediaType.IMAGE:
                media_desc.append(f"  {i + 1}. Image: {mf.path.name}")
            elif mf.media_type == MediaType.POWERPOINT:
                pptx_name = mf.original_pptx.name if mf.original_pptx else "presentation"
                media_desc.append(f"  {i + 1}. Slide {mf.slide_index + 1} from {pptx_name}")
            else:
                media_desc.append(f"  {i + 1}. Video: {mf.path.name} ({mf.duration:.1f}s)")

        # Add the analysis prompt
        prompt = f"""You are a marketing video scriptwriter. Analyze these {len(media_files)} media files in sequence and create a compelling marketing video script.

Media files:
{chr(10).join(media_desc)}

Product/Context: {product_name or 'Not specified - infer from content'}
Tone: {tone}
Target Audience: {target_audience}
{f'Additional Context: {additional_context}' if additional_context else ''}

For each media file, provide:
1. A brief description of what's shown
2. A voiceover script (2-3 sentences, ~5-8 seconds when spoken)
3. A short caption to display on screen (max 10 words)
4. Duration in seconds:
   - For IMAGES: suggest 4-8 seconds
   - For VIDEOS: use the video's actual duration (provided above)

The script should:
- Flow naturally from one scene to the next
- Build interest and engagement
- End with a clear call-to-action
- Sound natural when spoken aloud
- For video clips, the voiceover should complement what's happening in the video

Respond in this exact JSON format:
{{
    "title": "Video title",
    "scenes": [
        {{
            "media_index": 0,
            "is_video": false,
            "description": "What's shown",
            "voiceover": "The script to be spoken",
            "caption": "On-screen text",
            "duration": 6.0
        }}
    ]
}}

Important: Generate exactly {len(media_files)} scenes, one for each media file in order."""

        content.append(prompt)

        # Make the API call
        response_text = generate_with_content_blocks(
            blocks=content,
            max_output_tokens=4096,
        )

        progress.update(task, description="Processing AI response...")

    # Extract JSON from response (handle markdown code blocks)
    import json
    import re

    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
    if json_match:
        json_str = json_match.group(1)
    else:
        # Try to find raw JSON
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        if json_start != -1 and json_end > json_start:
            json_str = response_text[json_start:json_end]
        else:
            raise ValueError("Could not parse AI response as JSON")

    data = json.loads(json_str)

    # Build the VideoScript
    scenes = []
    for i, scene_data in enumerate(data.get("scenes", [])):
        idx = scene_data.get("media_index", i)
        if idx < len(media_files):
            media_file = media_files[idx]
            is_video = media_file.media_type == MediaType.VIDEO

            # For videos, use actual duration
            if is_video:
                duration = media_file.duration
            else:
                duration = float(scene_data.get("duration", 6.0))

            scenes.append(SceneScript(
                media_path=media_file.path,
                description=scene_data.get("description", ""),
                voiceover=scene_data.get("voiceover", ""),
                caption=scene_data.get("caption", ""),
                duration=duration,
                is_video=is_video
            ))

    return VideoScript(
        title=data.get("title", "Marketing Video"),
        scenes=scenes,
        tone=tone,
        target_audience=target_audience
    )


# Legacy function for backward compatibility
def analyze_screenshots(
    image_paths: List[Path],
    product_name: str = "",
    tone: str = "professional and engaging",
    target_audience: str = "general audience",
    additional_context: str = ""
) -> VideoScript:
    """
    Analyze all screenshots and generate a cohesive marketing script.
    Legacy function - use analyze_media_files for mixed content.
    """
    # Convert paths to MediaFile objects
    media_files = [
        MediaFile(path=p, media_type=MediaType.IMAGE)
        for p in image_paths
    ]
    return analyze_media_files(
        media_files,
        product_name=product_name,
        tone=tone,
        target_audience=target_audience,
        additional_context=additional_context
    )


def regenerate_scene_script(
    scene: SceneScript,
    feedback: str = "",
    tone: str = "professional and engaging"
) -> SceneScript:
    """
    Regenerate script for a single scene with optional feedback.
    """
    from .gemini_client import generate_with_images

    # Get image for analysis (thumbnail for videos)
    if scene.is_video:
        thumbnail = get_video_thumbnail(scene.media_path)
        base64_data, media_type = resize_pil_image_for_api(thumbnail)
    else:
        base64_data, media_type = resize_image_for_api(scene.media_path)

    # Decode base64 back to raw bytes for Gemini
    image_bytes = base64.standard_b64decode(base64_data)

    prompt = f"""Rewrite the marketing script for this {'video clip' if scene.is_video else 'screenshot'}.

Current script:
- Voiceover: {scene.voiceover}
- Caption: {scene.caption}

{f'Feedback to incorporate: {feedback}' if feedback else 'Make it more engaging and compelling.'}

Tone: {tone}

Respond in JSON format:
{{
    "voiceover": "New voiceover script",
    "caption": "New caption",
    "duration": {scene.duration}
}}"""

    response_text = generate_with_images(
        prompt=prompt,
        images=[(image_bytes, media_type)],
        max_output_tokens=1024,
    )

    import json
    import re
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
    if json_match:
        json_str = json_match.group(1)
    else:
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        json_str = response_text[json_start:json_end]

    data = json.loads(json_str)

    return SceneScript(
        media_path=scene.media_path,
        description=scene.description,
        voiceover=data.get("voiceover", scene.voiceover),
        caption=data.get("caption", scene.caption),
        duration=float(data.get("duration", scene.duration)),
        is_video=scene.is_video
    )
