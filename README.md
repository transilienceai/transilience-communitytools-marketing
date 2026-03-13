# Marketing Video Generator

AI-powered pipeline that creates professional marketing videos from any combination of images, documents, presentations, and videos — with voice cloning, AI music, and website-to-video storyboarding.

## Features

- **Any Input** — Images, PowerPoint, PDF, videos, or website URLs
- **Veo 3.1 Animation** — Cinematic zoom/pan/drift for static content (5s per scene)
- **Unified Narrative** — One AI call generates cohesive scripts across all scenes with opening hook, natural flow, and closing CTA
- **Voice Cloning** — Clone any voice from an audio sample via ElevenLabs
- **AI Music** — Generate background music (30s loop, auto-repeated to fill video)
- **Storyboard from URL** — Crawl a website, plan scenes with Gemini Vision, generate images with Imagen 4.0
- **Avatar Overlay** — Composite image/video avatars on any corner of the finished video
- **Web UI** — Full browser interface deployed on Modal
- **Video Style Profiles** — marketing, demo, explainer, pitch, tutorial
- **Cost-Effective** — ~$0.25-0.65 per video

## Installation

```bash
pip install -r requirements.txt

# Install Playwright for storyboard website crawling
playwright install chromium
```

### System Requirements

- Python 3.9+
- FFmpeg
  ```bash
  # macOS
  brew install ffmpeg

  # Ubuntu/Debian
  sudo apt install ffmpeg
  ```

### API Keys

```bash
export GOOGLE_API_KEY="..."       # Required — Gemini Vision + Veo 3.1 + Imagen 4.0
export ELEVENLABS_API_KEY="..."   # Optional — Premium TTS, voice cloning, music
```

## Quick Start

```bash
# Simplest — images to video
python cli.py create ./content/ -o video.mp4

# Full production
python cli.py create ./content/ -o video.mp4 \
    --clone-voice "Aman" --clone-from voice_sample.mp3 \
    --generate-music --music-prompt "upbeat corporate" \
    --storyline "A small team discovers AI automation and scales to 10x productivity" \
    --product "My App" --tone "energetic"

# From a website URL
python cli.py storyboard https://example.com \
    --storyline-file story.txt --scenes 9 --product "My App"
python cli.py create storyboard_output/sequence/ -o video.mp4 \
    --ai-order --generate-music --storyline-file story.txt
```

## CLI Commands

### `create` — All-in-one video generation

```bash
python cli.py create INPUT_PATH [OPTIONS]

  -o, --output TEXT              Output video file (default: output.mp4)
  --storyline TEXT               Narrative storyline to guide scripts and animation
  --storyline-file PATH          Read storyline from a text file
  --product TEXT                 Product name
  --tone TEXT                    Script tone (default: professional and engaging)
  --style CHOICE                 marketing|demo|explainer|pitch|tutorial
  --voice TEXT                   TTS voice name (default: Smritika)
  --tts-engine CHOICE            elevenlabs | edge (free)
  --resolution CHOICE            720p | 1080p | 4k (default: 1080p)
  --scene-duration INT           Seconds per Veo scene (default: 5)
  --max-workers INT              Parallel Veo API calls (default: 3)
  --clone-voice NAME             Clone a voice from audio sample
  --clone-from AUDIO_FILE        Audio sample for cloning
  --generate-music               Generate AI background music
  --music-prompt TEXT            Music prompt
  --music PATH                   Pre-existing music file
  --mix SPEED,VOICE,MUSIC        Audio mix shorthand (e.g., "1.2,6.0,0.04")
  --ai-order/--no-ai-order       AI scene ordering (default: ai-order)
  --blend                        Blend assets from subfolders
  --dry-run                      Preview execution plan
```

### `storyboard` — Website to visual assets

```bash
python cli.py storyboard URL [OPTIONS]

  --storyline TEXT / --storyline-file PATH
  --scenes INT                   Number of scenes (default: 6)
  --product TEXT                 Product name
  --style CHOICE                 marketing|demo|explainer|pitch|tutorial
  --skip-imagen                  Screenshots only
  --skip-screenshots             Imagen only
  --login                        Google sign-in for auth-required sites
  --dry-run                      Preview scene plan
```

### `avatar` — Add avatar overlay to a video

```bash
python cli.py avatar video.mp4 avatar.png -o output.mp4 \
    --position bottom-right --scale 0.15 --opacity 1.0 --margin 20
```

### Other commands

```bash
python cli.py veo-marketing ./content/ -o output.mp4    # Video pipeline only
python cli.py generate ./content/ -o video.mp4           # Basic (no Veo)
python cli.py voice-clone "Name" recording.mp3           # Clone a voice
python cli.py music -o bg.mp3 --prompt "upbeat"          # Generate music
python cli.py voices --engine elevenlabs                  # List voices
python cli.py veo image.png --prompt "gentle motion"     # Direct Veo access
python cli.py info                                        # Setup guide
```

## Web UI

Deploy the browser interface on Modal:

```bash
modal deploy modal_app.py
```

Features: drag-and-drop upload, URL-based storyboard, style picker with sample videos, avatar overlay panel, cost estimation, storyline file upload.

## Project Structure

```
video_generator/
├── cli.py                          # CLI entry point (all commands)
├── modal_app.py                    # Web UI (FastAPI on Modal)
├── process_recording.py            # Standalone video processor
├── requirements.txt
├── CLAUDE.md                       # Full architecture docs
├── src/
│   ├── ai/
│   │   ├── gemini_client.py        # Gemini API wrapper
│   │   ├── ai_analyzer.py          # Vision analysis + script generation
│   │   ├── veo_generator.py        # Veo 3.1 video generation
│   │   ├── tts_engine.py           # TTS (ElevenLabs + Edge) + STT
│   │   └── imagen_generator.py     # Imagen 4.0 image generation
│   ├── pipeline/
│   │   ├── veo_pipeline.py         # Main pipeline orchestrator
│   │   ├── screenshot_handler.py   # File loading, PPT/PDF extraction
│   │   ├── blend_handler.py        # Multi-folder blending
│   │   ├── video_assembler.py      # MoviePy video assembly
│   │   ├── storyboard_planner.py   # Gemini Vision scene planning
│   │   └── website_screenshotter.py # Playwright website crawling
│   ├── processing/
│   │   ├── avatar_overlay.py       # FFmpeg avatar compositing
│   │   ├── video_cleaner.py        # Remove still/idle frames
│   │   ├── video_effects.py        # Visual effects
│   │   ├── video_extractors.py     # Frame extraction
│   │   └── post_processor.py       # Post-processing filters
│   ├── core/
│   │   ├── image_utils.py          # Image utilities
│   │   ├── video_utils.py          # Video utilities
│   │   └── audio_utils.py          # Audio utilities
│   └── generators/
│       ├── music_generator.py      # Music generation (multiple engines)
│       └── text_animator.py        # Text animation
└── input_samples/                  # Sample input files
```

## Output

Each run produces up to three files:
- `output.mp4` — Final video (H.264, AAC, 30fps)
- `output.mp3` — Audio track with voice + music (44.1kHz, 192kbps)
- `output_music.mp3` — Background music only (trimmed to video length)

## Technical Stack

- **AI:** Google Gemini Vision, Veo 3.1, Imagen 4.0, ElevenLabs (TTS/STT/cloning/music)
- **Video:** FFmpeg, OpenCV, MoviePy
- **Web:** Playwright, FastAPI, Modal
- **Documents:** python-pptx, pdf2image, Pillow# videogen
