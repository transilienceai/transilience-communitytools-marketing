"""
Google Gemini Veo 3.1 Video Generator
Generates high-quality videos using Google's Veo 3.1 model.

Uses the REST API (predictLongRunning) which works better than the Python SDK.

Features:
- Text-to-video generation
- Image-to-video generation (animate images)
- 720p, 1080p, or 4K output
- Native audio generation
- Portrait (9:16) or landscape (16:9) videos

Models available:
- veo-3.1-generate-preview: Highest quality, 8-second videos
- veo-3.1-fast-generate-preview: Faster generation, good quality

Requires:
- GOOGLE_API_KEY environment variable (or in .env file)
"""

import os
import time
import requests
from pathlib import Path
from typing import Optional, List, Literal
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from dotenv import load_dotenv
from ..core.image_utils import image_to_base64, get_mime_type

# Load environment variables from .env file
load_dotenv()

console = Console()


def generate_video_veo(
    prompt: str,
    output_path: Path,
    image_path: Optional[Path] = None,
    last_image_path: Optional[Path] = None,
    duration: int = 8,
    aspect_ratio: Literal["16:9", "9:16"] = "16:9",
    resolution: Literal["720p", "1080p", "4k"] = "1080p",
    model: str = "veo-3.1-generate-preview",
    api_key: Optional[str] = None,
    enable_audio: bool = True
) -> Path:
    """
    Generate video using Google Veo 3.1 via REST API.

    Args:
        prompt: Text description of the video to generate
        output_path: Where to save the video
        image_path: Optional image to animate (first frame, image-to-video)
        last_image_path: Optional last frame image for smooth transitions
        duration: Video duration in seconds (default 8)
        aspect_ratio: "16:9" (landscape) or "9:16" (portrait)
        resolution: "720p", "1080p", or "4k"
        model: Veo model to use
        api_key: Google API key (or set GOOGLE_API_KEY env var)
        enable_audio: Generate native audio with video

    Returns:
        Path to the generated video
    """
    api_key = api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(
            "Google API key not set.\n"
            "Get your key at: https://aistudio.google.com/apikey\n"
            "Then set: export GOOGLE_API_KEY=your_key"
        )
    # Strip any whitespace from the API key
    api_key = api_key.strip()

    api_base = "https://generativelanguage.googleapis.com/v1beta"

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task(f"Generating video with Veo 3.1...", total=None)

        # Build request payload
        if image_path and image_path.exists():
            # Image-to-video generation
            progress.update(task, description="Encoding image...")
            image_base64 = image_to_base64(image_path)
            mime_type = get_mime_type(image_path)

            instance = {
                "prompt": prompt,
                "image": {
                    "bytesBase64Encoded": image_base64,
                    "mimeType": mime_type
                }
            }

            # Add last frame for smooth transitions between consecutive scenes
            if last_image_path and last_image_path.exists():
                last_image_base64 = image_to_base64(last_image_path)
                last_mime_type = get_mime_type(last_image_path)
                instance["lastFrame"] = {
                    "bytesBase64Encoded": last_image_base64,
                    "mimeType": last_mime_type
                }
                console.print(f"[dim]Mode: Image-to-Video (with last frame: {last_image_path.name})[/dim]")
            else:
                console.print(f"[dim]Mode: Image-to-Video[/dim]")

            payload = {
                "instances": [instance],
                "parameters": {
                    "aspectRatio": aspect_ratio,
                    "durationSeconds": duration,
                    "resolution": resolution,
                    "personGeneration": "allow_adult"
                }
            }
        else:
            # Text-to-video generation
            payload = {
                "instances": [
                    {
                        "prompt": prompt
                    }
                ],
                "parameters": {
                    "aspectRatio": aspect_ratio,
                    "durationSeconds": duration,
                    "resolution": resolution,
                    "personGeneration": "allow_adult"
                }
            }
            console.print(f"[dim]Mode: Text-to-Video[/dim]")

        console.print(f"[dim]Model: {model} | Duration: {duration}s | Aspect: {aspect_ratio}[/dim]")
        console.print(f"[dim]Prompt: {prompt[:100]}...[/dim]")

        headers = {
            "Content-Type": "application/json"
        }

        progress.update(task, description="Submitting to Veo API...")

        # Submit video generation task (Long Running Operation)
        try:
            response = requests.post(
                f"{api_base}/models/{model}:predictLongRunning?key={api_key}",
                headers=headers,
                json=payload,
                timeout=60
            )

            if response.status_code not in [200, 201]:
                raise ValueError(f"API error {response.status_code}: {response.text[:500]}")

            result = response.json()

            # Get operation name for polling
            operation_name = result.get("name")
            if not operation_name:
                raise ValueError(f"No operation name in response: {result}")

            console.print(f"[dim]Operation: {operation_name.split('/')[-1][:30]}...[/dim]")

        except requests.exceptions.RequestException as e:
            raise ValueError(f"Request failed: {e}")

        progress.update(task, description="Waiting for video generation (2-5 minutes)...")

        # Poll for completion
        max_attempts = 60  # 10 minutes max (10 sec intervals)
        for attempt in range(max_attempts):
            time.sleep(10)
            elapsed = (attempt + 1) * 10
            progress.update(task, description=f"Generating video... ({elapsed}s)")

            try:
                status_response = requests.get(
                    f"{api_base}/{operation_name}?key={api_key}",
                    headers=headers,
                    timeout=30
                )

                if status_response.status_code == 200:
                    status_data = status_response.json()

                    # Check if done
                    if status_data.get("done"):
                        # Check for error
                        if "error" in status_data:
                            error = status_data["error"]
                            raise ValueError(f"Generation failed: {error.get('message', error)}")

                        # Get response with generated videos
                        response_data = status_data.get("response", {})

                        # Try multiple response formats
                        video_uri = None
                        video_bytes = None

                        # Format 1: generateVideoResponse -> generatedSamples
                        gen_video_resp = response_data.get("generateVideoResponse", {})
                        generated_samples = gen_video_resp.get("generatedSamples", [])
                        if generated_samples:
                            video_uri = generated_samples[0].get("video", {}).get("uri")

                        # Format 2: generatedVideos array
                        if not video_uri:
                            generated_videos = response_data.get("generatedVideos", [])
                            if generated_videos:
                                video_uri = generated_videos[0].get("video", {}).get("uri")
                                video_bytes = generated_videos[0].get("video", {}).get("bytesBase64Encoded")

                        # Format 3: videos array
                        if not video_uri and not video_bytes:
                            videos = response_data.get("videos", [])
                            if videos:
                                video_uri = videos[0].get("uri")
                                video_bytes = videos[0].get("bytesBase64Encoded")

                        # Save video
                        output_path = Path(output_path)
                        output_path.parent.mkdir(parents=True, exist_ok=True)

                        if video_bytes:
                            # Video returned as base64
                            progress.update(task, description="Saving video...")
                            with open(output_path, "wb") as f:
                                f.write(base64.b64decode(video_bytes))
                            console.print(f"[green]✓ Video saved: {output_path}[/green]")
                            return output_path

                        elif video_uri:
                            # Download from URI (add API key for authenticated download)
                            progress.update(task, description="Downloading video...")
                            download_url = video_uri
                            if "?" in download_url:
                                download_url += f"&key={api_key}"
                            else:
                                download_url += f"?key={api_key}"

                            video_response = requests.get(download_url, timeout=120)
                            if video_response.status_code == 200:
                                with open(output_path, "wb") as f:
                                    f.write(video_response.content)
                                console.print(f"[green]✓ Video saved: {output_path} ({len(video_response.content)} bytes)[/green]")
                                return output_path
                            else:
                                raise ValueError(f"Failed to download video: {video_response.status_code}")

                        raise ValueError(f"No video in response: {response_data}")

                    else:
                        # Still processing
                        metadata = status_data.get("metadata", {})
                        state = metadata.get("state", "")
                        if state:
                            progress.update(task, description=f"Generating video... ({elapsed}s) - {state}")

            except requests.exceptions.RequestException as e:
                console.print(f"[dim]Status check failed: {e}, retrying...[/dim]")
                continue

        raise TimeoutError("Video generation timed out after 10 minutes")


def generate_video_from_images_veo(
    images: List[Path],
    output_path: Path,
    prompt: str = "smooth cinematic transition between scenes",
    api_key: Optional[str] = None,
    resolution: str = "1080p"
) -> Path:
    """
    Generate a video from multiple images using Veo 3.1.
    Uses first image as the base for animation.

    Args:
        images: List of image paths
        output_path: Where to save the final video
        prompt: Motion/style prompt
        api_key: Google API key

    Returns:
        Path to the generated video
    """
    if not images:
        raise ValueError("No images provided")

    return generate_video_veo(
        prompt=prompt,
        output_path=output_path,
        image_path=images[0],
        api_key=api_key,
        resolution=resolution
    )


def animate_image_veo(
    image_path: Path,
    output_path: Path,
    motion_prompt: str = "subtle natural motion, cinematic quality",
    duration: int = 8,
    api_key: Optional[str] = None
) -> Path:
    """
    Animate a static image using Veo 3.1.

    Args:
        image_path: Path to the image to animate
        output_path: Where to save the video
        motion_prompt: Description of desired motion
        duration: Video duration (default 8 seconds)
        api_key: Google API key

    Returns:
        Path to the animated video
    """
    return generate_video_veo(
        prompt=motion_prompt,
        output_path=output_path,
        image_path=image_path,
        duration=duration,
        api_key=api_key,
        enable_audio=True
    )


def list_veo_models() -> dict:
    """List available Veo models and their capabilities."""
    return {
        "veo-3.1-generate-preview": {
            "description": "Highest quality, 8-second videos with native audio",
            "resolutions": ["720p", "1080p", "4k"],
            "aspect_ratios": ["16:9", "9:16"],
            "features": ["text-to-video", "image-to-video", "native-audio"]
        },
        "veo-3.1-fast-generate-preview": {
            "description": "Faster generation, good quality",
            "resolutions": ["720p", "1080p"],
            "aspect_ratios": ["16:9", "9:16"],
            "features": ["text-to-video", "image-to-video"]
        },
        "veo-3.0-generate-001": {
            "description": "Stable high-quality",
            "resolutions": ["720p", "1080p"],
            "aspect_ratios": ["16:9", "9:16"],
            "features": ["text-to-video", "image-to-video"]
        },
        "veo-3.0-fast-generate-001": {
            "description": "Fast stable model",
            "resolutions": ["720p", "1080p"],
            "aspect_ratios": ["16:9", "9:16"],
            "features": ["text-to-video", "image-to-video"]
        },
        "veo-2.0-generate-001": {
            "description": "Previous generation model",
            "resolutions": ["720p", "1080p"],
            "aspect_ratios": ["16:9", "9:16"],
            "features": ["text-to-video", "image-to-video"]
        }
    }
