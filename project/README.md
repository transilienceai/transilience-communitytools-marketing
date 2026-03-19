# VideoGen — Running the Pipeline

## Setup

```bash
# 1. Install dependencies (from repo root)
pip install -r requirements.txt

# 2. Install Playwright for website storyboarding
playwright install chromium

# 3. Set API keys
export GOOGLE_API_KEY="your-google-api-key"       # Required
export ELEVENLABS_API_KEY="your-elevenlabs-key"    # Optional — premium TTS, cloning, music
```

## Run Commands

All CLI commands run from `project/videogen/`:

```bash
cd project/videogen
```

### Create a Video (Main Command)

```bash
# Simplest — images to video
python cli.py create ./content/ -o video.mp4

# With storyline + product name
python cli.py create ./content/ -o video.mp4 \
    --storyline "How our platform transforms security operations" \
    --product "Transilience AI" \
    --tone "professional and engaging"

# Full production — voice clone + music + style
python cli.py create ./content/ -o video.mp4 \
    --clone-voice "Aman" --clone-from voice_sample.mp3 \
    --generate-music --music-prompt "upbeat corporate" \
    --storyline "A small team discovers AI automation and scales to 10x productivity" \
    --product "My App" --tone "energetic" --style marketing

# Screen recording with preserved system audio
python cli.py create ./recordings/ -o tutorial.mp4 \
    --style tutorial --storyline "Step-by-step setup guide"

# Preview execution plan without running
python cli.py create ./content/ -o video.mp4 --dry-run
```

### Create Options

```
-o, --output TEXT              Output file (default: output.mp4)
--storyline TEXT               Narrative arc for scripts + animation
--product TEXT                 Product name
--tone TEXT                    Script tone (default: professional and engaging)
--style CHOICE                 marketing | demo | explainer | pitch | tutorial
--resolution CHOICE            720p | 1080p | 4k (default: 1080p)
--voice TEXT                   TTS voice (default: Smritika)
--tts-engine CHOICE            elevenlabs | edge (free)
--clone-voice NAME             Clone a voice from audio sample
--clone-from AUDIO_FILE        Audio sample for cloning
--voice-speed FLOAT            Speech rate (1.0 = normal)
--generate-music               Generate AI background music
--music-prompt TEXT            Music style prompt
--music PATH                   Use existing music file
--max-workers INT              Parallel Veo calls (default: 3)
--script-duration INT          Target narration seconds (default: 60)
--scene-duration INT           Seconds per Veo scene (default: 5)
--ai-order / --no-ai-order     AI scene ordering (default: on)
--intro / --no-intro           Generate branded intro frame
--outro / --no-outro           Generate branded outro frame
--blend                        Blend assets from subfolders
--dry-run                      Preview plan without running
```

### Storyboard from Website URL

```bash
# Generate visual assets from a website
python cli.py storyboard https://example.com \
    --storyline-file story.txt --scenes 9 --product "My App"

# Then create video from storyboard output
python cli.py create storyboard_output/sequence/ -o video.mp4 \
    --ai-order --generate-music --storyline-file story.txt
```

### Other Commands

```bash
# Avatar overlay
python cli.py avatar video.mp4 avatar.png -o out.mp4 \
    --position bottom-right --scale 0.15

# Voice clone (standalone)
python cli.py voice-clone "MyVoice" recording.mp3 \
    --accent "Indian" --gender "male"

# Generate music (standalone)
python cli.py music -o bg.mp3 --prompt "upbeat corporate" --duration 60

# List available voices
python cli.py voices --engine elevenlabs

# Direct Veo 3.1 animation
python cli.py veo image.png --prompt "gentle zoom" -o animated.mp4

# Basic video without Veo animation
python cli.py generate ./content/ -o video.mp4 --tts-engine edge

# Pipeline only (no clone/music generation)
python cli.py veo-marketing ./content/ -o out.mp4 --voice "Smritika"

# Show all commands
python cli.py --help

# Show options for a specific command
python cli.py create --help
```

## Supported Input Types

| Type | Extensions | What Happens |
|------|-----------|-------------|
| **Images** | `.png` `.jpg` `.jpeg` `.webp` `.gif` `.bmp` | OCR → AI script → Veo 3.1 animate → voiceover |
| **PowerPoint** | `.pptx` `.ppt` | Extract slides → process as images |
| **Documents** | `.pdf` `.doc` `.docx` | Extract pages → process as images |
| **Videos** | `.mp4` `.mov` `.avi` `.mkv` `.webm` | Transcribe → polish → clean → re-voice |
| **Screen Recordings** | `screen-recording-*.webm` | Detect mic track → preserve system audio → ducking |

Mix any types in one folder — files are processed in filename order.

## Output

Each run produces up to 3 files:

```
output.mp4       — Final video (H.264, AAC, 30fps)
output.mp3       — Audio track with voice + music
output_music.mp3 — Background music only
```

## Run Tests

```bash
cd project/videogen
pip install pytest
python -m pytest tests/ -v
```

## Deploy Web UI

```bash
# From repo root
modal deploy modal_app.py
```

API will be available at `https://video-generator.transilienceapi.com`
