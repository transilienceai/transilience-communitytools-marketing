# Bookend Generator — `src/pipeline/bookend_generator.py`

## Description

Generates branded intro and outro frames for marketing videos. Creates 3 options each using Gemini (creative direction) + Imagen 4.0 (image generation), then animates the selected frame with Veo 3.1.

## Data Classes

| Class | Description |
|-------|-------------|
| `BookendSuggestion` | Single concept: `option_number`, `title_text`, `subtitle_text`, `image_description` (Imagen prompt), `veo_motion_prompt`. |

## Functions

| Function | Description |
|----------|-------------|
| `generate_bookends()` | High-level orchestrator. For each enabled bookend type: Gemini generates 3 concepts, Imagen generates 3 images, user picks one (or auto-pick), Veo animates the selected image. Returns `(intro_clip_path, outro_clip_path)`. |
| `generate_bookend_suggestions()` | Uses Gemini to generate 3 creative concepts. Each concept includes distinct visual style, color palette, and motion direction. |
| `generate_bookend_images()` | Generates images for all 3 suggestions using Imagen 4.0. Images are background-only (no text). |
| `present_bookend_choices()` | Shows Rich table of options. In interactive mode, prompts user to pick 1-3. In non-interactive mode, auto-selects first valid option. |
| `animate_bookend()` | Animates selected image with Veo 3.1 using the suggestion's motion prompt. Falls back to static ImageClip if Veo fails. |

## CLI Flags
```bash
python cli.py create ./content/ -o video.mp4 --intro --outro --product "MyApp"
```

## Integration
Called from `create_marketing_video_veo()` as Step 4.5, between scene combination and final concatenation. Intro clip is prepended, outro clip is appended to the clip list.

## Dependencies
- `gemini_client` (generate_text), `imagen_generator` (generate_image), `veo_generator` (generate_video_veo)
- `moviepy` (ImageClip fallback), `rich` (table display)

## Cost
- Gemini: 2 calls (~$0.001)
- Imagen: 6 images (~$0.06)
- Veo: 2 animations (~$0.04-0.10)
- Total: ~$0.10-0.17 per video
