# Video Generator — AI Marketing Video Pipeline

Turns any content (images, PPT, PDF, videos, URLs) into professional marketing videos with AI voiceover, animation, and music.

## Repository Structure

```
video_generator/
├── CLAUDE.md                              # Architecture & rules (this file)
├── README.md                              # Project overview + diagrams
├── requirements.txt                       # Python dependencies
├── .env                                   # API keys (not tracked)
├── .gitignore
│
├── .claude/                               # Claude Code config
│   ├── settings.local.json
│   └── skill/                             # Skill files mirroring src/ modules
│       ├── ai/                            #   ai_analyzer, gemini_client, imagen, tts, veo
│       ├── pipeline/                      #   veo_pipeline, storyboard, screenshotter, blend, bookend
│       ├── processing/                    #   avatar_overlay, video_cleaner, effects, extractors
│       ├── core/                          #   audio_utils, image_utils, video_utils
│       └── generators/                    #   music_generator, text_animator
│
└── project/
    └── videogen/
        ├── cli.py                         # CLI entry point (all commands)
        ├── process_recording.py           # Standalone video processor
        ├── samples/
        │   ├── input_samples/             # Sample input files
        │   └── video_samples/             # Generated sample videos
        └── src/
            ├── ai/                        # AI wrappers (Gemini, Veo 3.1, TTS, Imagen 4.0)
            ├── pipeline/                  # Orchestration (veo_pipeline, storyboard, screenshotter)
            ├── processing/                # Video processing (cleaner, avatar overlay, effects)
            ├── core/                      # Utilities (image, video, audio)
            └── generators/                # Music + text animation
```

## Architecture

**Pipeline** (`project/videogen/src/pipeline/veo_pipeline.py`):
- Main orchestrator — scan → OCR → unified narrative → Veo animate → TTS → combine → FFmpeg concat
- Handles static content (images/PPT/PDF) and video content (transcribe → polish → re-voice)
- Screen recording support: detects companion mic files, preserves system audio, sidechain ducking
- `no_voiceover_files` param: skip TTS entirely for flagged files

**Skills** (`.claude/skill/`):
- Mirror the `src/` module structure with `.skills.md` files
- Provide Claude Code with per-module context for each component
- Auto-loaded when working in the corresponding source directory

## Critical Rules

**Running the CLI:**
- All commands run from `project/videogen/`: `cd project/videogen && python cli.py create ...`
- Imports use `src.` prefix (e.g. `from src.pipeline.veo_pipeline import ...`)
- Dependencies: `pip install -r requirements.txt` (from repo root)

**Screen Recording Audio Architecture:**
- System audio stays in the video file (`screen-recording-*.webm`)
- Mic records as separate file (`mic-recording-*.webm`)
- NEVER mix system audio + mic during recording — they must be independent
- Pipeline detects companion mic files automatically by matching timestamps

**Audio Ducking (preserve_audio mode):**
- `original_audio_volume >= 1.0` triggers sidechain compression path in `combine_video_with_audio()`
- FFmpeg filter: `sidechaincompress=threshold=0.008:ratio=6:attack=100:release=800`
- Normal videos use simple mix (`original_audio_volume=0.3`)

**FFmpeg Concatenation (Step 5):**
- Uses FFmpeg concat demuxer with `-c copy` (stream copy, near instant)
- Each clip normalized first: `scale+pad` to target resolution, `-preset ultrafast -crf 18`
- Falls back to full re-encode if stream copy fails
- DO NOT reintroduce MoviePy for concatenation — it was too slow

**Per-File Voiceover Control:**
- `no_voiceover_files`: list of filenames that skip transcription, TTS, and audio stripping
- Video passes through with original audio intact

## Key Modules

| Module | Purpose |
|--------|---------|
| `src/pipeline/veo_pipeline.py` | Main orchestrator — `create_marketing_video_veo()`, `combine_video_with_audio()`, `enhance_script_for_tts()`, `polish_transcript()` |
| `src/ai/tts_engine.py` | ElevenLabs/Edge TTS, voice cloning, transcription (Scribe STT) |
| `src/ai/veo_generator.py` | Veo 3.1 image-to-video |
| `src/ai/gemini_client.py` | Gemini API (Vision, content generation) |
| `src/ai/imagen_generator.py` | Imagen 4.0 text-to-image |
| `src/pipeline/storyboard_planner.py` | Gemini Vision scene planning |
| `src/pipeline/website_screenshotter.py` | Playwright crawling + screenshots |
| `src/pipeline/bookend_generator.py` | Intro/outro frames (Gemini + Imagen + Veo) |
| `src/processing/avatar_overlay.py` | FFmpeg avatar compositing |
| `src/generators/music_generator.py` | Music generation (ElevenLabs, Suno, Replicate) |

All paths relative to `project/videogen/`.

## Pipeline Phases (`create` command)

```
Phase 0 (opt): Blend/reorder (--blend, --ai-order)
Phase 1 (opt): Voice cloning (--clone-voice + --clone-from)
Phase 3:       Video pipeline — create_marketing_video_veo()
  Step 0: Detect companion mic files (screen recordings)
  Step 1: Static → OCR + Unified Narrative | Video → Transcribe + Polish
  Step 2: Veo 3.1 animation (static only, parallel)
  Step 3: TTS enhancement + voiceover generation
  Step 4: Combine video + audio (ducking for screen recordings)
  Step 5: FFmpeg normalize + concat + export
Phase 4 (opt): Music generation → mix into video
```

## Processing Paths

**Static content** (.png .jpg .pptx .pdf):
`OCR → Unified Narrative (one AI call) → Veo 3.1 → TTS enhance → voiceover → combine`

**Video content** (.mp4 .mov .webm):
`Transcribe (before clean) → Polish → Clean → Strip audio → TTS → combine (simple mix)`

**Screen recordings** (screen-recording-* + mic-recording-*):
`Transcribe mic → Polish → Clean → KEEP system audio → TTS → combine (sidechain ducking)`

**No-voiceover files** (flagged by user):
`Skip transcription → Skip TTS → Pass through with original audio`

## API & Deployment

```bash
export GOOGLE_API_KEY="..."       # Required — Gemini + Veo 3.1 + Imagen 4.0
export ELEVENLABS_API_KEY="..."   # Optional — TTS, cloning, music
```

**Deploy:** `modal deploy modal_app.py`

**Endpoints:** `/create` (POST), `/status/{job_id}` (GET), `/download/{job_id}` (GET), `/storyboard` (POST), `/avatar` (POST)

## Output

- `output.mp4` — H.264, AAC 192kbps, 30fps (720p / 1080p / 4K)
- `output.mp3` — Voice + music (44.1kHz stereo 192kbps)
- `output_music.mp3` — Music only (trimmed to video length)

## Cost

~$0.25–0.65 per video (10 scenes). Free: Edge TTS + `generate` command = ~$0.03.

## Style Profiles

`--style` sets persona, voice guidelines, and structure:
- **marketing** — Pitch strategist, bold statements, urgency, CTA
- **demo** — Technical narrator, feature walkthrough, clear steps
- **explainer** — Teacher, concept breakdown, analogies
- **pitch** — Investor storytelling, metrics, traction
- **tutorial** — Step-by-step instructor, educational
