#!/usr/bin/env python3
"""
Marketing Video Generator CLI
AI-powered tool to create professional marketing videos from any combination of:
- Images (PNG, JPG, WebP, etc.)
- Videos (MP4, MOV, AVI, etc.)
- PowerPoint presentations (PPTX, PPT)
- PDF documents

Features:
- Gemini Vision AI script generation
- Google Veo 3.1 cinematic animation
- ElevenLabs/Edge TTS professional voiceovers
- AI music generation
- Voice cloning
- Text animations with cursor & highlights

Quick Start:
    python cli.py generate ./content/ -o video.mp4
    python cli.py veo-marketing ./content/ -o marketing.mp4
    python cli.py voices
"""

import os
import re
import sys
from pathlib import Path
from typing import Optional
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.pipeline.screenshot_handler import (
    get_media_files, validate_media_files, MediaFile, MediaType,
    get_video_thumbnail, resize_pil_image_for_api,
    IMAGE_EXTENSIONS, VIDEO_EXTENSIONS, PPTX_EXTENSIONS
)
from src.ai.ai_analyzer import analyze_screenshots, analyze_media_files, VideoScript
from src.ai.tts_engine import generate_audio_segments, list_available_voices
from src.pipeline.video_assembler import assemble_video, SceneConfig, get_recommended_size

load_dotenv()
console = Console()


@click.group()
@click.version_option(version="1.0.0", prog_name="Marketing Video Generator")
def cli():
    """
    🎬 Marketing Video Generator - AI-powered video creation from any content.

    Supports: Images, Videos, PowerPoint, PDF • Gemini Vision • Veo 3.1 • ElevenLabs TTS

    Commands organized by category:

    \b
    Video Generation:
        create           All-in-one: clone voice + generate music + create video
        generate         Create video from images/videos/PPT/PDF
        veo-marketing    Full Veo 3.1 animated marketing video
        veo              Generate/animate with Google Veo 3.1
        engage           Create engaging videos with cursor & highlights

    \b
    Content Preparation:
        storyboard       Plan scenes from website URL + storyline → screenshots + AI images
        blend            Blend assets from folders into numbered sequence

    \b
    Post-Processing:
        post             Adjust speed, voice volume, music volume (no re-pipeline)

    \b
    Audio & Voice:
        voices           List available TTS voices
        voice-clone      Clone voices using ElevenLabs
        music            Generate AI background music

    \b
    Utilities:
        info             Show setup guide and examples

    Run 'python cli.py COMMAND --help' for detailed options.
    """
    pass


@cli.command()
@click.argument("input_path", type=click.Path(exists=True))
@click.option("-o", "--output", default="output.mp4", help="Output video file path")
@click.option("--product", default="", help="Product/service name for better context")
@click.option("--tone", default="professional and engaging", help="Script tone (e.g., 'casual', 'professional', 'energetic')")
@click.option("--audience", default="general audience", help="Target audience (e.g., 'developers', 'business owners')")
@click.option("--context", default="", help="Additional context about your product/service")
@click.option("--music", type=click.Path(exists=True), help="Path to background music file (.mp3, .wav)")
@click.option("--generate-music", is_flag=True, help="Auto-generate AI background music (requires API key)")
@click.option("--music-engine", type=click.Choice(["auto", "elevenlabs", "elevenlabs-sfx", "replicate", "suno", "simple"]), default="auto", help="Music generation engine")
@click.option("--music-prompt", default=None, help="Prompt for AI music generation (e.g., 'upbeat corporate background music')")
@click.option("--music-volume", default=0.03, type=float, help="Background music volume 0.0-1.0 (default: 0.03 - quiet)")
@click.option("--tts-engine", type=click.Choice(["edge", "openai", "elevenlabs"]), default="edge", help="Text-to-speech engine (edge=free, elevenlabs=premium)")
@click.option("--voice", default=None, help="Voice name (run 'python cli.py voices' to see options)")
@click.option("--no-captions", is_flag=True, help="Disable on-screen text captions")
@click.option("--caption-position", type=click.Choice(["bottom", "top", "center"]), default="bottom", help="Caption position on screen")
@click.option("--fps", default=30, type=int, help="Output video frame rate (default: 30)")
@click.option("--size", default=None, help="Video dimensions WxH (e.g., '1920x1080'). Auto-detected from input if not set.")
@click.option("--script-only", is_flag=True, help="Generate script only without creating video (preview mode)")
@click.option("--dry-run", is_flag=True, help="Show what would be processed without generating video")
def generate(
    input_path: str,
    output: str,
    product: str,
    tone: str,
    audience: str,
    context: str,
    music: Optional[str],
    generate_music: bool,
    music_engine: str,
    music_prompt: Optional[str],
    music_volume: float,
    tts_engine: str,
    voice: Optional[str],
    no_captions: bool,
    caption_position: str,
    fps: int,
    size: Optional[str],
    script_only: bool,
    dry_run: bool
):
    """
    Create marketing video from images, videos, PowerPoint, and PDFs.

    \b
    INPUT_PATH: Directory containing media files or a single file

    \b
    Supported Input Types:
    • Images:      .png, .jpg, .jpeg, .webp, .gif, .bmp
    • Videos:      .mp4, .mov, .avi, .mkv, .webm, .m4v
    • PowerPoint:  .pptx, .ppt (each slide becomes a scene)
    • Documents:   .pdf (each page becomes a scene)

    \b
    Pipeline:
    1. Analyze content with Gemini Vision AI
    2. Generate marketing script automatically
    3. Create voiceover with professional TTS
    4. Assemble video with captions & music

    \b
    Examples:
        # Basic usage (free)
        python cli.py generate ./screenshots/ -o video.mp4

        # With product context and premium voice
        python cli.py generate ./content/ \\
            --product "My SaaS App" \\
            --tone "friendly and conversational" \\
            --tts-engine elevenlabs --voice "Smritika" \\
            -o marketing.mp4

        # Mixed content (images + videos + PPT)
        python cli.py generate ./mixed_content/ \\
            --generate-music --music-prompt "upbeat tech" \\
            -o complete_video.mp4

        # Preview script before generating
        python cli.py generate ./content/ --script-only

    \b
    Tips:
    • Name files in order (01_intro.png, 02_demo.mp4, 03_slides.pptx)
    • Use --script-only to preview before generating full video
    • Set GOOGLE_API_KEY environment variable for Gemini Vision
    • Set ELEVENLABS_API_KEY for premium voices
    """
    console.print(Panel.fit(
        "[bold blue]🎬 Marketing Video Generator[/bold blue]\n"
        "AI-powered video creation from screenshots & clips",
        border_style="blue"
    ))

    # Check API key
    if not os.getenv("GOOGLE_API_KEY"):
        console.print("[red]Error: GOOGLE_API_KEY not set.[/red]")
        console.print("Set it in your environment or create a .env file.")
        sys.exit(1)

    # Get media files (images and videos)
    console.print(f"\n[bold]📸 Loading media from:[/bold] {input_path}")
    try:
        media_files = get_media_files(input_path)
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)

    num_images = sum(1 for m in media_files if m.media_type == MediaType.IMAGE)
    num_videos = sum(1 for m in media_files if m.media_type == MediaType.VIDEO)
    num_slides = sum(1 for m in media_files if m.media_type == MediaType.POWERPOINT)

    parts = []
    if num_images:
        parts.append(f"{num_images} images")
    if num_videos:
        parts.append(f"{num_videos} video clips")
    if num_slides:
        parts.append(f"{num_slides} slides")
    console.print(f"   Found {', '.join(parts)}")

    # Validate media files
    if not validate_media_files(media_files):
        console.print("[red]Error: Media validation failed[/red]")
        sys.exit(1)

    # Determine video size
    if size:
        width, height = map(int, size.split("x"))
        video_size = (width, height)
    else:
        video_size = get_recommended_size(media_files[0].path)
    console.print(f"   Output size: {video_size[0]}x{video_size[1]}")

    if dry_run:
        console.print("\n[yellow]DRY RUN - would generate video with:[/yellow]")
        console.print(f"  Media files: {len(media_files)} ({num_images} images, {num_videos} videos)")
        console.print(f"  Output: {output}")
        console.print(f"  TTS: {tts_engine}")
        console.print(f"  Music: {music or ('AI Generated' if generate_music else 'None')}")
        return

    # Generate AI music if requested
    music_path = Path(music) if music else None
    if generate_music and not music:
        from src.generators.music_generator import generate_music as gen_music, get_music_prompt_for_tone

        console.print("\n[bold]🎵 Generating AI background music...[/bold]")
        music_prompt_final = music_prompt or get_music_prompt_for_tone(tone)
        console.print(f"   Prompt: [cyan]{music_prompt_final}[/cyan]")

        temp_music_path = Path(output).parent / ".temp_music.mp3"
        try:
            music_path = gen_music(
                prompt=music_prompt_final,
                output_path=temp_music_path,
                duration=60,  # Generate 60s, will be looped/trimmed
                engine=music_engine
            )
        except Exception as e:
            console.print(f"[yellow]Warning: Could not generate music: {e}[/yellow]")
            music_path = None

    # Step 1: Analyze media and generate script
    console.print("\n[bold]🤖 Analyzing media with AI...[/bold]")
    video_script = analyze_media_files(
        media_files,
        product_name=product,
        tone=tone,
        target_audience=audience,
        additional_context=context
    )

    # Display generated script
    console.print(f"\n[bold green]✓ Generated script: {video_script.title}[/bold green]\n")

    table = Table(title="Scene Scripts", show_header=True)
    table.add_column("#", style="cyan", width=4)
    table.add_column("File", style="blue")
    table.add_column("Type", style="magenta", width=6)
    table.add_column("Voiceover", style="white", max_width=45)
    table.add_column("Caption", style="yellow", max_width=18)
    table.add_column("Duration", style="green", width=8)

    for i, scene in enumerate(video_script.scenes):
        media_type = "video" if scene.is_video else "image"
        table.add_row(
            str(i + 1),
            scene.media_path.name,
            media_type,
            scene.voiceover[:95] + "..." if len(scene.voiceover) > 95 else scene.voiceover,
            scene.caption,
            f"{scene.duration:.1f}s"
        )

    console.print(table)

    if script_only:
        console.print("\n[yellow]Script-only mode - stopping here[/yellow]")
        return

    # Step 2: Generate voiceover audio
    console.print("\n[bold]🎙️ Generating voiceover...[/bold]")

    # Create temp directory for audio
    temp_dir = Path(output).parent / ".temp_audio"
    temp_dir.mkdir(parents=True, exist_ok=True)

    voiceovers = [scene.voiceover for scene in video_script.scenes]
    audio_segments = generate_audio_segments(
        voiceovers,
        temp_dir,
        engine=tts_engine,
        voice=voice
    )

    console.print(f"[green]✓ Generated {len(audio_segments)} audio segments[/green]")

    # Step 3: Assemble video
    console.print("\n[bold]🎬 Assembling video...[/bold]")

    # Build scene configs
    scene_configs = []
    for i, (scene, audio) in enumerate(zip(video_script.scenes, audio_segments)):
        scene_configs.append(SceneConfig(
            media_path=scene.media_path,
            audio_path=audio.audio_path,
            caption=scene.caption,
            duration=max(scene.duration, audio.duration + 0.5),
            is_video=scene.is_video
        ))

    # Assemble final video
    output_path = Path(output)
    assemble_video(
        scene_configs,
        output_path,
        video_size=video_size,
        fps=fps,
        music_path=music_path,
        music_volume=music_volume,
        show_captions=not no_captions,
        caption_position=caption_position
    )

    # Cleanup temp files
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)

    # Final summary
    total_duration = sum(s.duration for s in scene_configs)
    console.print(Panel.fit(
        f"[bold green]✓ Video created successfully![/bold green]\n\n"
        f"📁 Output: {output_path.absolute()}\n"
        f"⏱️ Duration: {total_duration:.1f} seconds\n"
        f"📐 Resolution: {video_size[0]}x{video_size[1]}\n"
        f"🎬 Scenes: {len(scene_configs)}",
        border_style="green"
    ))


@cli.command()
@click.option("--engine", type=click.Choice(["edge", "openai", "elevenlabs", "all"]), default="all", help="Filter by TTS engine")
def voices(engine: str):
    """
    List all available text-to-speech voices.

    \b
    Engines:
    • edge        - Microsoft Edge TTS (FREE, no API key needed)
    • openai      - OpenAI TTS (requires OPENAI_API_KEY)
    • elevenlabs  - ElevenLabs (premium quality, requires ELEVENLABS_API_KEY)

    \b
    Examples:
        # Show all voices
        python cli.py voices

        # Show only free voices
        python cli.py voices --engine edge

        # Show ElevenLabs voices (including cloned)
        python cli.py voices --engine elevenlabs
    """
    console.print(Panel.fit("[bold]🎙️ Available TTS Voices[/bold]", border_style="blue"))

    if engine in ("edge", "all"):
        console.print("\n[bold cyan]Edge TTS (Free)[/bold cyan]")
        edge_voices = list_available_voices("edge")
        table = Table(show_header=True)
        table.add_column("Voice ID", style="cyan")
        table.add_column("Description", style="white")
        for voice_id, desc in edge_voices.items():
            table.add_row(voice_id, desc)
        console.print(table)

    if engine in ("openai", "all"):
        console.print("\n[bold green]OpenAI TTS (Requires API key)[/bold green]")
        openai_voices = list_available_voices("openai")
        table = Table(show_header=True)
        table.add_column("Voice ID", style="green")
        table.add_column("Description", style="white")
        for voice_id, desc in openai_voices.items():
            table.add_row(voice_id, desc)
        console.print(table)

    if engine in ("elevenlabs", "all"):
        console.print("\n[bold magenta]ElevenLabs TTS (Premium quality, voice cloning)[/bold magenta]")
        elevenlabs_voices = list_available_voices("elevenlabs")
        if elevenlabs_voices:
            table = Table(show_header=True)
            table.add_column("Voice Name", style="magenta")
            table.add_column("Category", style="white")
            for voice_name, category in elevenlabs_voices.items():
                table.add_row(voice_name, category)
            console.print(table)
        else:
            console.print("[dim]Set ELEVENLABS_API_KEY to see your voices (including cloned ones)[/dim]")
        console.print("\n[dim]Tip: Use 'voice-clone' command to create your own voice[/dim]")


@cli.command("voice-clone")
@click.argument("name", metavar="VOICE_NAME")
@click.argument("audio_files", nargs=-1, type=click.Path(exists=True), metavar="AUDIO_FILE...")
@click.option("--description", default="", help="Optional voice description")
@click.option("--accent", default="", help="Accent (e.g., British, Indian, American, Australian)")
@click.option("--gender", default="", help="Gender (e.g., male, female)")
@click.option("--age", default="", help="Age category (e.g., young, middle_aged, old)")
def voice_clone(name: str, audio_files: tuple, description: str, accent: str, gender: str, age: str):
    """
    Clone a custom voice using ElevenLabs AI voice cloning.

    Creates a high-quality voice clone from your audio samples. Requires ELEVENLABS_API_KEY.

    \b
    Requirements:
    • 1-5 minutes total audio (can use multiple files)
    • Clear audio with minimal background noise
    • Consistent speaking style and quality
    • ElevenLabs API key in environment

    \b
    Arguments:
        VOICE_NAME    Friendly name for your cloned voice (e.g., "Aman", "Narrator")
        AUDIO_FILE    One or more audio files (.mp3, .wav, .m4a)

    \b
    Best Practices:
    • Use high-quality recordings (no music, minimal echo)
    • Provide 2-5 diverse audio samples for better quality
    • Each sample: 30 seconds - 2 minutes
    • Speaker should sound natural and conversational

    \b
    Examples:
        # Clone from single file
        python cli.py voice-clone "My Voice" sample.mp3

        # Clone with metadata for better organization
        python cli.py voice-clone "British Narrator" voice.mp3 \\
            --accent "British" --gender "male" --age "middle_aged"

        # Clone from multiple samples (recommended for best quality)
        python cli.py voice-clone "Sarah" \\
            intro.mp3 presentation.mp3 outro.mp3 \\
            --description "Professional female narrator" \\
            --gender "female"

        # Clone Indian accent voice
        python cli.py voice-clone "Aman" recording.mp3 \\
            --accent "Indian" --gender "male"

    \b
    After Cloning:
    Your cloned voice will appear in the voices list and can be used:
        python cli.py voices --engine elevenlabs
        python cli.py generate ./content/ --tts-engine elevenlabs --voice "My Voice"
        python cli.py veo-marketing ./images/ --voice "My Voice"

    \b
    Setup:
    Set your ElevenLabs API key:
        export ELEVENLABS_API_KEY="your_api_key_here"
    """
    from src.ai.tts_engine import clone_voice_elevenlabs

    if not audio_files:
        console.print("[red]Error: Please provide at least one audio file for voice cloning[/red]")
        console.print("\nUsage: python cli.py voice-clone NAME audio1.mp3 [audio2.mp3 ...]")
        console.print("\nOptions:")
        console.print("  --accent    Accent (e.g., British, Indian, American, Australian)")
        console.print("  --gender    Gender (e.g., male, female)")
        console.print("  --age       Age (e.g., young, middle_aged, old)")
        console.print("\nTips for best results:")
        console.print("  - Use 1-5 minutes of clear audio")
        console.print("  - Minimize background noise")
        console.print("  - Use consistent speaking style")
        return

    label_info = ""
    if accent:
        label_info += f"\nAccent: {accent}"
    if gender:
        label_info += f"\nGender: {gender}"
    if age:
        label_info += f"\nAge: {age}"

    console.print(Panel.fit(
        f"[bold blue]Cloning Voice: {name}[/bold blue]\n"
        f"Using {len(audio_files)} audio sample(s)"
        + label_info,
        border_style="blue"
    ))

    try:
        audio_paths = [Path(f) for f in audio_files]
        voice_id = clone_voice_elevenlabs(
            name, audio_paths,
            description=description,
            accent=accent,
            gender=gender,
            age=age
        )

        console.print(Panel.fit(
            f"[bold green]Voice cloned successfully![/bold green]\n\n"
            f"Voice Name: {name}\n"
            f"Voice ID: {voice_id}"
            + (f"\nAccent: {accent}" if accent else "")
            + (f"\nGender: {gender}" if gender else "")
            + (f"\nAge: {age}" if age else "")
            + f"\n\nUse it with:\n"
            f"  python cli.py generate screenshots1/ --tts-engine elevenlabs --voice \"{name}\"",
            border_style="green"
        ))
    except Exception as e:
        console.print(f"[red]Error cloning voice: {e}[/red]")


@cli.command()
@click.option("-o", "--output", default="background.mp3", help="Output file path (.mp3)")
@click.option("--prompt", default="upbeat corporate background music", help="Describe the music you want")
@click.option("--duration", default=30, type=int, help="Duration in seconds (default: 30)")
@click.option("--engine", type=click.Choice(["auto", "elevenlabs", "elevenlabs-sfx", "replicate", "suno", "simple"]), default="auto", help="Music generation engine (auto=best available)")
def music(output: str, prompt: str, duration: int, engine: str):
    """
    Generate AI background music for your videos.

    Creates custom background music using AI based on your text description.

    \b
    Available Engines:
    • auto           - Automatically selects best available engine
    • elevenlabs     - ElevenLabs Music (high quality, requires API key)
    • elevenlabs-sfx - ElevenLabs Sound Effects
    • suno           - Suno AI (requires API key)
    • replicate      - MusicGen via Replicate (requires API key)
    • simple         - Simple tone generation (fallback, no API needed)

    \b
    Examples:
        # Generate upbeat corporate music
        python cli.py music -o corporate.mp3 \\
            --prompt "upbeat corporate background music" \\
            --duration 60

        # Cinematic dramatic music
        python cli.py music -o dramatic.mp3 \\
            --prompt "cinematic dramatic orchestral music"

        # Chill lo-fi beats
        python cli.py music -o lofi.mp3 \\
            --prompt "chill lo-fi hip hop beats" \\
            --duration 120

        # Sound effects
        python cli.py music -o whoosh.mp3 \\
            --prompt "cinematic whoosh transition" \\
            --engine elevenlabs-sfx

    \b
    Tips:
    • Be specific in your prompt (genre, mood, instruments)
    • Longer durations (60-120s) work better for video backgrounds
    • Use --engine auto to let the system pick the best option
    """
    from src.generators.music_generator import generate_music

    console.print(Panel.fit(
        "[bold blue]🎵 AI Music Generator[/bold blue]",
        border_style="blue"
    ))

    console.print(f"Prompt: [cyan]{prompt}[/cyan]")
    console.print(f"Duration: [cyan]{duration}s[/cyan]")
    console.print(f"Engine: [cyan]{engine}[/cyan]")
    console.print()

    try:
        output_path = generate_music(
            prompt=prompt,
            output_path=Path(output),
            duration=duration,
            engine=engine
        )
        console.print(Panel.fit(
            f"[bold green]✓ Music generated![/bold green]\n\n"
            f"📁 Output: {output_path.absolute()}",
            border_style="green"
        ))
    except Exception as e:
        console.print(f"[red]Error generating music: {e}[/red]")
        sys.exit(1)


@cli.command("create")
# Core I/O
@click.argument("input_path", type=click.Path(exists=True), metavar="INPUT_PATH")
@click.option("-o", "--output", default="output.mp4", help="Output video file path")
# Blend (optional — Phase 0)
@click.option("--blend", is_flag=True, help="Blend assets from subfolders into ordered sequence before creating video")
@click.option("--sequence", type=click.Path(exists=True), help="Markdown file or folder of .md files for blend ordering (implies --blend)")
@click.option("--bookend", type=click.Path(exists=True), help="Image used as first and last frame during blend (implies --blend)")
@click.option("--include-unsequenced/--exclude-unsequenced", default=True,
              help="Include files not in sequence file during blend (default: include)")
@click.option("--ai-order/--no-ai-order", default=True,
              help="Use Gemini Vision for blend ordering (default: ai-order)")
# Voice Cloning (optional)
@click.option("--clone-voice", default=None, metavar="NAME",
              help="Clone a voice from audio samples. Provide a name for the cloned voice.")
@click.option("--clone-from", multiple=True, type=click.Path(exists=True), metavar="AUDIO_FILE",
              help="Audio sample file(s) for voice cloning. Repeat for multiple samples. Requires --clone-voice.")
@click.option("--clone-description", default="", help="Description for the cloned voice")
@click.option("--clone-accent", default="", help="Accent (e.g., British, Indian, American)")
@click.option("--clone-gender", default="", help="Gender (e.g., male, female)")
@click.option("--clone-age", default="", help="Age (e.g., young, middle_aged, old)")
# Music (optional)
@click.option("--generate-music", is_flag=True, help="Generate AI background music")
@click.option("--music-prompt", default=None, help="Music generation prompt (auto-derived from --tone if omitted)")
@click.option("--music-duration", default=60, type=int, help="Generated music duration in seconds (default: 60)")
@click.option("--music-engine", type=click.Choice(["auto", "elevenlabs", "elevenlabs-sfx", "replicate", "suno", "simple"]),
              default="auto", help="Music generation engine (auto=best available)")
@click.option("--music", type=click.Path(exists=True), help="Pre-existing music file (overrides --generate-music)")
@click.option("--music-volume", default=0.03, type=float, help="Music volume 0.0-1.0 (default: 0.03)")
# Video Pipeline
@click.option("--voice", default="Smritika", help="Voice name for TTS (overridden by --clone-voice on success)")
@click.option("--tts-engine", type=click.Choice(["edge", "elevenlabs"]), default="elevenlabs",
              help="TTS engine (elevenlabs=premium, edge=free)")
@click.option("--voice-volume", default=5.0, type=float, help="Voice volume multiplier (default: 5.0)")
@click.option("--voice-speed", default=1.0, type=float, help="Voice speed (1.0=normal, 1.2=20%% faster)")
@click.option("--mix", default=None, metavar="SPEED,VOICE_VOL,MUSIC_VOL",
              help="Compact audio mix shorthand: voice-speed,voice-volume,music-volume (e.g., '1.2,6.0,0.04'). Overrides individual --voice-speed, --voice-volume, --music-volume.")
@click.option("--style", type=click.Choice(["marketing", "feature-explainer", "tutorial-explainer", "instagram-shorts"]),
              default="marketing", help="Video style: marketing (persuasive pitch), feature-explainer (product feature walkthrough), tutorial-explainer (step-by-step educational)")
@click.option("--context", default="", help="Product/service context for better scripts")
@click.option("--product", default="", help="Product name for script generation")
@click.option("--tone", default="professional and engaging", help="Script tone (e.g., casual, energetic)")
@click.option("--resolution", type=click.Choice(["720p", "1080p", "4k"]), default="1080p", help="Video resolution")
@click.option("--max-workers", default=3, type=int, help="Max parallel Veo 3.1 API calls (default: 3)")
@click.option("--script-duration", default=60, type=int, help="Target total narration duration in seconds for static images (default: 60). Ignored for video inputs — voiceover matches video length.")
@click.option("--scene-duration", default=5, type=int, help="Final duration per scene in seconds after speedup (default: 5, range 2-8). 8=no speedup, 5=1.6x speed, 4=2x speed")
# Bookends (optional)
@click.option("--intro/--no-intro", default=False, help="Generate branded intro frame (3 options to pick from)")
@click.option("--outro/--no-outro", default=False, help="Generate branded outro/CTA frame (3 options to pick from)")
@click.option("--intro-video", type=click.Path(exists=True), multiple=True, help="Pre-made intro video(s) to prepend (repeatable, played in order)")
@click.option("--outro-video", type=click.Path(exists=True), multiple=True, help="Pre-made outro video(s) to append (repeatable, played in order)")
# Behavior
@click.option("--no-voiceover", is_flag=True, help="Skip transcription and TTS entirely — keep original audio on all files")
@click.option("--clean-threshold", default=10.0, type=float, help="Motion threshold for still-frame removal (0-100). Higher = more aggressive. 10=near-identical, 50=50%+ similar (default: 10)")
@click.option("--video-speed", default=1.0, type=float, help="Video playback speed multiplier (1.0=normal, 1.5=50%% faster, 2.0=double speed)")
@click.option("--remove-shaky/--keep-shaky", default=False, help="Detect and remove shaky/jittery sections")
@click.option("--shake-threshold", default=3.0, type=float, help="Shake sensitivity (lower = more aggressive, default: 3.0)")
@click.option("--captions/--no-captions", default=False, help="Burn karaoke-style word-highlighted captions onto the video")
@click.option("--storyline", default="", help="Narrative storyline to guide voiceover scripts and video animation prompts")
@click.option("--storyline-file", type=click.Path(exists=True), help="Read storyline from a text file (avoids shell quoting issues)")
@click.option("--dry-run", is_flag=True, help="Show execution plan without running anything")
def create(
    input_path: str,
    output: str,
    blend: bool,
    sequence: Optional[str],
    bookend: Optional[str],
    include_unsequenced: bool,
    ai_order: bool,
    clone_voice: Optional[str],
    clone_from: tuple,
    clone_description: str,
    clone_accent: str,
    clone_gender: str,
    clone_age: str,
    generate_music: bool,
    music_prompt: Optional[str],
    music_duration: int,
    music_engine: str,
    music: Optional[str],
    music_volume: float,
    voice: str,
    tts_engine: str,
    voice_volume: float,
    voice_speed: float,
    mix: Optional[str],
    style: str,
    context: str,
    product: str,
    tone: str,
    resolution: str,
    max_workers: int,
    script_duration: int,
    scene_duration: int,
    intro: bool,
    outro: bool,
    intro_video: tuple,
    outro_video: tuple,
    no_voiceover: bool,
    clean_threshold: float,
    video_speed: float,
    remove_shaky: bool,
    shake_threshold: float,
    captions: bool,
    storyline: str,
    storyline_file: Optional[str],
    dry_run: bool,
):
    """
    All-in-one: blend + clone voice + generate music + create marketing video.

    Combines content blending, voice cloning, AI music generation, and the
    full Veo 3.1 video pipeline into a single command.

    \b
    Pipeline:
    Phase 0: Blend (optional)
        Scan subfolders, order via sequence file / Gemini Vision,
        output numbered folder. Triggered by --blend, --sequence, or --bookend.
    Phase 1: Clone Voice (optional)
        Clone a custom voice from your audio samples.
    Phase 2: Generate Music (optional)
        AI-generate background music from a text prompt.
    Phase 3: Create Video (always)
        Full Veo 3.1 pipeline: analyze → animate → voice → assemble.

    \b
    Supported Input:
    • Images (PNG, JPG, WebP) - Animated with Veo 3.1
    • PowerPoint (PPTX) - Each slide becomes a scene
    • Videos (MP4, MOV, AVI) - Cleaned + transcribed + re-voiced
    • Mix any combination in one folder!

    \b
    Arguments:
        INPUT_PATH    Directory with content or single file

    \b
    Examples:
        # Simplest: just make a video
        python cli.py create ./content/ -o video.mp4

        # Blend from subfolders + sequence + bookend, then create video
        python cli.py create ./project/ -o video.mp4 \\
            --sequence ./sequence-docs/ --bookend logo.png \\
            --voice "Venkat" --generate-music

        # Blend with AI ordering (no sequence file)
        python cli.py create ./scattered_assets/ -o video.mp4 \\
            --blend --storyline "From problem to solution"

        # Clone voice + generate music + make video
        python cli.py create ./content/ -o video.mp4 \\
            --clone-voice "Aman" --clone-from voice.mp3 \\
            --generate-music --music-prompt "upbeat corporate" \\
            --product "My App" --tone "energetic"

        # Full production: blend + clone + music + storyline
        python cli.py create ./project/ -o video.mp4 \\
            --sequence ./sequence-docs/ --bookend logo.png \\
            --clone-voice "Aman" --clone-from voice.mp3 \\
            --generate-music --music-prompt "upbeat corporate" \\
            --storyline "Meet our AI tool" --product "My App"

        # Preview what would happen
        python cli.py create ./project/ -o video.mp4 \\
            --sequence ./sequence-docs/ --bookend logo.png \\
            --generate-music --dry-run

    \b
    Required API Keys:
    • GOOGLE_API_KEY (Gemini Vision + Veo 3.1 - required)
    • ELEVENLABS_API_KEY (for voice cloning + premium TTS)
    """
    from src.ai.tts_engine import clone_voice_elevenlabs
    from src.generators.music_generator import generate_music as gen_music, get_music_prompt_for_tone
    from src.pipeline.veo_pipeline import create_marketing_video_veo

    # ── Read storyline from file if provided ──
    if storyline_file:
        storyline = Path(storyline_file).read_text(encoding="utf-8").strip()
        console.print(f"[dim]Read storyline from {storyline_file} ({len(storyline)} chars)[/dim]")

    # ── Blend: --sequence or --bookend implies --blend ──
    if sequence or bookend:
        blend = True

    # ── Validation ──
    if clone_voice and not clone_from:
        console.print("[red]Error: --clone-voice requires at least one --clone-from audio file[/red]")
        console.print("Example: --clone-voice \"Aman\" --clone-from sample.mp3")
        sys.exit(1)

    if clone_from and not clone_voice:
        console.print("[red]Error: --clone-from requires --clone-voice NAME[/red]")
        sys.exit(1)

    # ── Parse --mix shorthand ──
    if mix:
        try:
            parts = [p.strip() for p in mix.split(",")]
            if len(parts) != 3:
                raise ValueError("expected 3 values")
            voice_speed = float(parts[0])
            voice_volume = float(parts[1])
            music_volume = float(parts[2])
            console.print(f"[dim]--mix applied: speed={voice_speed}, voice-vol={voice_volume}, music-vol={music_volume}[/dim]")
        except (ValueError, IndexError) as e:
            console.print(f"[red]Error: --mix must be 3 comma-separated numbers: speed,voice-vol,music-vol (e.g., '1.2,6.0,0.04')[/red]")
            console.print(f"[red]Got: \"{mix}\" — {e}[/red]")
            sys.exit(1)

    effective_voice = voice
    effective_music_path = Path(music) if music else None

    full_context = context
    if product:
        full_context = f"Product: {product}. {context}" if context else f"Product: {product}"

    # ── Plan display ──
    plan_parts = []
    if blend:
        blend_desc = "Blend assets"
        if sequence:
            blend_desc += f" (sequence: {sequence})"
        if bookend:
            blend_desc += f" (bookend: {Path(bookend).name})"
        plan_parts.append(f"Phase 0: {blend_desc}")
    if clone_voice:
        plan_parts.append(f"Phase 1: Clone voice \"{clone_voice}\" from {len(clone_from)} sample(s)")
    if generate_music and not music:
        plan_parts.append(f"Phase 2: Music generation deferred to Phase 4 (matches final video duration)")
    elif music:
        plan_parts.append(f"Phase 2: Use existing music: {music}")
    plan_parts.append(f"Phase 3: Create Veo 3.1 video ({resolution})")
    if generate_music and not music:
        plan_parts.append(f"Phase 4: Generate background music (duration = final video length) & mix")

    storyline_display = f" | Storyline: \"{storyline[:50]}...\"" if len(storyline) > 50 else (f" | Storyline: \"{storyline}\"" if storyline else "")
    console.print(Panel.fit(
        "[bold blue]Marketing Video Creator - All-in-One[/bold blue]\n\n"
        + "\n".join(f"  {p}" for p in plan_parts)
        + f"\n\n  Voice: {voice} | Engine: {tts_engine} | Output: {output}"
        + storyline_display,
        border_style="blue"
    ))

    if dry_run:
        console.print("\n[yellow]DRY RUN - showing plan only[/yellow]")
        if blend:
            from src.pipeline.blend_handler import blend_content
            console.print(f"\n  Blend:")
            console.print(f"    Input: {input_path}")
            console.print(f"    Sequence: {sequence or 'None (AI ordering)'}")
            console.print(f"    Bookend: {bookend or 'None'}")
            console.print(f"    AI order: {ai_order}")
            blend_content(
                input_path=Path(input_path),
                output_dir=Path(output).parent / ".blended",
                sequence_path=Path(sequence) if sequence else None,
                bookend_path=Path(bookend) if bookend else None,
                include_unsequenced=include_unsequenced,
                ai_order=False,  # Don't call AI during dry-run
                context=full_context,
                tone=tone,
                storyline=storyline,
                dry_run=True,
            )
        if clone_voice:
            console.print(f"\n  Voice Cloning:")
            console.print(f"    Name: {clone_voice}")
            console.print(f"    Samples: {', '.join(clone_from)}")
            if clone_accent:
                console.print(f"    Accent: {clone_accent}")
            if clone_gender:
                console.print(f"    Gender: {clone_gender}")
        if generate_music and not music:
            mp = music_prompt or get_music_prompt_for_tone(tone)
            console.print(f"\n  Music Generation:")
            console.print(f"    Prompt: {mp}")
            console.print(f"    Duration: {music_duration}s")
            console.print(f"    Engine: {music_engine}")
        if storyline:
            console.print(f"\n  Storyline: {storyline}")
        sd = max(2, min(8, scene_duration))
        speed_factor = round(8 / sd, 2) if sd < 8 else 1
        num_pairs = max(1, script_duration // sd)
        max_images = num_pairs * 2
        console.print(f"\n  Video Pipeline:")
        console.print(f"    Input: {input_path}")
        console.print(f"    Resolution: {resolution}")
        console.print(f"    Max Workers: {max_workers}")
        console.print(f"    Scene Duration: {sd}s (8s Veo → {speed_factor}x speed)")
        console.print(f"    Script Duration: {script_duration}s → {num_pairs} pairs × 2 images = {max_images} images max")
        console.print(f"    [dim]If more images than {max_images}, Gemini Vision will shortlist the best ones and re-rank for optimal pitch flow[/dim]")
        if intro or outro:
            console.print(f"\n  Bookends:")
            if intro:
                console.print(f"    Intro: 3 options generated with Imagen 4.0 → pick 1 → animate with Veo ({sd}s)")
            if outro:
                console.print(f"    Outro: 3 options generated with Imagen 4.0 → pick 1 → animate with Veo ({sd}s)")
        return

    # ── Phase 0: Blend ──
    if blend:
        from src.pipeline.blend_handler import blend_content
        import shutil as _shutil

        blend_dir = Path(output).parent / ".blended"
        # Clean previous blend output
        if blend_dir.exists():
            _shutil.rmtree(str(blend_dir))

        console.print(f"\n[bold cyan]Phase 0: Blending assets...[/bold cyan]")
        blended_files = blend_content(
            input_path=Path(input_path),
            output_dir=blend_dir,
            sequence_path=Path(sequence) if sequence else None,
            bookend_path=Path(bookend) if bookend else None,
            include_unsequenced=include_unsequenced,
            ai_order=ai_order,
            context=full_context,
            tone=tone,
            storyline=storyline,
            dry_run=False,
        )
        if not blended_files:
            console.print("[red]Blend produced no files. Aborting.[/red]")
            sys.exit(1)
        # Redirect input_path to the blended folder for subsequent phases
        input_path = str(blend_dir)
        console.print(f"[green]Phase 0 complete: {len(blended_files)} files blended into {blend_dir}/[/green]")
    else:
        console.print("\n[dim]Phase 0: Skipped (no --blend/--sequence/--bookend)[/dim]")

    # ── Phase 1: Voice Cloning ──
    if clone_voice:
        console.print(f"\n[bold cyan]Phase 1: Cloning voice \"{clone_voice}\"...[/bold cyan]")
        try:
            audio_paths = [Path(f) for f in clone_from]
            voice_id = clone_voice_elevenlabs(
                name=clone_voice,
                audio_files=audio_paths,
                description=clone_description,
                accent=clone_accent,
                gender=clone_gender,
                age=clone_age,
            )
            effective_voice = clone_voice
            tts_engine = "elevenlabs"
            console.print(f"[green]Phase 1 complete: Voice \"{clone_voice}\" ready (ID: {voice_id})[/green]")
        except Exception as e:
            console.print(f"[yellow]Voice cloning failed: {e}[/yellow]")
            console.print(f"[yellow]Falling back to voice: \"{effective_voice}\"[/yellow]")
    else:
        console.print("\n[dim]Phase 1: Skipped (no --clone-voice)[/dim]")

    # ── Phase 2: Music (pre-existing file or deferred generation) ──
    if music:
        console.print(f"\n[dim]Phase 2: Using provided music: {music}[/dim]")
    elif generate_music:
        console.print(f"\n[dim]Phase 2: Music generation deferred until after video (to match final duration)[/dim]")
        effective_music_path = None
    else:
        console.print("\n[dim]Phase 2: Skipped (no --generate-music)[/dim]")

    # ── Phase 3: Video Pipeline (without generated music — added in Phase 4) ──
    console.print(f"\n[bold cyan]Phase 3: Creating Veo 3.1 marketing video...[/bold cyan]")
    if no_voiceover:
        console.print(f"  Voice: [yellow]disabled (--no-voiceover)[/yellow]")
    else:
        console.print(f"  Voice: [cyan]{effective_voice}[/cyan] ({tts_engine})")
    console.print(f"  Music: [cyan]{effective_music_path or 'Deferred' if generate_music else 'None'}[/cyan]")

    try:
        output_path = create_marketing_video_veo(
            input_path=Path(input_path),
            output_path=Path(output),
            tts_engine=tts_engine,
            voice=effective_voice,
            music_path=effective_music_path,
            music_volume=music_volume,
            voice_volume=voice_volume,
            context=full_context,
            tone=tone,
            resolution=resolution,
            max_concurrent_veo=max_workers,
            voice_speed=voice_speed,
            storyline=storyline,
            script_duration=script_duration,
            scene_duration=scene_duration,
            style=style,
            ai_order=ai_order,
            generate_intro=intro,
            generate_outro=outro,
            product=product,
            no_voiceover=no_voiceover,
            clean_threshold=clean_threshold,
            video_speed=video_speed,
            remove_shaky=remove_shaky,
            shake_threshold=shake_threshold,
            intro_video_paths=[Path(p) for p in intro_video] if intro_video else None,
            outro_video_paths=[Path(p) for p in outro_video] if outro_video else None,
            captions=captions,
        )
    except Exception as e:
        console.print(f"[red]Error creating video: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # ── Phase 4: Generate music at final video duration & mix ──
    console.print(f"\n[dim]Phase 4 check: generate_music={generate_music}, music={music}, effective_music_path={effective_music_path}[/dim]")
    if generate_music and not music and not effective_music_path:
        from src.pipeline.veo_pipeline import add_background_music_to_file
        from moviepy import VideoFileClip

        # Get actual video duration
        try:
            clip = VideoFileClip(str(output_path))
            final_duration = int(clip.duration) + 1  # round up
            clip.close()
        except Exception as e:
            console.print(f"[yellow]Could not read video duration: {e}[/yellow]")
            final_duration = music_duration  # fallback to user-specified

        # Generate a short loop (max 30s) and let add_background_music_to_file() loop it
        # This saves money — ElevenLabs charges by duration
        MUSIC_LOOP_CAP = 30
        gen_duration = min(final_duration, MUSIC_LOOP_CAP)

        console.print(f"\n[bold cyan]Phase 4: Generating background music...[/bold cyan]")
        music_prompt_final = music_prompt or get_music_prompt_for_tone(tone)
        console.print(f"  Prompt: [cyan]{music_prompt_final}[/cyan]")
        console.print(f"  Generate: [cyan]{gen_duration}s[/cyan] (video: {final_duration}s, will loop if needed)")

        temp_music_path = Path(output).parent / ".temp_create_music.mp3"
        try:
            effective_music_path = gen_music(
                prompt=music_prompt_final,
                output_path=temp_music_path,
                duration=gen_duration,
                engine=music_engine,
            )
            # Mix music into the final video
            temp_with_music = Path(output).parent / ".temp_with_music.mp4"
            import shutil
            shutil.move(str(output_path), str(temp_with_music))
            add_background_music_to_file(
                temp_with_music,
                effective_music_path,
                output_path,
                music_volume=music_volume,
            )
            # Clean up temp video
            if temp_with_music.exists():
                temp_with_music.unlink()

            # Re-extract audio from the music-mixed video (pipeline extracted it before Phase 4)
            from src.pipeline.veo_pipeline import _extract_final_audio
            audio_output = output_path.with_suffix('.mp3')
            try:
                _extract_final_audio(output_path, audio_output)
                console.print(f"[green]✓ Audio (with music) extracted:[/green] {audio_output.name}")
            except Exception as audio_err:
                console.print(f"[yellow]⚠ Audio re-extraction failed: {audio_err}[/yellow]")

            # Save background music as a separate output file (trimmed to video duration)
            music_output = output_path.with_name(output_path.stem + "_music.mp3")
            try:
                import subprocess
                # Trim music to match video duration using ffmpeg
                trim_result = subprocess.run(
                    [
                        "ffmpeg", "-y",
                        "-i", str(effective_music_path),
                        "-t", str(final_duration),
                        "-acodec", "libmp3lame",
                        "-ar", "44100", "-ac", "2", "-b:a", "192k",
                        str(music_output)
                    ],
                    capture_output=True, timeout=30
                )
                if trim_result.returncode != 0:
                    # Fallback: just copy the raw file
                    shutil.copy(str(effective_music_path), str(music_output))
                console.print(f"[green]✓ Background music saved ({final_duration}s):[/green] {music_output.name}")
            except Exception as copy_err:
                console.print(f"[yellow]⚠ Could not save music file: {copy_err}[/yellow]")

            console.print(f"[green]Phase 4 complete: Music generated and mixed[/green]")
        except Exception as e:
            import traceback
            console.print(f"[red]Music generation/mixing failed: {e}[/red]")
            traceback.print_exc()
            console.print("[yellow]Output video remains without background music[/yellow]")
            # If we moved the file but mixing failed, restore it
            temp_with_music = Path(output).parent / ".temp_with_music.mp4"
            if temp_with_music.exists() and not output_path.exists():
                import shutil
                shutil.move(str(temp_with_music), str(output_path))


@cli.command("veo-marketing")
@click.argument("input_path", type=click.Path(exists=True), metavar="INPUT_PATH")
@click.option("-o", "--output", default="marketing_video.mp4", help="Output video file path")
@click.option("--tts-engine", type=click.Choice(["edge", "elevenlabs"]), default="elevenlabs", help="TTS engine (elevenlabs=premium, edge=free)")
@click.option("--voice", default="Smritika", help="Voice name (default: Smritika from ElevenLabs)")
@click.option("--music", type=click.Path(exists=True), help="Background music file (.mp3, .wav)")
@click.option("--music-volume", default=0.03, type=float, help="Music volume 0.0-1.0 (default: 0.03)")
@click.option("--voice-volume", default=5.0, type=float, help="Voice volume multiplier (default: 5.0)")
@click.option("--context", default="", help="Product/service context for better scripts")
@click.option("--tone", default="professional and engaging", help="Script tone (e.g., casual, energetic, professional)")
@click.option("--resolution", type=click.Choice(["720p", "1080p", "4k"]), default="1080p", help="Video resolution (default: 1080p)")
@click.option("--product", default="", help="Product name for better script generation")
@click.option("--max-workers", default=3, type=int, help="Max parallel Veo 3.1 API calls (default: 3)")
@click.option("--voice-speed", default=1.0, type=float, help="Voice speed multiplier (1.0=normal, 1.2=20%% faster, 0.8=slower)")
def veo_marketing(input_path: str, output: str, tts_engine: str, voice: str, music: str,
                  music_volume: float, voice_volume: float, context: str, tone: str, resolution: str, product: str,
                  max_workers: int, voice_speed: float):
    """
    Create professional marketing videos using Google Veo 3.1 AI animation.

    The ULTIMATE marketing video generator with cinematic AI animation!

    \b
    Complete Pipeline:
    Static (images/PPT/PDF):
        1. 🔍 Analyze with Gemini Vision AI → script + OCR
        2. 🎬 Animate with Google Veo 3.1 (cinematic motion)
        3. 🎙️ Add professional voiceover (ElevenLabs or Edge TTS)
    Video files:
        1. 🧹 Clean video (remove still/idle frames)
        2. 📝 Transcribe existing audio (STT)
        3. 🎙️ Regenerate voiceover with professional TTS
    Final:
        4. 🎵 Mix background music
        5. 📦 Combine all scenes → final polished video

    \b
    Supported Input:
    • Images (PNG, JPG, WebP, etc.) - Animated with cinematic motion
    • PowerPoint (PPTX) - Each slide becomes an animated scene
    • PDF Documents - Each page becomes an animated scene
    • Videos (MP4, MOV, AVI, etc.) - Cleaned + transcribed + re-voiced
    • Mix any combination in one folder!

    \b
    Arguments:
        INPUT_PATH    Directory with images/videos/PPT/PDF or single file

    \b
    What Makes This Special:
    • Veo 3.1 turns static images into cinematic video clips
    • Videos are cleaned (stills removed) and re-voiced
    • Mixed content merges seamlessly in filename order
    • AI understands your content and generates relevant motion
    • Professional voiceover synced with visuals

    \b
    Examples:
        # Basic marketing video (free tier with Edge TTS)
        python cli.py veo-marketing ./screenshots/ \\
            -o marketing.mp4 --tts-engine edge

        # Premium quality with ElevenLabs voice
        python cli.py veo-marketing ./product_images/ \\
            -o product_video.mp4 \\
            --voice "Smritika" \\
            --tone "energetic and exciting"

        # Mixed content (images + video + PPT in one folder)
        python cli.py veo-marketing ./marketing_content/ \\
            -o complete_video.mp4 \\
            --voice "Smritika" \\
            --context "SaaS productivity tool"

        # Full production with custom voice and music
        python cli.py veo-marketing ./pitch_deck/ \\
            -o pitch_video.mp4 \\
            --voice "My Cloned Voice" \\
            --music background.mp3 \\
            --music-volume 0.05 \\
            --context "SaaS productivity tool for developers" \\
            --resolution 1080p

        # From PowerPoint presentation
        python cli.py veo-marketing ./presentation.pptx \\
            -o presentation_video.mp4 \\
            --voice "Aman" \\
            --tone "professional and clear"

        # 4K ultra quality
        python cli.py veo-marketing ./product_shots/ \\
            -o ultra_hd.mp4 \\
            --resolution 4k \\
            --voice-volume 6.0

    \b
    Cost Estimates (10 images):
    • Gemini Vision: ~$0.03
    • Veo 3.1 Animation: ~$0.20-0.50
    • ElevenLabs TTS: ~$0.02-0.05
    • Total: ~$0.25-0.60 per video

    \b
    Free Alternative:
    Use Edge TTS (free) instead of ElevenLabs:
        --tts-engine edge --voice "en-US-GuyNeural"

    \b
    Processing Time (default --max-workers 3):
    • 5 images: ~8-10 minutes
    • 10 images: ~12-16 minutes
    • Use --max-workers 1 for sequential (old behavior)
    • Use --max-workers 5 for faster (check API rate limits)

    \b
    Required API Keys:
    • GOOGLE_API_KEY (Gemini Vision + Veo 3.1 - required)
    • ELEVENLABS_API_KEY (optional, for premium voice + transcription)

    \b
    Tips:
    • Name files in order: 01_intro.png, 02_demo.mov, 03_slides.pptx
    • Use --context to tell AI about your product
    • Use --voice-volume 6.0-8.0 if voice too quiet
    • Use --music-volume 0.03-0.08 for subtle background
    • Use --max-workers to control parallel Veo API calls
    • Check voices with: python cli.py voices --engine elevenlabs
    """
    from src.pipeline.veo_pipeline import create_marketing_video_veo

    console.print(Panel.fit(
        "[bold blue]🎬 Veo 3.1 Marketing Video Creator[/bold blue]\n"
        f"Voice: {voice} | Engine: {tts_engine} | Resolution: {resolution}"
        + (f" | Product: {product}" if product else ""),
        border_style="blue"
    ))

    # Combine product and context for better script generation
    full_context = context
    if product:
        full_context = f"Product: {product}. {context}" if context else f"Product: {product}"

    try:
        output_path = create_marketing_video_veo(
            input_path=Path(input_path),
            output_path=Path(output),
            tts_engine=tts_engine,
            voice=voice,
            music_path=Path(music) if music else None,
            music_volume=music_volume,
            voice_volume=voice_volume,
            context=full_context,
            tone=tone,
            resolution=resolution,
            max_concurrent_veo=max_workers,
            voice_speed=voice_speed
        )
    except Exception as e:
        console.print(f"[red]Error creating video: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)


@cli.command("veo")
@click.argument("input_path", type=click.Path(exists=True), required=False)
@click.option("-o", "--output", default="veo_video.mp4", help="Output video file")
@click.option("--prompt", default="cinematic video with smooth motion", help="Video generation prompt")
@click.option("--resolution", type=click.Choice(["720p", "1080p", "4k"]), default="1080p", help="Video resolution")
@click.option("--aspect", type=click.Choice(["16:9", "9:16"]), default="16:9", help="Aspect ratio")
@click.option("--model", type=click.Choice(["veo-3.1-generate-preview", "veo-3.1-fast-generate-preview"]), default="veo-3.1-generate-preview", help="Veo model")
@click.option("--no-audio", is_flag=True, help="Disable native audio generation")
def veo(input_path: str, output: str, prompt: str, resolution: str, aspect: str, model: str, no_audio: bool):
    """
    Generate videos using Google Veo 3.1.

    Can generate video from text prompt or animate an image.

    Examples:
        # Text-to-video
        python cli.py veo --prompt "a sunset over mountains" -o sunset.mp4

        # Image-to-video (animate image)
        python cli.py veo image.png --prompt "gentle motion" -o animated.mp4
    """
    from src.ai.veo_generator import generate_video_veo

    console.print(Panel.fit(
        "[bold blue]🎬 Google Veo 3.1 Video Generator[/bold blue]\n"
        f"Model: {model}\n"
        f"Resolution: {resolution} | Aspect: {aspect}",
        border_style="blue"
    ))

    console.print(f"Prompt: [cyan]{prompt}[/cyan]")
    if input_path:
        console.print(f"Input image: [cyan]{input_path}[/cyan]")
    console.print()

    try:
        output_path = generate_video_veo(
            prompt=prompt,
            output_path=Path(output),
            image_path=Path(input_path) if input_path else None,
            resolution=resolution,
            aspect_ratio=aspect,
            model=model,
            enable_audio=not no_audio
        )

        console.print(Panel.fit(
            f"[bold green]✓ Video generated with Veo 3.1![/bold green]\n\n"
            f"📁 Output: {output_path.absolute()}\n"
            f"Resolution: {resolution}\n"
            f"Audio: {'Yes' if not no_audio else 'No'}",
            border_style="green"
        ))
    except Exception as e:
        console.print(f"[red]Error generating video: {e}[/red]")
        sys.exit(1)


@cli.command("engage")
@click.argument("input_path", type=click.Path(exists=True))
@click.option("-o", "--output", default="engaged_video.mp4", help="Output video file")
@click.option("--tts-engine", type=click.Choice(["edge", "openai", "elevenlabs"]), default="edge", help="TTS engine")
@click.option("--voice", default=None, help="Voice to use")
@click.option("--music", type=click.Path(exists=True), help="Background music file")
@click.option("--music-volume", default=0.03, help="Background music volume")
@click.option("--fps", default=30, help="Output video FPS")
def engage(input_path: str, output: str, tts_engine: str, voice: str, music: str, music_volume: float, fps: int):
    """
    Create ENGAGING videos with cursor movement, text highlights, and zoom effects.

    Syncs animations with voiceover for maximum audience engagement:
    - Cursor points to text being discussed
    - Highlights appear on important text
    - Subtle zoom focuses attention
    - All synced with AI-generated voiceover

    Example:
        python cli.py engage screenshots1/ -o engaging_video.mp4 --tts-engine elevenlabs --voice "Smritika"
    """
    from src.generators.text_animator import create_animated_scene
    from src.ai.ai_analyzer import analyze_screenshots
    from src.ai.tts_engine import generate_audio_segments
    from src.pipeline.screenshot_handler import IMAGE_EXTENSIONS
    from src.pipeline.video_assembler import add_background_music
    from moviepy import VideoFileClip, concatenate_videoclips, AudioFileClip

    input_path = Path(input_path)
    output_path = Path(output)

    console.print(Panel.fit(
        "[bold blue]🎯 Engaging Video Creator[/bold blue]\n"
        "Cursor + Highlights + Zoom + Voice Sync",
        border_style="blue"
    ))

    # Get image files
    if input_path.is_file():
        image_files = [input_path]
    else:
        image_files = sorted([
            f for f in input_path.iterdir()
            if f.suffix.lower() in IMAGE_EXTENSIONS and not f.name.startswith('.')
        ])

    if not image_files:
        console.print("[red]No images found![/red]")
        return

    console.print(f"Found [cyan]{len(image_files)}[/cyan] images to process")

    # Step 1: Analyze images with AI
    console.print("\n[bold]Step 1: Analyzing images with AI...[/bold]")
    video_script = analyze_screenshots(
        image_files,  # Pass list of Path objects
        product_name="",
        tone="engaging and clear",
        target_audience="general audience"
    )

    # Extract voiceover scripts from VideoScript object
    scripts = [scene.voiceover for scene in video_script.scenes]

    # Step 2: Generate voiceovers
    console.print("\n[bold]Step 2: Generating voiceovers...[/bold]")
    temp_dir = Path(".temp_engage")
    temp_dir.mkdir(exist_ok=True)

    audio_segments = generate_audio_segments(
        scripts,
        temp_dir / "audio",
        engine=tts_engine,
        voice=voice
    )

    # Step 3: Create animated scenes
    console.print("\n[bold]Step 3: Creating animated scenes with cursor, highlights, zoom...[/bold]")
    animated_clips = []

    for i, (image_path, script, audio_seg) in enumerate(zip(image_files, scripts, audio_segments)):
        console.print(f"\n  Processing {i+1}/{len(image_files)}: {image_path.name}")

        scene_output = temp_dir / f"scene_{i:03d}.mp4"

        try:
            create_animated_scene(
                image_path=image_path,
                script_text=script,
                audio_path=audio_seg.audio_path,
                output_path=scene_output,
                fps=fps
            )
            animated_clips.append(VideoFileClip(str(scene_output)))
        except Exception as e:
            console.print(f"[yellow]Warning: Animation failed for {image_path.name}: {e}[/yellow]")
            # Fallback to static image
            from moviepy import ImageClip
            clip = ImageClip(str(image_path)).with_duration(audio_seg.duration)
            clip = clip.with_audio(AudioFileClip(str(audio_seg.audio_path)))
            animated_clips.append(clip)

    # Step 4: Combine all scenes
    console.print("\n[bold]Step 4: Combining scenes...[/bold]")
    if animated_clips:
        final_video = concatenate_videoclips(animated_clips, method="compose")

        # Add background music if provided
        if music:
            console.print("\n[bold]Step 5: Adding background music...[/bold]")
            final_video = add_background_music(final_video, Path(music), music_volume)

        # Write final video
        console.print("\n[bold]Rendering final video...[/bold]")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        final_video.write_videofile(
            str(output_path),
            fps=fps,
            codec='libx264',
            audio_codec='aac',
            preset='medium',
            threads=4
        )

        # Cleanup
        for clip in animated_clips:
            clip.close()

        console.print(Panel.fit(
            f"[bold green]✓ Engaging video created![/bold green]\n\n"
            f"📁 Output: {output_path.absolute()}\n\n"
            f"Features:\n"
            f"  ✓ Cursor movement synced with narration\n"
            f"  ✓ Text highlighting effects\n"
            f"  ✓ Subtle zoom on key areas\n"
            f"  ✓ {tts_engine.upper()} voiceover",
            border_style="green"
        ))
    else:
        console.print("[red]No clips were created![/red]")


@cli.command("post")
@click.argument("input_video", type=click.Path(exists=True), metavar="INPUT_VIDEO")
@click.option("-o", "--output", default=None, help="Output file (default: {input}_post.mp4)")
@click.option("--video-speed", default=1.0, type=float, help="Playback speed (0.5=half, 2.0=double, default: 1.0)")
@click.option("--voice-volume", default=None, type=float, help="Voice volume (requires voice track or manifest)")
@click.option("--music-volume", default=None, type=float, help="Music volume (requires music track or manifest)")
@click.option("--volume", default=None, type=float, help="Overall audio volume (simple mode)")
@click.option("--voice-audio", type=click.Path(exists=True), default=None, help="Voice-only audio file for remixing")
@click.option("--music-audio", type=click.Path(exists=True), default=None, help="Music file for remixing")
@click.option("--mix", default=None, metavar="SPEED,V_VOL,M_VOL",
              help="Shorthand: speed,voice-vol,music-vol (e.g., '1.2,6.0,0.04')")
@click.option("--extract-audio/--no-extract-audio", default=True, help="Extract MP3 alongside output (default: yes)")
def post(
    input_video: str,
    output: Optional[str],
    video_speed: float,
    voice_volume: Optional[float],
    music_volume: Optional[float],
    volume: Optional[float],
    voice_audio: Optional[str],
    music_audio: Optional[str],
    mix: Optional[str],
    extract_audio: bool,
):
    """
    Post-process a video: adjust speed, voice volume, and music volume.

    Works in two modes:

    \b
    Simple mode (default):
      Adjust overall audio volume and/or video speed on the mixed audio track.
      Use --volume and --video-speed.

    \b
    Remix mode:
      Re-mix separate voice and music tracks at new volumes.
      Requires voice/music files via --voice-audio/--music-audio flags,
      or auto-discovered from a pipeline manifest (saved by `create`).
      Use --voice-volume and --music-volume.

    \b
    Arguments:
        INPUT_VIDEO    The video file to post-process

    \b
    Examples:
        # Speed up 20%
        python cli.py post output.mp4 --video-speed 1.2

        # Overall volume boost (no video re-encode)
        python cli.py post output.mp4 --volume 2.0

        # Shorthand — auto-discovers manifest for voice/music tracks
        python cli.py post output.mp4 --mix 1.2,8.0,0.05

        # Explicit remix with separate tracks
        python cli.py post output.mp4 \\
            --voice-audio voice_track.mp3 \\
            --music-audio background.mp3 \\
            --voice-volume 8.0 --music-volume 0.05

        # Speed change + custom output path
        python cli.py post output.mp4 --video-speed 0.8 -o slow_version.mp4

    \b
    Notes:
        The `create` command saves a manifest JSON alongside its output.
        When you run `post` on that video, it auto-discovers the manifest
        and can remix voice/music independently without extra flags.

        Volume-only changes use -c:v copy (no video re-encode = fast).
        Speed changes require video re-encoding.
    """
    from src.processing.post_processor import adjust_video, load_manifest

    input_path = Path(input_video)

    # Default output: {stem}_post.mp4
    if output is None:
        output_path = input_path.with_name(f"{input_path.stem}_post{input_path.suffix}")
    else:
        output_path = Path(output)

    # ── Parse --mix shorthand ──
    if mix:
        try:
            parts = [p.strip() for p in mix.split(",")]
            if len(parts) != 3:
                raise ValueError("expected 3 values")
            video_speed = float(parts[0])
            voice_volume = float(parts[1])
            music_volume = float(parts[2])
            console.print(f"[dim]--mix applied: speed={video_speed}, voice-vol={voice_volume}, music-vol={music_volume}[/dim]")
        except (ValueError, IndexError) as e:
            console.print(f"[red]Error: --mix must be 3 comma-separated numbers: speed,voice-vol,music-vol (e.g., '1.2,6.0,0.04')[/red]")
            console.print(f"[red]Got: \"{mix}\" — {e}[/red]")
            sys.exit(1)

    # ── Auto-discover manifest ──
    manifest_path = input_path.with_name(f"{input_path.stem}_manifest.json")
    manifest = load_manifest(manifest_path)

    effective_voice_audio = Path(voice_audio) if voice_audio else None
    effective_music_audio = Path(music_audio) if music_audio else None

    if manifest and not voice_audio:
        # Auto-populate from manifest
        if manifest.get("pre_music_video") and Path(manifest["pre_music_video"]).exists():
            effective_voice_audio = Path(manifest["pre_music_video"])
            console.print(f"[dim]Manifest: using voice track from {effective_voice_audio.name}[/dim]")
        if manifest.get("music_file") and not music_audio and Path(manifest["music_file"]).exists():
            effective_music_audio = Path(manifest["music_file"])
            console.print(f"[dim]Manifest: using music from {effective_music_audio.name}[/dim]")

    # ── Determine mode ──
    remix_mode = (voice_volume is not None or music_volume is not None) and effective_voice_audio is not None

    if (voice_volume is not None or music_volume is not None) and effective_voice_audio is None:
        console.print("[yellow]Warning: --voice-volume/--music-volume require voice/music tracks or a manifest.[/yellow]")
        console.print("[yellow]Falling back to --volume (simple mode). Use --voice-audio/--music-audio to provide tracks.[/yellow]")
        if volume is None:
            volume = voice_volume or 1.0
        remix_mode = False

    # ── Display plan ──
    has_speed = abs(video_speed - 1.0) > 0.01
    adjustments = []
    if has_speed:
        adjustments.append(f"Speed: {video_speed:.2f}x")
    if remix_mode:
        adjustments.append(f"Voice volume: {voice_volume or 5.0}")
        adjustments.append(f"Music volume: {music_volume or 0.03}")
        if not has_speed:
            adjustments.append("No video re-encode (fast)")
    elif volume is not None:
        adjustments.append(f"Volume: {volume:.2f}x")
        if not has_speed:
            adjustments.append("No video re-encode (fast)")

    mode_label = "Remix" if remix_mode else "Simple"
    console.print(Panel.fit(
        f"[bold blue]Post-Processing ({mode_label} mode)[/bold blue]\n\n"
        f"  Input:  {input_path.name}\n"
        f"  Output: {output_path.name}\n"
        + ("\n".join(f"  {a}" for a in adjustments) if adjustments else "  No adjustments"),
        border_style="blue"
    ))

    if not adjustments:
        console.print("[yellow]Nothing to do. Specify --video-speed, --volume, --voice-volume, or --mix.[/yellow]")
        return

    # ── Run post-processing ──
    try:
        if remix_mode:
            result = adjust_video(
                input_video=input_path,
                output_video=output_path,
                video_speed=video_speed,
                voice_audio=effective_voice_audio,
                music_audio=effective_music_audio,
                voice_volume=voice_volume or 5.0,
                music_volume=music_volume or 0.03,
                extract_audio=extract_audio,
            )
        else:
            result = adjust_video(
                input_video=input_path,
                output_video=output_path,
                video_speed=video_speed,
                overall_volume=volume,
                extract_audio=extract_audio,
            )

        console.print(Panel.fit(
            f"[bold green]Post-processing complete![/bold green]\n\n"
            f"Output: {result.absolute()}",
            border_style="green"
        ))
    except Exception as e:
        console.print(f"[red]Error during post-processing: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)


@cli.command("avatar")
@click.argument("input_video", type=click.Path(exists=True), metavar="INPUT_VIDEO")
@click.argument("avatar_image", type=click.Path(exists=True), metavar="AVATAR")
@click.option("-o", "--output", default=None, help="Output file (default: {input}_avatar.mp4)")
@click.option("--position", default="bottom-right",
              type=click.Choice(["top-left", "top-right", "bottom-left", "bottom-right"]),
              help="Corner position (default: bottom-right)")
@click.option("--scale", default=0.15, type=float,
              help="Avatar size as fraction of video width (default: 0.15 = 15%%)")
@click.option("--margin", default=20, type=int, help="Pixel margin from edges (default: 20)")
@click.option("--opacity", default=1.0, type=float, help="Avatar opacity 0.0-1.0 (default: 1.0, images only)")
def avatar(
    input_video: str,
    avatar_image: str,
    output: Optional[str],
    position: str,
    scale: float,
    margin: int,
    opacity: float,
):
    """
    Overlay an avatar image or video in a corner of your video.

    \b
    Examples:
        # Add avatar to bottom-right corner
        python cli.py avatar video.mp4 avatar.png

        # Top-left, larger, with some transparency
        python cli.py avatar video.mp4 face.png --position top-left --scale 0.2 --opacity 0.8

        # Video avatar (e.g., talking head) in bottom-right
        python cli.py avatar video.mp4 talking_head.mp4 --scale 0.25

        # Custom output path
        python cli.py avatar video.mp4 avatar.png -o final_with_avatar.mp4
    """
    from pathlib import Path
    from rich.panel import Panel

    input_path = Path(input_video)
    avatar_path = Path(avatar_image)

    if output:
        output_path = Path(output)
    else:
        output_path = input_path.with_name(f"{input_path.stem}_avatar.mp4")

    console.print(Panel.fit(
        f"[bold blue]Avatar Overlay[/bold blue]\n\n"
        f"  Video:    {input_path.name}\n"
        f"  Avatar:   {avatar_path.name}\n"
        f"  Position: {position}\n"
        f"  Scale:    {int(scale * 100)}%\n"
        f"  Opacity:  {opacity}\n"
        f"  Output:   {output_path.name}",
        border_style="blue"
    ))

    try:
        from src.processing.avatar_overlay import overlay_avatar

        result = overlay_avatar(
            input_video=input_path,
            avatar_source=avatar_path,
            output_video=output_path,
            position=position,
            scale=scale,
            margin=margin,
            opacity=opacity,
        )

        console.print(Panel.fit(
            f"[bold green]Avatar overlay complete![/bold green]\n\n"
            f"Output: {result.absolute()}",
            border_style="green"
        ))
    except Exception as e:
        console.print(f"[red]Error during avatar overlay: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)


@cli.command("blend")
@click.argument("input_path", type=click.Path(exists=True))
@click.option("-o", "--output", default="blended/", help="Output directory for numbered files")
@click.option("--sequence", type=click.Path(exists=True), help="Markdown file or folder of .md files with file references")
@click.option("--bookend", type=click.Path(exists=True), help="Image used as first and last frame")
@click.option("--include-unsequenced/--exclude-unsequenced", default=True,
              help="Include files not in sequence file (default: include)")
@click.option("--ai-order/--no-ai-order", default=True,
              help="Use Gemini Vision to determine optimal order for unsequenced files")
@click.option("--context", default="", help="Product/service context for AI ordering")
@click.option("--tone", default="professional and engaging", help="Tone for AI ordering")
@click.option("--storyline", default="", help="Storyline to guide AI ordering")
@click.option("--dry-run", is_flag=True, help="Show plan without copying files")
def blend(
    input_path: str,
    output: str,
    sequence: Optional[str],
    bookend: Optional[str],
    include_unsequenced: bool,
    ai_order: bool,
    context: str,
    tone: str,
    storyline: str,
    dry_run: bool,
):
    """
    Blend assets from multiple folders into a numbered sequence for video creation.

    Scans INPUT_PATH recursively for images and videos, optionally follows a
    markdown sequence file for ordering, and copies everything into a single
    output directory with zero-padded filenames ready for `python cli.py create`.

    \b
    Pipeline:
    1. Recursively scan INPUT_PATH for all image/video files
    2. If --sequence: parse file references from .md file or folder of .md files
    3. Fuzzy-match references to found files, order the rest with Gemini Vision AI
    4. If --bookend: place it as first and last frame
    5. Copy to OUTPUT with 00-name, 01-name, ... naming

    \b
    Examples:
        # With sequence folder of .md files + bookend
        python cli.py blend ./project/ -o blended/ \\
            --sequence ./sequence-docs/ --bookend logo.png

        # With a single sequence file
        python cli.py blend ./project/ -o blended/ \\
            --sequence scene-shotlist.md --bookend logo.png

        # AI-only ordering (no sequence file)
        python cli.py blend ./mixed_assets/ -o blended/ \\
            --storyline "From problem to solution"

        # Dry run to preview
        python cli.py blend ./project/ -o blended/ \\
            --sequence ./sequence-docs/ --dry-run

        # Then create video from blended output
        python cli.py create ./blended/ -o video.mp4 --voice "Venkat"
    """
    from src.pipeline.blend_handler import blend_content

    console.print(Panel.fit(
        "[bold blue]Content Blender[/bold blue]\n"
        f"Input: {input_path} | Output: {output}"
        + (f"\nSequence: {sequence}" if sequence else "")
        + (f"\nBookend: {bookend}" if bookend else "")
        + (f"\nStoryline: {storyline}" if storyline else ""),
        border_style="blue"
    ))

    blend_content(
        input_path=Path(input_path),
        output_dir=Path(output),
        sequence_path=Path(sequence) if sequence else None,
        bookend_path=Path(bookend) if bookend else None,
        include_unsequenced=include_unsequenced,
        ai_order=ai_order,
        context=context,
        tone=tone,
        storyline=storyline,
        dry_run=dry_run,
    )


@cli.command("storyboard")
@click.argument("urls", nargs=-1, required=True, metavar="URL...")
@click.option("-o", "--output", default="storyboard_output/", help="Output directory for storyboard assets")
@click.option("--storyline", default="", help="Narrative storyline for the video")
@click.option("--storyline-file", type=click.Path(exists=True), help="Read storyline from a text file")
@click.option("--scenes", default=6, type=int, help="Number of scenes to plan (default: 6)")
@click.option("--product", default="", help="Product/service name")
@click.option("--context", default="", help="Additional product/service context")
@click.option("--tone", default="professional and engaging", help="Script tone")
@click.option("--style", type=click.Choice(["marketing", "feature-explainer", "tutorial-explainer", "instagram-shorts"]),
              default="marketing", help="Video style profile")
@click.option("--aspect-ratio", default="16:9", help="Aspect ratio for Imagen images (default: 16:9)")
@click.option("--skip-imagen", is_flag=True, help="Skip AI image generation (screenshots only)")
@click.option("--skip-screenshots", is_flag=True, help="Skip website screenshots (Imagen only)")
@click.option("--login", is_flag=True, help="Open browser for manual login before crawling (for auth-required sites)")
@click.option("--dry-run", is_flag=True, help="Show scene plan without generating assets")
def storyboard(
    urls: tuple,
    output: str,
    storyline: str,
    storyline_file: Optional[str],
    scenes: int,
    product: str,
    context: str,
    tone: str,
    style: str,
    aspect_ratio: str,
    skip_imagen: bool,
    skip_screenshots: bool,
    login: bool,
    dry_run: bool,
):
    """
    Plan a video storyboard from one or more website URLs + storyline.

    Captures the website(s), plans scenes with AI, generates screenshots and
    AI images, then assembles a numbered sequence ready for `create`.

    \b
    Pipeline:
    Phase 1: Full-page website screenshot (Playwright) — crawls each URL
    Phase 2: AI scene planning (Gemini Vision)
    Phase 3: Website section screenshots
    Phase 4: Imagen 3.0 image generation
    Phase 5: Assemble numbered sequence

    \b
    Arguments:
        URL...    One or more website URLs to capture and analyze

    \b
    Output Structure:
        storyboard_output/
        ├── storyboard.txt           # Scene breakdown
        ├── website_full.png         # Full-page capture
        ├── screenshots/             # Website section crops
        ├── generated/               # Imagen-generated images
        └── sequence/                # Final numbered sequence

    \b
    Examples:
        # Full storyboard
        python cli.py storyboard https://example.com \\
            --storyline "From chaos to clarity" \\
            --scenes 8 --product "My App"

        # From storyline file
        python cli.py storyboard https://example.com \\
            --storyline-file story.txt --scenes 9

        # Preview plan only
        python cli.py storyboard https://example.com \\
            --storyline "AI transforms compliance" --dry-run

        # Screenshots only (no Imagen)
        python cli.py storyboard https://example.com \\
            --storyline "Product demo" --skip-imagen

        # Then create video from the storyboard
        python cli.py create storyboard_output/sequence/ \\
            -o video.mp4 --storyline-file story.txt

    \b
    Required API Keys:
    • GOOGLE_API_KEY (Gemini Vision + Imagen 3.0)
    """
    from src.pipeline.website_screenshotter import crawl_and_capture_sync
    from src.pipeline.storyboard_planner import plan_storyboard, write_storyboard_text

    # ── Read storyline ──
    if storyline_file:
        storyline = Path(storyline_file).read_text(encoding="utf-8").strip()
        console.print(f"[dim]Read storyline from {storyline_file} ({len(storyline)} chars)[/dim]")

    if not storyline:
        console.print("[red]Error: Provide --storyline or --storyline-file[/red]")
        sys.exit(1)

    # ── Normalize URLs ──
    normalized_urls = []
    for u in urls:
        if not u.startswith("http://") and not u.startswith("https://"):
            u = "https://" + u
        normalized_urls.append(u)
    # Keep first URL as primary for display/planning
    url = normalized_urls[0]

    # ── Check API key ──
    if not os.getenv("GOOGLE_API_KEY"):
        console.print("[red]Error: GOOGLE_API_KEY not set.[/red]")
        sys.exit(1)

    output_dir = Path(output)
    full_context = context
    if product:
        full_context = f"Product: {product}. {context}" if context else f"Product: {product}"

    urls_display = "\n".join(f"  URL: {u}" for u in normalized_urls)
    console.print(Panel.fit(
        "[bold blue]Storyboard Planner[/bold blue]\n\n"
        f"{urls_display}\n"
        f"  Scenes: {scenes}\n"
        f"  Style: {style} | Tone: {tone}\n"
        + (f"  Product: {product}\n" if product else "")
        + f"  Storyline: {storyline[:80]}{'...' if len(storyline) > 80 else ''}\n"
        f"  Output: {output_dir}/",
        border_style="blue"
    ))

    # ── Login (if needed) ──
    auth_state = None
    if login and not skip_screenshots:
        from src.pipeline.website_screenshotter import login_and_save_auth_sync, AUTH_STATE_FILE
        google_email = os.getenv("GOOGLE_EMAIL", "")
        google_password = os.getenv("GOOGLE_PASSWORD", "")
        if google_email and google_password:
            console.print(f"\n[bold yellow]Login: Auto sign-in with {google_email}...[/bold yellow]")
        else:
            console.print(f"\n[bold yellow]Login: Opening browser — sign in manually...[/bold yellow]")
            console.print(f"[dim]Tip: Set GOOGLE_EMAIL and GOOGLE_PASSWORD env vars for auto sign-in[/dim]")
        try:
            auth_state = login_and_save_auth_sync(url, google_email, google_password)
            console.print(f"[green]Auth saved — future runs will reuse it (use --login again to refresh)[/green]")
        except Exception as e:
            console.print(f"[red]Login failed: {e}[/red]")
            sys.exit(1)
    elif not login and not skip_screenshots:
        # Check for existing saved auth
        from src.pipeline.website_screenshotter import AUTH_STATE_FILE
        if AUTH_STATE_FILE.exists():
            auth_state = AUTH_STATE_FILE
            console.print(f"[dim]Using saved auth from {AUTH_STATE_FILE}[/dim]")

    # ── Phase 1: Crawl website(s) — scroll + click all nav links ──
    screenshots_dir = output_dir / "screenshots"
    all_captures = []
    capture_labels = []

    if not skip_screenshots:
        console.print(f"\n[bold cyan]Phase 1: Crawling {len(normalized_urls)} URL(s) (scroll + nav clicks)...[/bold cyan]")
        output_dir.mkdir(parents=True, exist_ok=True)

        for url_idx, crawl_url in enumerate(normalized_urls):
            console.print(f"  [cyan]Crawling [{url_idx + 1}/{len(normalized_urls)}]: {crawl_url}[/cyan]")
            # Use subdirectory per URL when multiple URLs to avoid filename collisions
            if len(normalized_urls) > 1:
                from urllib.parse import urlparse as _urlparse
                _domain = _urlparse(crawl_url).netloc.replace(".", "_")
                url_screenshots_dir = screenshots_dir / f"{url_idx:02d}_{_domain}"
            else:
                url_screenshots_dir = screenshots_dir
            try:
                all_captures_obj = crawl_and_capture_sync(
                    crawl_url, url_screenshots_dir, aspect_ratio=aspect_ratio,
                    auth_state=auth_state,
                )
                for cap in all_captures_obj:
                    all_captures.append(cap.path)
                    capture_labels.append(cap.label)
                console.print(f"  [green]{len(all_captures_obj)} screenshots from {crawl_url}[/green]")
            except Exception as e:
                console.print(f"  [red]Failed to crawl {crawl_url}: {e}[/red]")
                if url_idx == 0:
                    console.print("[yellow]Tip: Run 'python -m playwright install chromium' if browser not installed[/yellow]")
                    sys.exit(1)
                else:
                    console.print(f"  [yellow]Continuing with remaining URLs...[/yellow]")

        console.print(f"[green]Phase 1 complete: {len(all_captures)} total screenshots captured[/green]")
    else:
        console.print(f"\n[dim]Phase 1: Skipped (--skip-screenshots)[/dim]")
        output_dir.mkdir(parents=True, exist_ok=True)

    if not all_captures and not skip_screenshots:
        console.print("[red]No screenshots captured. Cannot plan storyboard.[/red]")
        sys.exit(1)

    # ── Phase 2: AI scene planning — Gemini sees ALL captures ──
    console.print(f"\n[bold cyan]Phase 2: Planning {scenes} scenes with Gemini Vision ({len(all_captures)} captures)...[/bold cyan]")

    try:
        sb = plan_storyboard(
            storyline=storyline,
            url=" , ".join(normalized_urls),
            captures=all_captures,
            capture_labels=capture_labels,
            num_scenes=scenes,
            product=product,
            context=full_context,
            tone=tone,
            style=style,
        )
    except Exception as e:
        console.print(f"[red]Scene planning failed: {e}[/red]")
        sys.exit(1)

    # Write storyboard text
    storyboard_txt = write_storyboard_text(sb, output_dir / "storyboard.txt")
    console.print(f"[green]Phase 2 complete: {len(sb.scenes)} scenes planned[/green]")

    # Display scene table
    table = Table(title="Storyboard Scenes", show_header=True)
    table.add_column("#", style="cyan", width=3)
    table.add_column("Title", style="blue", width=18)
    table.add_column("Capture", style="green", width=10)
    table.add_column("Script", style="white", max_width=50)

    for scene in sb.scenes:
        cap_label = f"#{scene.best_capture_index}" if scene.best_capture_index >= 0 else "none"
        table.add_row(
            str(scene.scene_number),
            scene.title,
            cap_label,
            scene.voiceover_script[:95] + "..." if len(scene.voiceover_script) > 95 else scene.voiceover_script,
        )

    console.print(table)

    if dry_run:
        console.print(f"\n[yellow]DRY RUN — plan saved to {storyboard_txt}[/yellow]")
        console.print("[dim]Remove --dry-run to generate screenshots and images[/dim]")
        return

    # ── Phase 3: Generate Imagen images for ALL scenes ──
    generated_dir = output_dir / "generated"
    generated_images = {}

    if not skip_imagen:
        from src.ai.imagen_generator import generate_image

        console.print(f"\n[bold cyan]Phase 3: Generating {len(sb.scenes)} Imagen images...[/bold cyan]")
        generated_dir.mkdir(parents=True, exist_ok=True)

        _style_prefixes = [
            "Cinematic shot, holographic dashboard floating above a clean white desk, soft blue ambient glow, minimal background.",
            "Close-up detail, transparent tablet displaying live data analytics, warm amber tones, shallow depth of field, clean workspace.",
            "Medium shot, floating 3D data visualization rotating in mid-air, soft purple and magenta lighting, dark minimal background.",
            "Eye-level shot, sleek transparent monitor on a minimal desk showing real-time metrics, emerald green accent lighting.",
            "Wide shot, multiple holographic panels arranged in an arc displaying charts and graphs, cool blue tones, soft diffused light.",
            "Over-the-shoulder of one person interacting with a floating holographic interface, clean modern office, golden hour light.",
            "Top-down shot, digital whiteboard surface with AI-generated diagrams and flowcharts glowing softly, cool teal palette.",
            "Medium shot, robotic arm precisely assembling a device on a clean lab bench, soft white lighting, minimal setting.",
            "Bright inviting shot, a single holographic notification floating in a sunlit modern room, warm golden tones, minimal decor.",
            "Macro close-up, fingertips swiping through a translucent data interface, soft cyan highlights, dark blurred background.",
        ]

        for scene in sb.scenes:
            slug = re.sub(r'[^\w\s-]', '', scene.title.lower())
            slug = re.sub(r'[\s_-]+', '_', slug).strip('_')[:40]
            filename = f"scene_{scene.scene_number:03d}_{slug}.png"
            filepath = generated_dir / filename

            prefix = _style_prefixes[(scene.scene_number - 1) % len(_style_prefixes)]
            # Extract key phrases from storyline (first 120 chars) + product for context
            story_context = storyline[:120].rstrip()
            product_tag = f", related to {product}" if product else ""
            imagen_prompt = f"{prefix} {scene.image_description} Context: {story_context}{product_tag}."

            console.print(f"  Generating scene {scene.scene_number} ({scene.title})...")
            try:
                generate_image(
                    prompt=imagen_prompt,
                    output_path=filepath,
                    aspect_ratio=aspect_ratio,
                )
                generated_images[scene.scene_number] = filepath
                console.print(f"  [green]Scene {scene.scene_number}:[/green] {filepath.name}")
            except Exception as e:
                console.print(f"  [yellow]Scene {scene.scene_number} failed: {e}[/yellow]")

        console.print(f"[green]Phase 3 complete: {len(generated_images)}/{len(sb.scenes)} images generated[/green]")
    else:
        console.print(f"\n[dim]Phase 3: Skipped (--skip-imagen)[/dim]")

    # ── Phase 4: Assemble sequence folder (both screenshots + generated) ──
    console.print(f"\n[bold cyan]Phase 4: Assembling sequence folder...[/bold cyan]")
    import shutil

    sequence_dir = output_dir / "sequence"
    sequence_dir.mkdir(parents=True, exist_ok=True)

    assembled = 0
    for scene in sb.scenes:
        slug = re.sub(r'[^\w\s-]', '', scene.title.lower())
        slug = re.sub(r'[\s_-]+', '_', slug).strip('_')[:40]

        # Copy screenshot if available
        if scene.best_capture_index >= 0 and scene.best_capture_index < len(all_captures):
            src_path = all_captures[scene.best_capture_index]
            if src_path.exists():
                ss_dest = sequence_dir / f"{scene.scene_number:03d}_{slug}_screenshot.png"
                shutil.copy2(str(src_path), str(ss_dest))
                console.print(f"  {ss_dest.name} <- capture #{scene.best_capture_index}")
                assembled += 1

        # Copy generated image if available
        if scene.scene_number in generated_images:
            gen_src = generated_images[scene.scene_number]
            gen_dest = sequence_dir / f"{scene.scene_number:03d}_{slug}_generated.png"
            shutil.copy2(str(gen_src), str(gen_dest))
            console.print(f"  {gen_dest.name} <- generated")
            assembled += 1

        if (scene.best_capture_index < 0 or scene.best_capture_index >= len(all_captures)) \
                and scene.scene_number not in generated_images:
            console.print(f"  [yellow]Scene {scene.scene_number} ({scene.title}): no visual available[/yellow]")

    console.print(f"[green]Phase 4 complete: {assembled} files for {len(sb.scenes)} scenes assembled[/green]")

    # ── Summary ──
    num_screenshots_used = sum(1 for s in sb.scenes if 0 <= s.best_capture_index < len(all_captures))
    console.print(Panel.fit(
        f"[bold green]Storyboard complete![/bold green]\n\n"
        f"  Storyboard: {storyboard_txt}\n"
        f"  Captures: {len(all_captures)} total in {screenshots_dir}/\n"
        f"  Screenshots used: {num_screenshots_used} (picked by Gemini)\n"
        f"  Generated: {len(generated_images)} in {generated_dir}/\n"
        f"  Sequence: {assembled} files in {sequence_dir}/\n\n"
        f"  Create video:\n"
        f"    python cli.py create {sequence_dir}/ -o video.mp4"
        + (f" \\\n        --storyline-file {storyline_file}" if storyline_file else "")
        + (f" \\\n        --product \"{product}\"" if product else ""),
        border_style="green"
    ))


@cli.command("test-script")
@click.option("--storyline", default="", help="Narrative storyline (short text)")
@click.option("--storyline-file", type=click.Path(exists=True), help="Read storyline from a text file")
@click.option("--scenes", default=5, type=int, help="Number of scenes (default: 5)")
@click.option("--images", default=0, type=int, help="Number of images (for context in prompt)")
@click.option("--context", default="", help="Product/service context")
@click.option("--product", default="", help="Product name")
@click.option("--tone", default="bold, confident, high-stakes", help="Pitch tone")
def test_script(storyline: str, storyline_file: str, scenes: int, images: int, context: str, product: str, tone: str):
    """
    Test pitch/script generation without running the full video pipeline.

    \b
    Quickly iterate on script quality:
      python cli.py test-script --storyline-file story.txt --scenes 9
      python cli.py test-script --storyline "SOC2 compliance" --scenes 5 --product "AuditBot"
    """
    import re
    from src.pipeline.veo_pipeline import generate_pitch_from_storyline

    # Read storyline from file if provided
    if storyline_file:
        storyline = Path(storyline_file).read_text(encoding="utf-8").strip()
        console.print(f"[dim]Read storyline from {storyline_file} ({len(storyline)} chars)[/dim]")

    if not storyline:
        console.print("[red]Error: Provide --storyline or --storyline-file[/red]")
        return

    console.print(Panel.fit(
        f"[bold blue]Script Test[/bold blue]\n"
        f"Storyline: {storyline[:200]}{'...' if len(storyline) > 200 else ''}\n"
        f"Scenes: {scenes} | Images: {images} | Tone: {tone}"
        + (f"\nProduct: {product}" if product else "")
        + (f"\nContext: {context}" if context else ""),
        border_style="blue"
    ))

    try:
        pitch = generate_pitch_from_storyline(
            storyline=storyline,
            num_scenes=scenes,
            num_images=images,
            context=context,
            tone=tone,
            product=product,
        )
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        return

    if not pitch:
        console.print("\n[red]Pitch generation failed — no output.[/red]")
        return

    # Split and display
    sentences = [s.strip() for s in pitch.strip().split("\n") if s.strip()]

    console.print(f"\n[bold green]PITCH ({len(sentences)} sentences):[/bold green]")
    console.print("=" * 60)

    total_words = 0
    for i, sentence in enumerate(sentences):
        wc = len(sentence.split())
        total_words += wc
        duration = round(wc / 2.5, 1)
        console.print(f"\n[bold]Scene {i+1}[/bold] ({wc} words, ~{duration}s):")
        console.print(f"  {sentence}")

    console.print("\n" + "=" * 60)
    console.print(f"[bold]Total: {total_words} words, ~{round(total_words / 2.5)}s[/bold]")


@cli.command("shorts")
@click.argument("input_video", type=click.Path(exists=True))
@click.option("-o", "--output", default="short.mp4", help="Output path")
@click.option("--resolution", type=click.Choice(["720p", "1080p", "4k"]), default="1080p")
@click.option("--captions/--no-captions", default=False, help="Burn karaoke captions")
@click.option("--music/--no-music", default=True, help="Generate background music (default: on)")
@click.option("--music-prompt", default="", help="Custom music prompt (auto-generated if empty)")
@click.option("--music-volume", default=0.15, type=float, help="Background music volume (0.0-1.0, default: 0.15)")
@click.option("--target-duration", default=45, type=int, help="Target duration in seconds (default: 45)")
@click.option("--enhance/--no-enhance", default=True, help="AI scene enhancement with split-screen visuals (default: on)")
def shorts(input_video: str, output: str, resolution: str, captions: bool, music: bool, music_prompt: str, music_volume: float, target_duration: int, enhance: bool):
    """
    Create an Instagram Short from a longer video.

    \b
    AI extracts the most impactful moments, trims and merges them
    into a highlight reel with background music. Scene enhancement
    generates split-screen or full-screen AI visuals to illustrate
    what the speaker is describing.

    \b
    Examples:
      python cli.py shorts long_video.mp4 -o short.mp4
      python cli.py shorts interview.mov --captions --target-duration 40
      python cli.py shorts talk.mp4 --music-prompt "lo-fi chill beats" --music-volume 0.2
      python cli.py shorts talk.mp4 --no-enhance  # skip AI scene generation
    """
    from pathlib import Path
    from src.pipeline.shorts_pipeline import create_instagram_short

    create_instagram_short(
        input_video=Path(input_video),
        output_path=Path(output),
        resolution=resolution,
        captions=captions,
        target_duration=target_duration,
        generate_music=music,
        music_prompt=music_prompt,
        music_volume=music_volume,
        enhance_scenes=enhance,
    )


@cli.command()
def info():
    """
    Show comprehensive setup guide and usage examples.

    \b
    Displays:
    • Quick start guide
    • API key setup instructions
    • Complete examples for all commands
    • Tips and best practices
    """
    info_text = """
# 🎬 Marketing Video Generator - Complete Guide

## 🚀 Quick Start (Free Tier)

1. **Set API Keys:**
   ```bash
   export GOOGLE_API_KEY="your_google_key"          # Required for Gemini Vision + Veo 3.1
   export ELEVENLABS_API_KEY="your_eleven_key"      # Optional, for premium voices
   ```

2. **Prepare Content:**
   - Create a folder with your media files
   - Name them in order: `01_intro.png`, `02_demo.mp4`, `03_slides.pptx`
   - Mix any combination of images, videos, PowerPoint, PDF

3. **Generate Your First Video (Free):**
   ```bash
   python cli.py generate ./content/ -o output.mp4
   ```

---

## 📋 Available Commands

### 🎥 Video Generation

**`generate`** - Create marketing video from any content
```bash
python cli.py generate ./content/ -o video.mp4 --product "My App"
```

**`veo-marketing`** - Premium animated videos with Veo 3.1
```bash
python cli.py veo-marketing ./images/ -o marketing.mp4 --voice "Smritika"
```

**`engage`** - Videos with cursor movement & highlights
```bash
python cli.py engage ./screenshots/ -o engaging.mp4
```

### 🎙️ Voice & Audio

**`voices`** - List all available TTS voices
```bash
python cli.py voices --engine elevenlabs
```

**`voice-clone`** - Clone your own voice
```bash
python cli.py voice-clone "My Voice" sample.mp3
```

**`music`** - Generate AI background music
```bash
python cli.py music -o bg.mp3 --prompt "upbeat corporate"
```

---

## 💡 Common Use Cases

### Basic Marketing Video (FREE)
```bash
python cli.py generate ./screenshots/ -o demo.mp4 \\
    --product "My SaaS App" \\
    --tone "friendly and conversational" \\
    --tts-engine edge \\
    --voice "en-US-GuyNeural"
```

### Premium Quality with Veo 3.1 Animation
```bash
python cli.py veo-marketing ./product_shots/ -o premium.mp4 \\
    --voice "Smritika" \\
    --product "AI Video Tool" \\
    --context "SaaS for content creators" \\
    --tone "energetic and exciting" \\
    --music background.mp3 \\
    --resolution 1080p
```

### From PowerPoint Presentation
```bash
python cli.py veo-marketing ./pitch.pptx -o pitch_video.mp4 \\
    --voice "Aman" \\
    --product "My Startup" \\
    --tone "professional"
```

### Mixed Content (Images + Videos + PPT)
```bash
python cli.py generate ./mixed_content/ -o complete.mp4 \\
    --product "Complete Product Demo" \\
    --generate-music \\
    --music-prompt "upbeat tech background"
```

### Voice Cloning Workflow
```bash
# Step 1: Clone your voice
python cli.py voice-clone "My Voice" recording.mp3 \\
    --accent "Indian" --gender "male"

# Step 2: Use cloned voice in video
python cli.py veo-marketing ./content/ -o personal.mp4 \\
    --tts-engine elevenlabs \\
    --voice "My Voice"
```

---

## 🎯 Pro Tips

- **Naming:** Use numbered prefixes (01_, 02_) for correct order
- **Preview:** Use `--script-only` to preview before generating
- **Quality:** Use `--resolution 1080p` or `4k` for best quality
- **Voice:** Run `python cli.py voices` to see all options
- **Music:** Keep `--music-volume` low (0.03-0.08) to prioritize voice
- **Voice Volume:** Increase `--voice-volume 6.0-8.0` if voice too quiet

---

## 📁 Supported File Types

| Type | Extensions | Processing |
|------|-----------|------------|
| **Images** | .png, .jpg, .jpeg, .webp, .gif, .bmp | Analyzed & animated |
| **PowerPoint** | .pptx, .ppt | Each slide becomes a scene |
| **Documents** | .pdf | Each page becomes a scene |
| **Videos** | .mp4, .mov, .avi, .mkv | Cleaned & transcribed |

---

## 🔑 API Keys

Get your keys from:
- **Google (Gemini Vision + Veo 3.1):** https://ai.google.dev/
- **ElevenLabs (Voice):** https://elevenlabs.io/

---

## 📚 More Help

For detailed help on any command:
```bash
python cli.py COMMAND --help
```

Examples:
```bash
python cli.py generate --help
python cli.py veo-marketing --help
python cli.py voice-clone --help
```
"""
    console.print(Markdown(info_text))


if __name__ == "__main__":
    cli()
