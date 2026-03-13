# Video Generator - Marketing Video Pipeline

**Automatically creates professional marketing videos from any combination of images, documents, presentations, and videos — with optional voice cloning and AI music generation.**

---

## Quick Start

```bash
# Everything in one command: clone voice + generate music + storyline + create video
python cli.py create ./content/ -o video.mp4 \
    --clone-voice "Aman" --clone-from voice_sample.mp3 \
    --generate-music --music-prompt "upbeat corporate" \
    --storyline "A small team discovers AI automation and scales to 10x productivity" \
    --product "My App" --tone "energetic"
```

Or step by step:
```bash
# Just make a video (simplest)
python cli.py create ./content/ -o video.mp4

# With an existing voice and no music
python cli.py create ./content/ -o video.mp4 --voice "Smritika"
```

Or start from just a website URL:
```bash
# Generate all visuals from a website + storyline
python cli.py storyboard https://example.com \
    --storyline-file story.txt --scenes 9 --product "My App"

# Then create video from storyboard output
python cli.py create storyboard_output/sequence/ -o video.mp4 \
    --ai-order --generate-music --storyline-file story.txt
```

The system automatically detects all file types, processes each appropriately, and combines everything into one cohesive video.

---

## Supported Input Types

| Type | Extensions | Processing |
|------|-----------|------------|
| **Images** | `.png`, `.jpg`, `.jpeg`, `.webp`, `.gif`, `.bmp` | Gemini Vision analysis + Veo 3.1 animation |
| **PowerPoint** | `.pptx`, `.ppt` | Extract slides → process as images |
| **Documents** | `.pdf`, `.doc`, `.docx` | Extract pages → process as images |
| **Videos** | `.mp4`, `.mov`, `.avi`, `.mkv`, `.webm`, `.m4v` | Transcribe → Polish → Clean → Re-voice |

**Mix any types in one folder** — the system processes each intelligently and combines them in filename order.

---

## The `create` Command (All-in-One)

The primary CLI command that handles everything in a single invocation.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     python cli.py create ./content/ -o video.mp4           │
│                          --storyline "your narrative arc"                   │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          ▼                       ▼                       ▼
┌─────────────────┐   ┌─────────────────────┐   ┌────────────────────────────┐
│  PHASE 1 (opt)  │   │   PHASE 2 (opt)     │   │       PHASE 3 (always)     │
│  Voice Cloning  │   │  Music Generation   │   │      Video Pipeline        │
│                 │   │                     │   │                            │
│  --clone-voice  │   │  --generate-music   │   │  create_marketing_video_   │
│  --clone-from   │   │  --music-prompt     │   │  veo()                     │
│                 │   │                     │   │  + --storyline              │
│  tts_engine.py  │   │  music_generator.py │   │  veo_pipeline.py           │
│  clone_voice_   │   │  generate_music()   │   │                            │
│  elevenlabs()   │   │                     │   │                            │
│        │        │   │        │            │   │                            │
│        ▼        │   │        ▼            │   │                            │
│  Cloned Voice   │   │   Music MP3         │   │                            │
│  (name/ID)      │   │   (background)      │   │                            │
└────────┬────────┘   └────────┬────────────┘   └─────────────┬──────────────┘
         │                     │                              │
         └──────── feeds into ─┴──────── feeds into ──────────┘
                                                              │
                                                              ▼
                              ┌────────────────────────────────────────────┐
                              │        Scan Folder & Sort by Filename     │
                              │          screenshot_handler.py            │
                              │                                           │
                              │  01_intro.png  02_pitch.pptx  03_demo.mov │
                              └──────────────────┬────────────────────────┘
                                                 │
                              ┌──────────────────┴──────────────────┐
                              │            For each file            │
                              │          What type is it?           │
                              └───────┬─────────────────────┬───────┘
                                      │                     │
              ┌───────────────────────┘                     └───────────────────────┐
              ▼                                                                     ▼
┌─────────────────────────────────────┐               ┌─────────────────────────────────────┐
│     STATIC CONTENT                  │               │     VIDEO CONTENT                   │
│     .png .jpg .pptx .pdf            │               │     .mp4 .mov .avi .mkv             │
│                                     │               │                                     │
│  ┌───────────────────────────────┐  │               │  ┌───────────────────────────────┐  │
│  │ 1a. OCR Text Extraction      │  │               │  │ 1. Transcribe Original Audio  │  │
│  │     extract_image_text()      │  │               │  │    transcribe_video()         │  │
│  │     → extracted text per scene│  │               │  │    (BEFORE cleaning =         │  │
│  │     (fast, per-scene)         │  │               │  │     no speech lost)           │  │
│  └──────────────┬────────────────┘  │               │  └──────────────┬────────────────┘  │
│                 ▼                    │               │                 ▼                    │
│  ┌───────────────────────────────┐  │               │  ┌───────────────────────────────┐  │
│  │ 1b. Unified Narrative        │  │               │  │ 2. Polish Transcript          │  │
│  │     generate_unified_         │  │               │  │    polish_transcript()        │  │
│  │     narrative()               │  │               │  │    + scene position context   │  │
│  │     ONE Claude call for ALL   │  │               │  │    (scene_number, preceding   │  │
│  │     scenes → cohesive scripts │  │               │  │     script, following topic)  │  │
│  │     + opening hook (scene 1)  │  │               │  │    + storyline guides polish  │  │
│  │     + CTA/close (last scene)  │  │               │  └──────────────┬────────────────┘  │
│  │     + no repeated phrases     │  │               │                 ▼                    │
│  │     + video scripts = "fixed" │  │               │  ┌───────────────────────────────┐  │
│  └──────────────┬────────────────┘  │               │  │ 3. Clean Video               │  │
│                 ▼                    │               │  │    clean_video()              │  │
│  ┌───────────────────────────────┐  │               │  │    Remove still/idle frames   │  │
│  │ 2. Veo 3.1 Animation         │  │               │  └──────────────┬────────────────┘  │
│  │    generate_video_veo()       │  │               │                 ▼                    │
│  │    Parallel: --max-workers    │  │               │  ┌───────────────────────────────┐  │
│  │    Cinematic zoom/pan/drift   │  │               │  │ 4. Strip Original Audio       │  │
│  │    + storyline guides motion  │  │               │  │    FFmpeg -an -c:v copy       │  │
│                 ▼                    │               │  └──────────────┬────────────────┘  │
│  ┌───────────────────────────────┐  │               │                 ▼                    │
│  │ 3. TTS Enhancement + Voice   │  │               │  ┌───────────────────────────────┐  │
│  │    enhance_script_for_tts()   │  │               │  │ 5. TTS Enhancement + Voice   │  │
│  │    → adds emphasis, pauses    │  │               │  │    enhance_script_for_tts()   │  │
│  │    generate_tts_elevenlabs()  │  │               │  │    → adds emphasis, pauses    │  │
│  │    or generate_tts_edge()     │  │               │  │    generate_tts_elevenlabs()  │  │
│  └──────────────┬────────────────┘  │               │  │    from polished script       │  │
│                 │                    │               │  └──────────────┬────────────────┘  │
└─────────────────┼────────────────────┘               └─────────────────┼────────────────────┘
                  │                                                      │
                  └──────────────────────┬──────────────────────────────┘
                                         │
                                         ▼
                  ┌──────────────────────────────────────────────────────┐
                  │              FINAL ASSEMBLY                         │
                  │                                                     │
                  │  1. Combine each scene's video + voiceover audio    │
                  │     combine_video_with_audio()                      │
                  │                                                     │
                  │  2. Normalize all clips to target resolution        │
                  │     720p (1280x720) / 1080p (1920x1080) / 4K       │
                  │                                                     │
                  │  3. Concatenate all scenes in filename order        │
                  │     concatenate_videoclips()                        │
                  │                                                     │
                  │  4. Mix background music (if provided/generated)    │
                  │     add_background_music_to_file()                  │
                  │                                                     │
                  │  5. Export → H.264 · AAC 192kbps · 30fps           │
                  │                                                     │
                  │  6. Extract audio → MP3 (44.1kHz stereo 192kbps)   │
                  │     _extract_final_audio()                          │
                  └───────────────────────┬────────────────────────────┘
                                          │
                                          ▼
                              ┌──────────────────────────────┐
                              │  output.mp4 (video)          │
                              │  output.mp3 (audio+music)    │
                              │  output_music.mp3 (music)    │
                              │                              │
                              │  All scenes combined         │
                              │  Unified voiceover           │
                              │  Background music (looped)   │
                              │  Target resolution           │
                              └──────────────────────────────┘
```

### Full Options

```bash
python cli.py create INPUT_PATH [OPTIONS]

# Core
  -o, --output TEXT              Output video file (default: output.mp4)

# Blend (optional — Phase 0)
  --blend                        Blend assets from subfolders into ordered sequence
  --sequence PATH                Markdown file/folder for blend ordering (implies --blend)
  --bookend PATH                 Image used as first and last frame during blend
  --ai-order/--no-ai-order       Use Gemini Vision to auto-order scenes (default: ai-order)
  --include-unsequenced          Include files not in sequence file (default: include)

# Voice Cloning (optional)
  --clone-voice NAME             Clone a voice — provide a name
  --clone-from AUDIO_FILE        Audio sample(s) for cloning (repeat for multiple)
  --clone-accent TEXT            Accent (e.g., British, Indian, American)
  --clone-gender TEXT            Gender (e.g., male, female)
  --clone-age TEXT               Age (e.g., young, middle_aged, old)
  --clone-description TEXT       Voice description

# Music (optional)
  --generate-music               Generate AI background music (30s loop, cost-efficient)
  --music-prompt TEXT            Music prompt (auto-derived from --tone if omitted)
  --music-duration INT           Music length in seconds (default: 60)
  --music-engine CHOICE          auto|elevenlabs|replicate|suno|simple
  --music PATH                   Pre-existing music file (overrides --generate-music)
  --music-volume FLOAT           Music mix volume (default: 0.03)

# Storyline
  --storyline TEXT               Narrative storyline to guide voiceover scripts and video animation

# Video Pipeline
  --voice TEXT                   TTS voice name (default: Smritika, overridden by --clone-voice)
  --tts-engine CHOICE            elevenlabs (premium) | edge (free)
  --voice-volume FLOAT           Voice volume multiplier (default: 5.0)
  --voice-speed FLOAT            Speech rate (1.0=normal, 1.2=20% faster)
  --mix SPEED,VOICE,MUSIC        Compact audio mix shorthand (e.g., "1.2,6.0,0.04")
  --style CHOICE                 marketing|demo|explainer|pitch|tutorial (default: marketing)
  --context TEXT                 Product/service context for scripts
  --product TEXT                 Product name
  --tone TEXT                    Script tone (default: professional and engaging)
  --resolution CHOICE            720p | 1080p | 4k (default: 1080p)
  --max-workers INT              Parallel Veo API calls (default: 3)
  --script-duration INT          Target total narration duration in seconds (default: 60)
  --scene-duration INT           Duration per Veo scene in seconds (default: 5)

# Bookends (optional)
  --intro/--no-intro             Generate branded intro frame (3 Imagen options, pick 1, Veo animate)
  --outro/--no-outro             Generate branded outro/CTA frame (3 Imagen options, pick 1, Veo animate)

# Behavior
  --dry-run                      Show execution plan without running
```

### Examples

```bash
# Full production: clone voice + generate music + storyline + style
python cli.py create ./content/ -o video.mp4 \
    --clone-voice "Aman" --clone-from recording.mp3 \
    --clone-accent "Indian" --clone-gender "male" \
    --generate-music --music-prompt "upbeat corporate" \
    --storyline "Meet our AI tool that transforms how teams collaborate and ship faster" \
    --product "My SaaS App" --tone "energetic" --style marketing \
    --script-duration 90 --resolution 1080p --max-workers 5

# Technical demo style
python cli.py create ./screenshots/ -o demo.mp4 \
    --style demo --storyline "Watch how our API handles 10k requests per second" \
    --product "FastAPI Pro" --script-duration 45

# Investor pitch
python cli.py create ./pitch_deck.pptx -o pitch.mp4 \
    --style pitch --storyline "From 0 to $1M ARR in 6 months" \
    --generate-music --music-prompt "inspiring orchestral"

# Storyline-driven marketing (no cloning, no music)
python cli.py create ./content/ -o story.mp4 \
    --storyline "From chaos to clarity — how one dashboard changed everything" \
    --product "Analytics Pro" --tone "inspiring"

# Compact audio mix shorthand
python cli.py create ./content/ -o video.mp4 \
    --mix "1.2,6.0,0.04" --generate-music

# With pre-existing music file
python cli.py create ./mixed_content/ -o final.mp4 \
    --clone-voice "MyVoice" --clone-from sample.mp3 \
    --music background.mp3 --resolution 1080p

# Preview execution plan
python cli.py create ./content/ -o video.mp4 \
    --clone-voice "Test" --clone-from sample.mp3 \
    --generate-music --dry-run
```

---

## Processing Details

### Static Content Flow (Images/PPT/PDF)

```
Step  What                       Module                              Function
───── ─────────────────────────── ─────────────────────────────────── ──────────────────────────────────
1     Load & Sort                 src/pipeline/screenshot_handler.py  get_media_files(), extract_pptx_slides()
1a    OCR Text Extraction         src/pipeline/veo_pipeline.py        extract_image_text()
      (per-scene, fast)                                                Gemini Vision → extracted text only
1b    Unified Narrative           src/pipeline/veo_pipeline.py        generate_unified_narrative()
      (ONE call for ALL scenes)                                        All thumbnails + OCR text + storyline
                                                                       + --style profile (persona/voice/structure)
                                                                       + --script-duration word budget
                                                                       → cohesive per-scene scripts
                                                                       (hook → flow → CTA, no repetition)
                                                                       Fallback: analyze_image_for_script_and_text()
2     Veo 3.1 Animation           src/ai/veo_generator.py             generate_video_veo()
      (parallel, --max-workers)   src/pipeline/veo_pipeline.py        _generate_veo_scenes_parallel()
      5 seconds per scene                                              (storyline injected into video prompt)
      + storyline → motion                                             Clean script used (no TTS cues)
3     TTS Enhancement             src/pipeline/veo_pipeline.py        enhance_script_for_tts()
      (per-scene)                                                      Claude adds delivery cues: ALL CAPS
                                                                       emphasis, dashes for pauses, ellipses
                                                                       for suspense, energy gradient
3b    TTS Voiceover               src/ai/tts_engine.py                generate_tts_elevenlabs() / generate_tts_edge()
      (from enhanced script)                                           Enhanced script → expressive voiceover
4     Combine video + audio       src/pipeline/veo_pipeline.py        combine_video_with_audio()
```

### Video Content Flow

```
Step  What                       Module                              Function
───── ─────────────────────────── ─────────────────────────────────── ──────────────────────────────────
1     Transcribe original audio   src/ai/tts_engine.py                transcribe_video() → raw text
      (BEFORE cleaning — no       (calls transcribe_elevenlabs()       via ElevenLabs Scribe STT)
       speech lost)
2     Polish transcript           src/pipeline/veo_pipeline.py        polish_transcript() → Claude rewrites:
      + scene position context                                         removes filler, fixes grammar,
      + storyline → coherence                                          keeps all points + original order
                                                                       scene_number, preceding_script,
                                                                       following_topic for narrative flow
3     Clean video                 src/processing/video_cleaner.py     clean_video() → remove still/idle frames
4     Strip original audio        FFmpeg (-an -c:v copy)              inline in veo_pipeline.py
5     TTS Enhancement + Voice      src/pipeline/veo_pipeline.py        enhance_script_for_tts() → delivery cues
                                  src/ai/tts_engine.py                generate_tts_elevenlabs() / generate_tts_edge()
6     Combine video + audio       src/pipeline/veo_pipeline.py        combine_video_with_audio()

      After all videos processed:
      Video scripts become "fixed" segments in the unified narrative call (Step 1b).
      Surrounding static scene scripts are written to flow into/out of video scripts.
```

### Voice Cloning Flow (Phase 1 of `create`)

```
Step  What                       Module                              Function
───── ─────────────────────────── ─────────────────────────────────── ──────────────────────────────────
1     Upload audio samples        src/ai/tts_engine.py                clone_voice_elevenlabs()
2     Returns voice name/ID       ElevenLabs API                      POST /v1/voices/add
      (used as --voice for TTS)
```

### Music Generation Flow (Phase 4 of `create` — after video pipeline)

```
Step  What                       Module                              Function
───── ─────────────────────────── ─────────────────────────────────── ──────────────────────────────────
1     Get video duration          MoviePy VideoFileClip               clip.duration → final_duration
2     Auto-derive prompt          src/generators/music_generator.py   get_music_prompt_for_tone()
      (if --music-prompt omitted)
3     Generate short loop         src/generators/music_generator.py   generate_music()
      (max 30s to save cost)      Engines: elevenlabs, suno,          → saves API credits vs full length
                                  replicate, simple
4     Mix into video              src/pipeline/veo_pipeline.py        add_background_music_to_file()
      (loops if needed,                                                loops short clip to fill video
       trims to video duration)                                        trims excess, fades out at end
5     Re-extract audio            src/pipeline/veo_pipeline.py        _extract_final_audio()
      (MP3 now includes music)                                         output.mp3 has voice + music
6     Save music separately       FFmpeg trim to video duration        output_music.mp3 (trimmed)
```

### Final Assembly

```
Step  What                       Module                              Function
───── ─────────────────────────── ─────────────────────────────────── ──────────────────────────────────
1     Normalize all clips         MoviePy clip.resized()              target from --resolution (720p/1080p/4k)
      to target resolution
2     Concatenate scenes          MoviePy                             concatenate_videoclips()
3     Export final MP4            FFmpeg via MoviePy                   H.264, AAC, 30fps
4     Extract audio as MP3        src/pipeline/veo_pipeline.py        _extract_final_audio()
      (44.1kHz stereo 192kbps)    FFmpeg -vn -acodec libmp3lame       output.mp4 → output.mp3

      Phase 4 (if --generate-music):
5     Generate 30s music loop     src/generators/music_generator.py   generate_music() (max 30s for cost)
6     Mix into video              src/pipeline/veo_pipeline.py        add_background_music_to_file()
      (loop + trim + fade)                                             loops short clip to fill video length
7     Re-extract audio            src/pipeline/veo_pipeline.py        _extract_final_audio()
      (MP3 now has voice+music)                                        output.mp3 updated with music
8     Save music separately       FFmpeg -t trim                       output_music.mp3 (trimmed to video)
```

### Orchestration

```
cli.py                           All CLI commands
  ├─ storyboard command          Phase 1: crawl_and_capture() (Playwright)
  │                              Phase 2: plan_storyboard() (Gemini Vision)
  │                              Phase 3: generate_image() (Imagen 4.0) for all scenes
  │                              Phase 4: assemble sequence/ folder
  │
  └─ create command              Phase 0 (opt): blend/reorder (--blend, --ai-order)
                                 Phase 1 (opt): clone_voice_elevenlabs()
                                 Phase 2 (opt): (reserved)
                                 Phase 3:       create_marketing_video_veo()
                                 Phase 4 (opt): generate_music() → 30s loop → mix → re-extract audio

src/pipeline/veo_pipeline.py     Main pipeline orchestrator
  ├─ create_marketing_video_veo()   Full flow: scan → OCR → narrative → Veo → TTS enhance → voice → combine
  ├─ enhance_script_for_tts()       Add delivery cues before TTS
  ├─ generate_unified_narrative()   One Gemini call for all scene scripts
  ├─ add_background_music_to_file() Loop + trim + mix music into video
  └─ create_marketing_video_static() Static-only flow (no Veo)

src/pipeline/storyboard_planner.py  Scene planning with Gemini Vision
  ├─ plan_storyboard()              Send captures + storyline → scene plan
  └─ write_storyboard_text()        Human-readable storyboard output

src/pipeline/website_screenshotter.py  Website crawling
  ├─ crawl_and_capture()            Scroll + click nav links → screenshots
  ├─ login_and_save_auth()          Google sign-in + auth state persistence
  └─ crawl_and_capture_sync()       Synchronous wrapper

src/ai/imagen_generator.py         Imagen 4.0 wrapper
  └─ generate_image()               Text prompt → PNG image

src/pipeline/bookend_generator.py   Intro/outro frame generation
  └─ generate_bookends()             Gemini suggestions → Imagen images → Veo animation

src/processing/avatar_overlay.py   Avatar overlay compositing
  └─ overlay_avatar()                FFmpeg overlay filter (image or video avatar)

process_recording.py             Standalone video processing pipeline
```

---

## Mixed Content Example

**Input Folder:**
```
marketing/
├── 01_title.png              # Image
├── 02_pitch.pptx             # 3 slides
├── 03_demo.mov               # Video with voiceover (45s)
├── 04_features.pdf           # 2 pages
└── 05_cta.jpg                # Image
```

**Processing:**
1. `03_demo.mov` → Transcribe → Polish (with scene position context) → Clean → Strip audio → **Scene 5 script fixed**
2. All 7 static images → OCR text extraction (per-scene)
3. **Unified narrative call** → Claude sees all 8 thumbnails + OCR + Scene 5's fixed script → generates cohesive scripts for scenes 1-4, 6-8 that flow into/out of scene 5
4. Static scenes → Veo animate (parallel) → **Scenes 1-4, 6-8**
5. All scenes → TTS voiceover → combine → final assembly

**Result:** `marketing_video.mp4` + `marketing_video.mp3` (voice+music) + `marketing_video_music.mp3` (music only) — 8 scenes, ~99 seconds, cohesive narrative with opening hook + natural flow + closing CTA

---

## The `storyboard` Command (Content Preparation)

Generates all visual assets from a **website URL + storyline** — screenshots + AI-generated images — ready to feed into `create`.

### Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│  python cli.py storyboard https://example.com                         │
│      --storyline-file story.txt --scenes 9 --product "My App"         │
└──────────────────────────────┬─────────────────────────────────────────┘
                               │
    ┌──────────────────────────┼──────────────────────────┐
    ▼                          ▼                          ▼
┌────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│  Phase 1       │  │  Phase 2             │  │  Phase 3             │
│  Website Crawl │  │  AI Scene Planning   │  │  Imagen Generation   │
│  (Playwright)  │  │  (Gemini Vision)     │  │  (Imagen 4.0)        │
│                │  │                      │  │                      │
│  Scroll pages  │  │  Sees ALL captures   │  │  Futuristic tech     │
│  Click nav     │  │  Picks best per      │  │  visuals for ALL     │
│  16:9 viewport │  │  scene by index      │  │  scenes              │
│                │  │  Writes fallback     │  │  + storyline context │
│  screenshots/  │  │  Imagen prompts      │  │                      │
│  ├── 000_*.png │  │                      │  │  generated/          │
│  ├── 001_*.png │  │  storyboard.txt      │  │  ├── scene_001.png  │
│  └── ...       │  │                      │  │  └── ...            │
└───────┬────────┘  └──────────┬───────────┘  └──────────┬───────────┘
        │                      │                         │
        └──────────────────────┼─────────────────────────┘
                               ▼
                    ┌──────────────────────┐
                    │  Phase 4: Assemble   │
                    │  sequence/ folder    │
                    │                      │
                    │  Screenshot if avail │
                    │  + Generated image   │
                    │  per scene           │
                    │                      │
                    │  001_title_ss.png    │
                    │  001_title_gen.png   │
                    │  002_title_ss.png    │
                    │  ...                 │
                    └──────────┬───────────┘
                               ▼
                    ┌──────────────────────┐
                    │  Feed into `create`  │
                    │  with --ai-order     │
                    │  for pitch reranking │
                    └──────────────────────┘
```

### Output Structure

```
storyboard_output/
├── storyboard.txt              # Scene breakdown with descriptions
├── screenshots/                # All website captures (scroll + nav)
│   ├── 000_homepage_scroll_0.png
│   ├── 001_homepage_scroll_1.png
│   └── 002_nav_pricing_scroll_0.png
├── generated/                  # Imagen 4.0 generated images
│   ├── scene_001_the_hook.png
│   └── scene_002_the_problem.png
└── sequence/                   # Final numbered sequence
    ├── 001_the_hook_screenshot.png
    ├── 001_the_hook_generated.png
    ├── 002_the_problem_screenshot.png
    ├── 002_the_problem_generated.png
    └── ...
```

### Full Options

```bash
python cli.py storyboard URL [OPTIONS]

  URL                            Website URL to capture and analyze

  -o, --output TEXT              Output directory (default: storyboard_output/)
  --storyline TEXT               Narrative storyline for the video
  --storyline-file PATH          Read storyline from a text file
  --scenes INT                   Number of scenes to plan (default: 6)
  --product TEXT                 Product/service name
  --context TEXT                 Additional context
  --tone TEXT                    Script tone (default: professional and engaging)
  --style CHOICE                 marketing|demo|explainer|pitch|tutorial
  --aspect-ratio TEXT            Aspect ratio (default: 16:9)
  --skip-imagen                  Skip AI image generation (screenshots only)
  --skip-screenshots             Skip website screenshots (Imagen only)
  --login                        Open browser for Google sign-in before crawling
  --dry-run                      Show scene plan without generating assets
```

### Examples

```bash
# Full storyboard with login (auth-required site)
python cli.py storyboard https://transilience.ai \
    --login \
    --storyline-file story.txt \
    --scenes 9 --product "Transilience.AI" \
    -o storyboard_output/

# Auto Google sign-in (set env vars first)
export GOOGLE_EMAIL="you@gmail.com"
export GOOGLE_PASSWORD="your_password"
python cli.py storyboard https://transilience.ai \
    --login --storyline-file story.txt --scenes 9

# Preview plan only (no generation)
python cli.py storyboard https://example.com \
    --storyline "AI transforms compliance" --dry-run

# Screenshots only (no Imagen)
python cli.py storyboard https://example.com \
    --storyline "Product demo" --skip-imagen

# Imagen only (no screenshots, for auth-blocked sites)
python cli.py storyboard https://example.com \
    --storyline "Product demo" --skip-screenshots

# Then rerank + create video from storyboard output
python cli.py create storyboard_output/sequence/ -o video.mp4 \
    --ai-order \
    --generate-music \
    --music-prompt "upbeat marketing corporate music" \
    --storyline-file story.txt \
    --product "Transilience.AI" \
    --voice "Venkat" \
    --style marketing

# Or blend from all subfolders + rerank
python cli.py create storyboard_output/ -o video.mp4 \
    --blend --ai-order --include-unsequenced \
    --generate-music \
    --storyline-file story.txt \
    --product "Transilience.AI" \
    --voice "Venkat" \
    --style marketing
```

### Storyboard Pipeline Details

```
Step  What                       Module                                  Function
───── ─────────────────────────── ─────────────────────────────────────── ──────────────────────────────
1     Website Crawl               src/pipeline/website_screenshotter.py   crawl_and_capture()
      Playwright headless         Scroll through pages + click nav        _scroll_and_capture()
      16:9 viewport               links → capture every viewport          _find_nav_links()
      Optional Google login       Persistent browser profile              login_and_save_auth()
      Auth state saved to         ~/.cache/video_generator/               AUTH_STATE_FILE

2     AI Scene Planning           src/pipeline/storyboard_planner.py      plan_storyboard()
      Gemini sees ALL captures    Interleaved text + images               generate_with_content_blocks()
      Picks best capture/scene    Returns StoryboardScene[]               best_capture_index per scene
      Writes Imagen prompts       Futuristic tech focus                   image_description per scene
      Uses VIDEO_STYLE_PROFILES   from veo_pipeline.py                    persona/voice/structure

3     Imagen Generation           src/ai/imagen_generator.py              generate_image()
      Imagen 4.0 for ALL scenes   google-genai SDK                        client.models.generate_images()
      Futuristic tech visuals     Holographic displays, data viz          NOT environments/cities
      Storyline keywords injected Style prefix rotation (10 styles)       Clean minimal backgrounds
      Occasional humans (2-3)     Person at whiteboard, hands on UI       Technology is the subject

4     Assemble Sequence           cli.py storyboard command               Phase 4
      Copy screenshot + generated Both files per scene                    _screenshot.png + _generated.png
      to sequence/ folder         Feeds into create --ai-order            Gemini reranks for pitch flow
```

### New Files

| File | Purpose |
|------|---------|
| `src/ai/imagen_generator.py` | Imagen 4.0 image generation wrapper |
| `src/pipeline/website_screenshotter.py` | Playwright website crawling + screenshots |
| `src/pipeline/storyboard_planner.py` | Gemini Vision scene planning |
| `src/processing/avatar_overlay.py` | FFmpeg avatar overlay (image or video) on video corners |
| `modal_app.py` | Web UI deployed on Modal (FastAPI + embedded frontend) |

### Key Design Decisions

- **Screenshots first, Imagen as complement** — Gemini picks the best real screenshot per scene; Imagen generates a visually distinct futuristic image for every scene too
- **Futuristic tech, not environments** — Generated images show holographic dashboards, transparent tablets, floating data — not cities, corridors, or glowing circuits
- **Occasional humans only (2-3 scenes)** — Person at whiteboard, hands on interface — technology is the subject
- **Storyline keywords in Imagen prompts** — Generated images reference the storyline and product name for relevance
- **Google login support** — Persistent Chrome profile with automation detection bypass for auth-required sites
- **Auth state cached** — Login once with `--login`, future runs reuse `~/.cache/video_generator/auth_state.json`

---

## Other CLI Commands

### `veo-marketing` — Video pipeline only (no cloning/music generation)
```bash
python cli.py veo-marketing ./content/ \
    --voice "Smritika" --resolution 1080p -o output.mp4
```

### `generate` — Basic video (no Veo animation)
```bash
python cli.py generate ./content/ -o video.mp4 \
    --tts-engine edge --generate-music
```

### `voice-clone` — Clone a voice separately
```bash
python cli.py voice-clone "Aman" recording.mp3 \
    --accent "Indian" --gender "male"
```

### `music` — Generate music separately
```bash
python cli.py music -o bg.mp3 \
    --prompt "upbeat corporate" --duration 60
```

### `voices` — List available TTS voices
```bash
python cli.py voices --engine elevenlabs
```

### `veo` — Direct Veo 3.1 access
```bash
python cli.py veo image.png --prompt "gentle motion" -o animated.mp4
```

### `avatar` — Add avatar overlay to a video
```bash
python cli.py avatar video.mp4 avatar.png -o video_with_avatar.mp4 \
    --position bottom-right --scale 0.15 --opacity 1.0 --margin 20
```

Options:
- `--position`: top-left, top-right, bottom-left, bottom-right (default: bottom-right)
- `--scale`: Avatar size as fraction of video width (default: 0.15 = 15%)
- `--margin`: Pixel margin from edges (default: 20)
- `--opacity`: Avatar opacity 0.0–1.0 (default: 1.0, image avatars only)

Supports both image avatars (.png/.jpg) and video avatars (.mp4/.mov).

### `engage` — Videos with cursor + highlight animations
```bash
python cli.py engage ./screenshots/ -o engaging.mp4
```

### `info` — Setup guide and examples
```bash
python cli.py info
```

---

## Feature Matrix

| Feature | `storyboard` | `create` | `veo-marketing` | `generate` |
|---------|-------------|----------|-----------------|------------|
| Website Crawling | Yes (Playwright) | No | No | No |
| Imagen 4.0 Generation | Yes (futuristic tech) | No | No | No |
| AI Scene Planning | Yes (Gemini Vision) | No | No | No |
| Google Login | Yes (`--login`) | No | No | No |
| Storyline | `--storyline` (scene planning) | `--storyline` (scripts + animation) | No | No |
| Unified Narrative | No | Yes (two-pass: OCR → cohesive scripts) | Yes (two-pass) | No (per-scene) |
| Video Style Profiles | `--style` (scene planning) | `--style` (marketing/demo/explainer/pitch/tutorial) | No | No |
| Script Duration Control | No | `--script-duration` (word budget) | No | No |
| TTS Enhancement | No | Yes (enhance_script_for_tts → expressive delivery) | Yes | No |
| Voice Cloning | No | Built-in | Use `--voice` with pre-cloned | Use `--voice` with pre-cloned |
| AI Music Generation | No | Built-in (30s loop, cost-efficient) | Pass `--music` file | Built-in (`--generate-music`) |
| Gemini Vision | Scene planning + capture selection | For static content | For static content | For all content |
| Veo 3.1 Animation | No | For static content (5s per scene) | For static content | No |
| AI Scene Ordering | Gemini picks best capture | `--ai-order` (Gemini Vision) | No | No |
| Dry Run | `--dry-run` | `--dry-run` | No | `--dry-run` |
| Avatar Overlay | No | No (use `avatar` command after) | No | No |
| Cost Estimation | No | Yes (Web UI post-generation) | No | No |

---

## Technical Stack

**AI/ML:** Google Gemini Vision, Google Veo 3.1, Google Imagen 4.0, ElevenLabs (TTS + STT + voice cloning + music)

**Video:** FFmpeg, OpenCV, MoviePy

**Web:** Playwright (headless Chromium for website crawling + screenshots)

**Documents:** python-pptx, PyPDF2/pdf2image, PIL/Pillow

**Deployment:** Modal (serverless GPU/CPU, FastAPI web app)

---

## Output Specifications

**Video:** 720p / 1080p / 4K, 30 FPS, H.264 (libx264), AAC 192kbps

**Audio:** MP3, 44.1kHz stereo, 192kbps — automatically extracted alongside the video (same filename with `.mp3` extension, includes voice + music)

**Music:** MP3, 44.1kHz stereo, 192kbps — saved separately as `output_music.mp3` (trimmed to video duration)

**Veo Animation:** 5 seconds per scene (configurable via `--scene-duration`), cinematic zoom/pan, resolution sent to API

---

## Cost & Performance

### Estimated Costs (10 scenes)
- Gemini Vision: ~$0.03
- Veo 3.1 Animation: ~$0.20-0.50
- ElevenLabs TTS: ~$0.02-0.05
- Voice Cloning: Free (included with ElevenLabs plan)
- Music Generation: ~$0.01-0.05
- **Total: ~$0.25-0.65 per video**

### Processing Times (--max-workers 3, default)
- 5 images: ~8-10 minutes
- 10 slides (PPT): ~12-16 minutes
- 2min video input: ~2-3 minutes
- Mixed (5 images + 1 video): ~10-13 minutes

### Free Alternative
- Use Edge TTS (`--tts-engine edge`)
- Skip Veo (use `generate` command instead)
- **Cost: ~$0.03 (Claude only)**

---

## Required API Keys

```bash
export GOOGLE_API_KEY="..."       # Required — Gemini Vision + Veo 3.1 + Imagen 4.0
export ELEVENLABS_API_KEY="..."   # Optional — Premium TTS, voice cloning, music
export GOOGLE_EMAIL="..."         # Optional — Auto Google sign-in for storyboard --login
export GOOGLE_PASSWORD="..."      # Optional — Auto Google sign-in for storyboard --login
```

---

## Key Advantages

- **URL to Video** — `storyboard` + `create` goes from a website URL to a finished marketing video with AI-generated visuals, voiceover, and music
- **One Command** — `create` does voice cloning + music + video in a single run
- **Cohesive Narrative** — Two-pass script generation: OCR first, then one Claude call for ALL scenes produces scripts with opening hook, natural flow, no repetition, and closing CTA. Video transcripts become "fixed" segments that surrounding scripts flow into/out of
- **Storyline-Driven** — `--storyline` guides voiceover scripts, transcript polishing, and Veo animation prompts for narrative coherence
- **Video Style Profiles** — `--style` switches between marketing, demo, explainer, pitch, and tutorial personas with distinct voice guidelines, structure, and vocabulary
- **Expressive TTS** — Scripts are enhanced with delivery cues (ALL CAPS emphasis, dashes for pauses, ellipses for suspense, energy gradient) before sending to TTS, producing more engaging voiceovers
- **Any Input** — Images, PPT, PDF, Videos in any combination
- **Smart Video Processing** — Transcribes original audio, polishes script (position-aware), cleans visuals, re-voices
- **No Speech Lost** — Transcription happens before video cleaning
- **AI Scene Ordering** — `--ai-order` uses Gemini Vision to automatically sequence scenes into a logical narrative
- **Resolution Normalized** — All scenes scaled to target resolution before combining
- **Parallel Generation** — Concurrent Veo API calls with `--max-workers`
- **Professional Quality** — Veo 3.1 animation (5s per scene) + ElevenLabs voice + AI music
- **Cost-Efficient Music** — Generates max 30s loop and repeats it, saving ~4x on music API costs vs full-length generation
- **Graceful Fallbacks** — Clone failure falls back to default voice, music failure continues without, unified narrative failure falls back to per-scene generation
- **Triple Output** — Exports video (MP4), audio with music (MP3), and background music separately (MP3)
- **Cost-Effective** — ~$0.25-0.65 per video, or $0.03 with free options
- **Post-Generation Cost Estimation** — After video generation, displays per-component cost breakdown (Gemini Vision, Veo, TTS, Music)
- **Avatar Overlay** — Composite image or video avatars on any corner of the finished video via CLI or Web UI

---

## Web UI (Modal Deployment)

The project includes a full web interface deployed on Modal (`modal_app.py`). Deploy with `modal deploy modal_app.py`.

### Features

- **Drag-and-drop file upload** — Upload images, PPT, PDF, or video files directly
- **URL-based storyboard** — Paste a website URL and click "Generate Storyboard" to crawl the site, plan scenes, and generate images (available when marketing style is selected)
- **Storyboard gallery** — Browse generated storyboard images inline, then "Create Video from Storyboard" to feed them into the video pipeline
- **Style picker** — Visual cards for marketing, demo, explainer, pitch, tutorial styles with sample videos
- **Video modal** — Click sample videos to expand full-screen with sound playback
- **Storyline input** — Text area with `+` button to upload `.txt/.md` storyline files
- **Scene duration guidance** — Dynamic hint showing `N scenes ~ Xs video` (5s per scene)
- **Avatar overlay panel** — After video generation, users can:
  1. Download the generated audio
  2. Create an avatar video externally (HeyGen, Synthesia, D-ID)
  3. Upload the avatar and apply overlay with position/scale/opacity controls
- **Cost estimation** — Post-generation breakdown showing per-component costs (Gemini Vision, Veo 3.1, TTS, Music) and total
- **Desktop-optimized layout** — Wide container (1600px) with responsive grid

### Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Main web interface |
| `/create` | POST | Start video generation job |
| `/status/{job_id}` | GET | Poll job status + logs |
| `/download/{job_id}` | GET | Download finished video |
| `/storyboard` | POST | Start storyboard generation from URL |
| `/storyboard-status/{job_id}` | GET | Poll storyboard job status |
| `/storyboard-image/{job_id}/{filename}` | GET | Serve storyboard images |
| `/avatar` | POST | Apply avatar overlay to generated video |

### New Files

| File | Purpose |
|------|---------|
| `modal_app.py` | FastAPI app with embedded HTML/CSS/JS, deployed on Modal |
| `src/processing/avatar_overlay.py` | FFmpeg-based avatar overlay compositing |