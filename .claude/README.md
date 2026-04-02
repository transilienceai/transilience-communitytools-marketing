# .claude/ — Claude Code Configuration

This directory contains skill files that provide Claude Code with per-module context when working on this codebase. Each `.skills.md` file maps to a corresponding source module in `project/videogen/src/`.

## skill/

### skill/ai/ — AI Service Wrappers

| File | Description |
|------|-------------|
| `ai_analyzer.skills.md` | Claude Vision analysis — generates marketing scripts and scene descriptions from media files |
| `gemini_client.skills.md` | Google Gemini API wrapper for vision and text generation (single/multi-image, interleaved content) |
| `imagen_generator.skills.md` | Google Imagen 4.0 text-to-image generation |
| `tts_engine.skills.md` | Text-to-speech and transcription — supports Edge TTS, OpenAI TTS, ElevenLabs with voice cloning and word-level transcription |
| `veo_generator.skills.md` | Google Veo 3.1 video generation from text prompts or images, including image-to-video animation |

### skill/core/ — Shared Utilities

| File | Description |
|------|-------------|
| `audio_utils.skills.md` | Audio extraction from video and background music overlay with looping/fade-out |
| `image_utils.skills.md` | Base64 encoding, MIME detection, API-compatible resizing, and dimension retrieval |
| `video_utils.skills.md` | Video metadata extraction via ffprobe (duration, dimensions, frame rate) |

### skill/generators/ — Content Generators

| File | Description |
|------|-------------|
| `music_generator.skills.md` | AI background music generation with multi-engine support (ElevenLabs, Suno, Replicate) and local fallback |
| `text_animator.skills.md` | Animated text videos with cursor movement, highlighting, and zoom effects synced to voiceover |

### skill/pipeline/ — Orchestration & Assembly

| File | Description |
|------|-------------|
| `veo_pipeline.skills.md` | Main orchestrator — scan, OCR, narrative, Veo animate, TTS, combine, FFmpeg concat |
| `blend_handler.skills.md` | Media file scanning, deduplication, and sequencing (markdown or AI reordering) |
| `bookend_generator.skills.md` | Branded intro/outro frame generation using Gemini + Imagen + Veo |
| `screenshot_handler.skills.md` | Media loader for images, videos, and PowerPoint slides (PPTX extraction) |
| `storyboard_planner.skills.md` | Gemini Vision scene planning from website screenshots with Imagen prompt generation |
| `video_assembler.skills.md` | Final video stitching with captions, audio sync, music mixing, and multi-aspect-ratio support |
| `website_screenshotter.skills.md` | Playwright-based website crawling and screenshot capture with auth support |

### skill/processing/ — Video Processing

| File | Description |
|------|-------------|
| `avatar_overlay.skills.md` | FFmpeg avatar compositing — overlays static/video avatars with scaling, opacity, and border radius |
| `post_processor.skills.md` | Speed adjustment, volume control, audio remixing, and optional MP3 extraction |
| `video_cleaner.skills.md` | Motion detection to remove still/repetitive frames using OpenCV + FFmpeg |
| `video_effects.skills.md` | Cinematic effects (zoom pulses, color grading, vignette, transitions) via FFmpeg filter chains |
| `video_extractors.skills.md` | Frame extraction — keyframes, last frames (for scene chaining), and timestamp-based extraction |
