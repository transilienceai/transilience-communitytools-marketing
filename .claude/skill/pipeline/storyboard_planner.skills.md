# Storyboard Planner — `src/pipeline/storyboard_planner.py`

## Description

Gemini Vision scene planning from website screenshots + storyline.

## Data Classes

| Class | Description |
|-------|-------------|
| `StoryboardScene` | Single scene: `scene_number`, `title`, `voiceover_script`, `image_description` (Imagen prompt), `best_capture_index` (-1 if none), `best_capture_reason`. |
| `Storyboard` | Complete plan: `url`, `storyline`, `scenes: List[StoryboardScene]`, `product`, `tone`, `style`. |

## Functions

| Function | Description |
|----------|-------------|
| `plan_storyboard()` | Shows Gemini ALL captured screenshots (up to 20, labeled by index). Gemini picks the best capture per scene and writes Imagen prompts for futuristic tech visuals. Uses `VIDEO_STYLE_PROFILES` for persona/voice/structure. Retries up to 3 times on JSON parse failures. Works with or without captures (text-only fallback). |
| `write_storyboard_text()` | Writes human-readable storyboard text file with scene breakdown. |

## Imagen Prompt Guidelines (built into prompt)
- Focus: holographic dashboards, floating 3D data, transparent tablets, AI interfaces
- Avoid: cities, corridors, server rooms, UI mockups
- Occasional humans (2-3 scenes): person at whiteboard, hands on interface
- Camera: close-up tech detail, medium floating display, top-down digital surface
- Scene 1: hook shot, Last scene: CTA with warm tone

## Dependencies
- `gemini_client` (generate_with_content_blocks, generate_text)
- `veo_pipeline.VIDEO_STYLE_PROFILES`

## Usage
```python
from src.pipeline.storyboard_planner import plan_storyboard, write_storyboard_text

storyboard = plan_storyboard(
    storyline="AI transforms compliance workflows",
    url="https://example.com",
    captures=capture_paths,
    capture_labels=labels,
    num_scenes=9,
    product="My App",
    style="marketing",
)
write_storyboard_text(storyboard, Path("storyboard.txt"))
```
