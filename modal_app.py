"""
Video Generator — Modal Serverless Deployment

Deploy:  modal deploy modal_app.py
Test:    curl -X POST -F "content=@video.mp4" https://<modal-url>/create
Health:  curl https://<modal-url>/health

Requires Modal secrets:
    modal secret create video-generator-secrets \
        GOOGLE_API_KEY=<your-key> \
        ELEVENLABS_API_KEY=<your-key>
"""
import modal
from modal import Image, Volume, asgi_app
from starlette.requests import Request

app = modal.App("video-generator-v2")

# Persistent volume for caching cloned voices and temp files
volume = Volume.from_name("video-generator-vol", create_if_missing=True)

image = (
    Image.debian_slim(python_version="3.12")
    .run_commands(
        "apt-get update && apt-get install -y --no-install-recommends "
        "ffmpeg poppler-utils fonts-dejavu-core && rm -rf /var/lib/apt/lists/*",
    )
    .pip_install(
        "google-genai>=1.0.0",
        "moviepy>=2.0.0",
        "Pillow>=10.0.0",
        "edge-tts>=6.1.0",
        "openai>=1.0.0",
        "rich>=13.0.0",
        "python-dotenv>=1.0.0",
        "python-pptx>=0.6.21",
        "pdf2image>=1.16.0",
        "scipy>=1.10.0",
        "numpy>=1.24.0",
        "requests>=2.28.0",
        "python-multipart",
        "fastapi",
        "opencv-python-headless>=4.8.0",
        "playwright>=1.40.0",
    )
    .run_commands("python -m playwright install --with-deps chromium")
    .add_local_dir("src", remote_path="/app/src")
)

secrets = modal.Secret.from_name("video-generator-secrets")


@app.function(
    image=image,
    secrets=[secrets],
    timeout=1800,  # 30 min — video generation is slow
    memory=4096,
    cpu=4,
    volumes={"/cache": volume},
    min_containers=1,  # Keep 1 container warm to avoid cold starts
)
def create_video_worker(
    job_id: str,
    files: dict[str, bytes],
    voice: str = "Smritika",
    tts_engine: str = "elevenlabs",
    voice_volume: float = 5.0,
    voice_speed: float = 1.0,
    music_volume: float = 0.03,
    style: str = "marketing",
    context: str = "",
    product: str = "",
    tone: str = "professional and engaging",
    resolution: str = "1080p",
    max_workers: int = 3,
    script_duration: int = 60,
    scene_duration: int = 5,
    storyline: str = "",
    generate_music: bool = False,
    music_prompt: str = "",
    music_engine: str = "auto",
    ai_order: bool = True,
    clone_voice: str = "",
    clone_from_key: str = "",
    clone_accent: str = "",
    clone_gender: str = "",
    clone_age: str = "",
    generate_intro: bool = False,
    generate_outro: bool = False,
    bookend_job_id: str = "",
    intro_option: int = 0,
    outro_option: int = 0,
    intro_veo_prompt: str = "",
    outro_veo_prompt: str = "",
):
    """Worker that runs the full create pipeline with live logging."""
    import sys
    import io
    import re
    import json
    import base64
    import tempfile
    import shutil
    import threading
    import time

    # ── MUST install stdout/stderr capture BEFORE any src imports ──
    # Rich Console() captures sys.stdout at creation time (module level),
    # so we must replace sys.stdout/stderr first.

    sys.path.insert(0, "/app")
    from pathlib import Path

    log_dir = Path(f"/cache/jobs/{job_id}")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "log.txt"
    status_file = log_dir / "status.json"
    ansi_re = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')

    # Buffer logs and flush to volume periodically
    log_buffer = []
    log_lock = threading.Lock()
    flush_stop = threading.Event()

    def flush_logs():
        """Background thread: write buffered logs to volume every 2s."""
        while not flush_stop.is_set():
            flush_stop.wait(2)
            _do_flush()

    def _do_flush():
        with log_lock:
            if not log_buffer:
                return
            batch = list(log_buffer)
            log_buffer.clear()
        with open(log_file, "a") as f:
            for line in batch:
                f.write(line + "\n")
        try:
            volume.commit()
        except Exception:
            pass

    def append_log(msg):
        with log_lock:
            log_buffer.append(msg)

    def write_status(state, error=""):
        status_file.write_text(json.dumps({"state": state, "error": error}))
        try:
            volume.commit()
        except Exception:
            pass

    class LogCapture(io.TextIOBase):
        def __init__(self, original):
            self.original = original
            self._line_buf = ""

        def write(self, s):
            if self.original:
                self.original.write(s)
            if not s:
                return 0
            # Buffer partial lines, emit on newline
            self._line_buf += s
            while "\n" in self._line_buf:
                line, self._line_buf = self._line_buf.split("\n", 1)
                clean = ansi_re.sub("", line).strip()
                if clean and len(clean) > 2 and not clean.startswith("━"):
                    append_log(clean)
            return len(s)

        def flush(self):
            if self.original:
                self.original.flush()
            # Flush any remaining partial line
            if self._line_buf:
                clean = ansi_re.sub("", self._line_buf).strip()
                if clean and len(clean) > 2:
                    append_log(clean)
                self._line_buf = ""

        @property
        def encoding(self):
            return getattr(self.original, "encoding", "utf-8")

    # Install capture BEFORE importing src modules
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    sys.stdout = LogCapture(old_stdout)
    sys.stderr = LogCapture(old_stderr)

    # Start background flush thread
    flush_thread = threading.Thread(target=flush_logs, daemon=True)
    flush_thread.start()

    write_status("running")
    append_log("Starting video generation pipeline...")
    _do_flush()  # Ensure first message is visible immediately

    try:
        # Now import src modules — their Console() will capture our LogCapture
        from src.pipeline.veo_pipeline import create_marketing_video_veo

        work_dir = Path(tempfile.mkdtemp())
        content_dir = work_dir / "content"
        content_dir.mkdir()

        for filename, data in files.items():
            (content_dir / filename).write_bytes(data)

        append_log(f"Loaded {len(files)} input file(s)")

        output_path = work_dir / "output.mp4"

        full_context = context
        if product:
            full_context = f"Product: {product}. {context}" if context else f"Product: {product}"

        effective_voice = voice
        effective_music_path = None

        # Phase 1: Voice Cloning (optional)
        if clone_voice and clone_from_key and clone_from_key in files:
            append_log(f"Cloning voice: {clone_voice}...")
            try:
                from src.ai.tts_engine import clone_voice_elevenlabs
                clone_audio_path = content_dir / clone_from_key
                voice_id = clone_voice_elevenlabs(
                    name=clone_voice,
                    audio_files=[clone_audio_path],
                    accent=clone_accent,
                    gender=clone_gender,
                    age=clone_age,
                )
                effective_voice = clone_voice
                tts_engine = "elevenlabs"
                append_log(f"Voice cloned: {clone_voice}")
            except Exception as e:
                append_log(f"Voice cloning failed: {e} — using default voice")

        # Resolve bookend image paths from volume (if user selected from gallery)
        resolved_intro_image = None
        resolved_outro_image = None
        resolved_intro_veo = intro_veo_prompt
        resolved_outro_veo = outro_veo_prompt

        if bookend_job_id and (generate_intro or generate_outro):
            bookend_dir = Path(f"/cache/bookends/{bookend_job_id}/images")
            result_file = Path(f"/cache/bookends/{bookend_job_id}/result.json")
            if result_file.exists():
                bk_result = json.loads(result_file.read_text())
                if generate_intro and intro_option > 0:
                    for opt in bk_result.get("intro_options", []):
                        if opt["option_number"] == intro_option and opt.get("image_filename"):
                            src = bookend_dir / opt["image_filename"]
                            if src.exists():
                                dest = work_dir / f"intro_selected.png"
                                shutil.copy2(str(src), str(dest))
                                resolved_intro_image = dest
                                if not resolved_intro_veo:
                                    resolved_intro_veo = opt.get("veo_motion_prompt", "")
                                append_log(f"Using pre-selected intro frame: {opt['title_text']}")
                if generate_outro and outro_option > 0:
                    for opt in bk_result.get("outro_options", []):
                        if opt["option_number"] == outro_option and opt.get("image_filename"):
                            src = bookend_dir / opt["image_filename"]
                            if src.exists():
                                dest = work_dir / f"outro_selected.png"
                                shutil.copy2(str(src), str(dest))
                                resolved_outro_image = dest
                                if not resolved_outro_veo:
                                    resolved_outro_veo = opt.get("veo_motion_prompt", "")
                                append_log(f"Using pre-selected outro frame: {opt['title_text']}")

        # Phase 3: Create Video
        append_log("Starting video pipeline...")
        create_marketing_video_veo(
            input_path=content_dir,
            output_path=output_path,
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
            generate_intro=generate_intro,
            generate_outro=generate_outro,
            product=product,
            intro_image_path=resolved_intro_image,
            outro_image_path=resolved_outro_image,
            intro_veo_prompt=resolved_intro_veo,
            outro_veo_prompt=resolved_outro_veo,
        )

        # Phase 4: Generate music (optional)
        if generate_music and output_path.exists():
            append_log("Generating background music...")
            try:
                from src.generators.music_generator import generate_music as gen_music, get_music_prompt_for_tone
                from src.pipeline.veo_pipeline import add_background_music_to_file
                from moviepy import VideoFileClip

                clip = VideoFileClip(str(output_path))
                final_duration = int(clip.duration) + 1
                clip.close()

                gen_duration = min(final_duration, 30)
                prompt = music_prompt or get_music_prompt_for_tone(tone)
                temp_music = work_dir / "temp_music.mp3"

                gen_music(
                    prompt=prompt,
                    output_path=temp_music,
                    duration=gen_duration,
                    engine=music_engine,
                )

                if temp_music.exists():
                    temp_with_music = work_dir / "temp_with_music.mp4"
                    shutil.move(str(output_path), str(temp_with_music))
                    add_background_music_to_file(
                        temp_with_music, temp_music, output_path,
                        music_volume=music_volume,
                    )
                    append_log("Background music added")
            except Exception as e:
                append_log(f"Music generation failed: {e}")

        # Build cost estimation
        num_scenes = len(files)
        log_text = log_file.read_text() if log_file.exists() else ""
        used_veo = "veo" in log_text.lower()
        used_tts = "elevenlabs" in log_text.lower() or tts_engine == "elevenlabs"
        used_music = generate_music

        cost = {
            "gemini_vision": round(max(num_scenes, 1) * 0.003, 3),
            "veo_animation": round(num_scenes * 0.035, 2) if used_veo else 0,
            "tts": round(num_scenes * 0.005, 3) if used_tts else 0,
            "music": 0.03 if used_music else 0,
            "num_scenes": num_scenes,
        }
        cost["total"] = round(sum([cost["gemini_vision"], cost["veo_animation"], cost["tts"], cost["music"]]), 2)

        # Save output files to volume for streaming download
        append_log("Saving final output...")
        _do_flush()
        result = {"cost": cost}

        if output_path.exists():
            dest = log_dir / "output.mp4"
            shutil.copy2(str(output_path), str(dest))
            result["has_video"] = True

        audio_path = output_path.with_suffix(".mp3")
        if audio_path.exists():
            dest = log_dir / "output.mp3"
            shutil.copy2(str(audio_path), str(dest))
            result["has_audio"] = True

        music_path = output_path.with_name(output_path.stem + "_music.mp3")
        if music_path.exists():
            dest = log_dir / "output_music.mp3"
            shutil.copy2(str(music_path), str(dest))
            result["has_music"] = True

        # Save lightweight result (no base64) to volume
        result_file = log_dir / "result.json"
        result_file.write_text(json.dumps(result))
        append_log("Done!")
        _do_flush()
        write_status("done")

        shutil.rmtree(str(work_dir), ignore_errors=True)
        return result

    except Exception as e:
        append_log(f"ERROR: {e}")
        _do_flush()
        write_status("error", str(e))
        raise
    finally:
        flush_stop.set()
        _do_flush()
        sys.stdout = old_stdout
        sys.stderr = old_stderr


@app.function(
    image=image,
    secrets=[secrets],
    timeout=60,
    memory=512,
    cpu=1,
)
def list_voices_worker():
    """Worker that lists all available ElevenLabs voices."""
    import sys
    sys.path.insert(0, "/app")
    from src.ai.tts_engine import list_elevenlabs_voices
    return list_elevenlabs_voices()


@app.function(
    image=image,
    secrets=[secrets],
    timeout=300,
    memory=2048,
    cpu=2,
)
def voice_clone_worker(
    audio_files: dict[str, bytes],
    name: str,
    description: str = "",
    accent: str = "",
    gender: str = "",
    age: str = "",
):
    """Worker that clones a voice using ElevenLabs."""
    import sys
    import tempfile
    import shutil

    sys.path.insert(0, "/app")
    from pathlib import Path
    from src.ai.tts_engine import clone_voice_elevenlabs

    work_dir = Path(tempfile.mkdtemp())

    # Write audio files to disk
    audio_paths = []
    for filename, data in audio_files.items():
        p = work_dir / filename
        p.write_bytes(data)
        audio_paths.append(p)

    try:
        voice_id = clone_voice_elevenlabs(
            name=name,
            audio_files=audio_paths,
            description=description,
            accent=accent,
            gender=gender,
            age=age,
        )
        result = {"success": True, "voice_name": name, "voice_id": voice_id}
    except Exception as e:
        result = {"success": False, "error": str(e)}

    shutil.rmtree(str(work_dir), ignore_errors=True)
    return result


@app.function(
    image=image,
    secrets=[secrets],
    timeout=1800,
    memory=4096,
    cpu=4,
    volumes={"/cache": volume},
)
def storyboard_worker(
    job_id: str,
    url: str,
    storyline: str = "",
    product: str = "",
    num_scenes: int = 6,
    tone: str = "professional and engaging",
    style: str = "marketing",
    aspect_ratio: str = "16:9",
    skip_screenshots: bool = False,
    skip_imagen: bool = False,
):
    """Worker that runs the storyboard pipeline: crawl → plan → imagen → assemble."""
    import sys
    import io
    import re
    import json
    import tempfile
    import shutil
    import threading

    sys.path.insert(0, "/app")
    from pathlib import Path

    log_dir = Path(f"/cache/storyboard/{job_id}")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "log.txt"
    status_file = log_dir / "status.json"
    images_dir = log_dir / "images"
    images_dir.mkdir(exist_ok=True)
    ansi_re = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')

    log_buffer = []
    log_lock = threading.Lock()
    flush_stop = threading.Event()

    def flush_logs():
        while not flush_stop.is_set():
            flush_stop.wait(2)
            _do_flush()

    def _do_flush():
        with log_lock:
            if not log_buffer:
                return
            batch = list(log_buffer)
            log_buffer.clear()
        with open(log_file, "a") as f:
            for line in batch:
                f.write(line + "\n")
        try:
            volume.commit()
        except Exception:
            pass

    def append_log(msg):
        with log_lock:
            log_buffer.append(msg)

    def write_status(state, error=""):
        status_file.write_text(json.dumps({"state": state, "error": error}))
        try:
            volume.commit()
        except Exception:
            pass

    class LogCapture(io.TextIOBase):
        def __init__(self, original):
            self.original = original
            self._line_buf = ""

        def write(self, s):
            if self.original:
                self.original.write(s)
            if not s:
                return 0
            self._line_buf += s
            while "\n" in self._line_buf:
                line, self._line_buf = self._line_buf.split("\n", 1)
                clean = ansi_re.sub("", line).strip()
                if clean and len(clean) > 2 and not clean.startswith("━"):
                    append_log(clean)
            return len(s)

        def flush(self):
            if self.original:
                self.original.flush()
            if self._line_buf:
                clean = ansi_re.sub("", self._line_buf).strip()
                if clean and len(clean) > 2:
                    append_log(clean)
                self._line_buf = ""

        @property
        def encoding(self):
            return getattr(self.original, "encoding", "utf-8")

    old_stdout = sys.stdout
    old_stderr = sys.stderr
    sys.stdout = LogCapture(old_stdout)
    sys.stderr = LogCapture(old_stderr)

    flush_thread = threading.Thread(target=flush_logs, daemon=True)
    flush_thread.start()

    write_status("running")
    append_log("Starting storyboard generation...")
    _do_flush()

    try:
        work_dir = Path(tempfile.mkdtemp())
        screenshots_dir = work_dir / "screenshots"
        generated_dir = work_dir / "generated"
        sequence_dir = work_dir / "sequence"
        screenshots_dir.mkdir()
        generated_dir.mkdir()
        sequence_dir.mkdir()

        all_captures = []
        capture_labels = []

        # Phase 1: Website crawling
        if not skip_screenshots:
            append_log(f"Phase 1: Crawling website {url}...")
            _do_flush()
            from src.pipeline.website_screenshotter import crawl_and_capture_sync
            captures_result = crawl_and_capture_sync(
                url=url,
                output_dir=screenshots_dir,
                aspect_ratio=aspect_ratio,
            )
            all_captures = [c.path for c in captures_result]
            capture_labels = [c.label for c in captures_result]
            append_log(f"Captured {len(all_captures)} screenshots")

            # Copy screenshots to volume for preview
            for cap in captures_result:
                dest = images_dir / f"ss_{cap.index:03d}_{cap.label}.png"
                shutil.copy2(str(cap.path), str(dest))
            _do_flush()
        else:
            append_log("Phase 1: Skipped screenshots")

        # Phase 2: AI scene planning
        append_log(f"Phase 2: Planning {num_scenes} scenes with AI...")
        _do_flush()
        from src.pipeline.storyboard_planner import plan_storyboard, write_storyboard_text
        sb = plan_storyboard(
            storyline=storyline,
            url=url,
            captures=all_captures,
            capture_labels=capture_labels,
            num_scenes=num_scenes,
            product=product,
            tone=tone,
            style=style,
        )
        append_log(f"Planned {len(sb.scenes)} scenes")

        storyboard_txt = work_dir / "storyboard.txt"
        write_storyboard_text(sb, storyboard_txt)
        shutil.copy2(str(storyboard_txt), str(log_dir / "storyboard.txt"))

        # Phase 3: Imagen generation
        generated_images = {}
        if not skip_imagen:
            append_log(f"Phase 3: Generating {len(sb.scenes)} AI images...")
            _do_flush()
            from src.ai.imagen_generator import generate_image

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
                story_context = storyline[:120].rstrip()
                product_tag = f", related to {product}" if product else ""
                imagen_prompt = f"{prefix} {scene.image_description} Context: {story_context}{product_tag}."

                append_log(f"  Generating scene {scene.scene_number}: {scene.title}...")
                try:
                    generate_image(
                        prompt=imagen_prompt,
                        output_path=filepath,
                        aspect_ratio=aspect_ratio,
                    )
                    generated_images[scene.scene_number] = filepath
                    # Copy to volume
                    dest = images_dir / f"gen_{scene.scene_number:03d}_{slug}.png"
                    shutil.copy2(str(filepath), str(dest))
                    append_log(f"  Generated scene {scene.scene_number}")
                except Exception as e:
                    append_log(f"  Failed scene {scene.scene_number}: {e}")
        else:
            append_log("Phase 3: Skipped Imagen generation")

        # Phase 4: Assemble sequence folder
        append_log("Phase 4: Assembling sequence...")
        assembled = 0
        for scene in sb.scenes:
            slug = re.sub(r'[^\w\s-]', '', scene.title.lower())
            slug = re.sub(r'[\s_-]+', '_', slug).strip('_')[:40]

            if 0 <= scene.best_capture_index < len(all_captures):
                src_path = all_captures[scene.best_capture_index]
                if src_path.exists():
                    ss_dest = sequence_dir / f"{scene.scene_number:03d}_{slug}_screenshot.png"
                    shutil.copy2(str(src_path), str(ss_dest))
                    assembled += 1

            if scene.scene_number in generated_images:
                gen_src = generated_images[scene.scene_number]
                gen_dest = sequence_dir / f"{scene.scene_number:03d}_{slug}_generated.png"
                shutil.copy2(str(gen_src), str(gen_dest))
                assembled += 1

        # Copy sequence to volume for use by create endpoint
        seq_vol_dir = log_dir / "sequence"
        seq_vol_dir.mkdir(exist_ok=True)
        for f in sorted(sequence_dir.iterdir()):
            shutil.copy2(str(f), str(seq_vol_dir / f.name))

        append_log(f"Assembled {assembled} files for {len(sb.scenes)} scenes")

        # Build result
        image_files = sorted([f.name for f in images_dir.iterdir()
                              if f.suffix.lower() in ('.png', '.jpg', '.jpeg')])
        sequence_files = sorted([f.name for f in seq_vol_dir.iterdir()
                                 if f.suffix.lower() in ('.png', '.jpg', '.jpeg')])

        scenes_data = []
        for scene in sb.scenes:
            scenes_data.append({
                "scene_number": scene.scene_number,
                "title": scene.title,
                "voiceover_script": scene.voiceover_script,
                "image_description": scene.image_description,
                "best_capture_index": scene.best_capture_index,
            })

        result = {
            "scenes": scenes_data,
            "images": image_files,
            "sequence_files": sequence_files,
            "num_screenshots": len(all_captures),
            "num_generated": len(generated_images),
        }

        result_file = log_dir / "result.json"
        result_file.write_text(json.dumps(result))
        volume.commit()
        append_log("Storyboard complete!")
        _do_flush()
        write_status("done")

        shutil.rmtree(str(work_dir), ignore_errors=True)
        return result

    except Exception as e:
        append_log(f"ERROR: {e}")
        _do_flush()
        write_status("error", str(e))
        raise
    finally:
        flush_stop.set()
        _do_flush()
        sys.stdout = old_stdout
        sys.stderr = old_stderr


@app.function(
    image=image,
    secrets=[secrets],
    timeout=600,
    memory=2048,
    cpu=2,
)
def post_video_worker(
    video_bytes: bytes,
    video_speed: float = 1.0,
    voice_volume: float = 5.0,
    music_volume: float = 0.03,
    overall_volume: float = 0.0,
    voice_audio_bytes: bytes = b"",
    music_audio_bytes: bytes = b"",
):
    """Worker that runs post-processing on a video."""
    import sys
    import base64
    import tempfile
    import shutil

    sys.path.insert(0, "/app")
    from pathlib import Path
    from src.processing.post_processor import adjust_video

    work_dir = Path(tempfile.mkdtemp())
    input_path = work_dir / "input.mp4"
    output_path = work_dir / "output_post.mp4"
    input_path.write_bytes(video_bytes)

    voice_audio_path = None
    music_audio_path = None

    if voice_audio_bytes:
        voice_audio_path = work_dir / "voice.mp3"
        voice_audio_path.write_bytes(voice_audio_bytes)

    if music_audio_bytes:
        music_audio_path = work_dir / "music.mp3"
        music_audio_path.write_bytes(music_audio_bytes)

    remix_mode = voice_audio_path is not None

    if remix_mode:
        adjust_video(
            input_video=input_path,
            output_video=output_path,
            video_speed=video_speed,
            voice_audio=voice_audio_path,
            music_audio=music_audio_path,
            voice_volume=voice_volume,
            music_volume=music_volume,
            extract_audio=True,
        )
    else:
        adjust_video(
            input_video=input_path,
            output_video=output_path,
            video_speed=video_speed,
            overall_volume=overall_volume if overall_volume > 0 else None,
            extract_audio=True,
        )

    response = {}
    if output_path.exists():
        response["video"] = base64.b64encode(output_path.read_bytes()).decode()

    audio_path = output_path.with_suffix(".mp3")
    if audio_path.exists():
        response["audio"] = base64.b64encode(audio_path.read_bytes()).decode()

    shutil.rmtree(str(work_dir), ignore_errors=True)
    return response


@app.function(
    image=image,
    secrets=[secrets],
    timeout=600,
    memory=2048,
    cpu=2,
    volumes={"/cache": volume},
)
def bookend_worker(
    job_id: str,
    product: str = "",
    storyline: str = "",
    tone: str = "professional and engaging",
    style: str = "marketing",
    context: str = "",
    generate_intro: bool = True,
    generate_outro: bool = True,
    aspect_ratio: str = "16:9",
    intro_prompt: str = "",
    outro_prompt: str = "",
    intro_ref_path: str = "",
    outro_ref_path: str = "",
):
    """Worker that generates bookend frame options (Gemini suggestions + Imagen images only, no Veo)."""
    import sys
    import json
    import shutil

    sys.path.insert(0, "/app")
    from pathlib import Path

    log_dir = Path(f"/cache/bookends/{job_id}")
    log_dir.mkdir(parents=True, exist_ok=True)
    images_dir = log_dir / "images"
    images_dir.mkdir(exist_ok=True)
    status_file = log_dir / "status.json"

    def write_status(state, error=""):
        status_file.write_text(json.dumps({"state": state, "error": error}))
        try:
            volume.commit()
        except Exception:
            pass

    write_status("running")

    try:
        from src.pipeline.bookend_generator import generate_bookend_suggestions, generate_bookend_images
        from concurrent.futures import ThreadPoolExecutor, as_completed

        result = {"intro_options": [], "outro_options": []}

        def _generate_type(bookend_type):
            """Generate suggestions + images for one bookend type."""
            # Append user's custom prompt to context
            user_prompt = intro_prompt if bookend_type == "intro" else outro_prompt
            ref_path = intro_ref_path if bookend_type == "intro" else outro_ref_path
            full_context = context

            # Build context from user prompt + reference image description
            context_parts = []
            if context:
                context_parts.append(context)
            if user_prompt:
                context_parts.append(f"User direction: {user_prompt}")

            # If reference image provided, analyze it with Gemini Vision and add to context
            if ref_path and Path(ref_path).exists():
                try:
                    from src.ai.gemini_client import generate_with_content_blocks
                    ref_bytes = Path(ref_path).read_bytes()
                    suffix = Path(ref_path).suffix.lower()
                    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}.get(suffix.lstrip("."), "image/png")
                    ref_desc = generate_with_content_blocks(
                        blocks=[
                            (ref_bytes, mime),
                            "Describe this image's visual style, color palette, composition, and mood in 2-3 sentences. Focus on design elements that should be replicated.",
                        ],
                        max_output_tokens=300,
                    )
                    if ref_desc:
                        context_parts.append(f"Reference image style to match: {ref_desc}")
                except Exception as e:
                    # Fallback: just note there's a reference
                    context_parts.append("User provided a reference image — match its visual style and color palette")

            full_context = ". ".join(context_parts) if context_parts else ""

            suggestions = generate_bookend_suggestions(
                bookend_type=bookend_type,
                product=product,
                storyline=storyline,
                tone=tone,
                style=style,
                context=full_context,
            )
            image_paths = generate_bookend_images(
                suggestions, images_dir, bookend_type, aspect_ratio=aspect_ratio,
            )
            options = []
            for s, p in zip(suggestions, image_paths):
                options.append({
                    "option_number": s.option_number,
                    "title_text": s.title_text,
                    "subtitle_text": s.subtitle_text,
                    "veo_motion_prompt": s.veo_motion_prompt,
                    "image_filename": p.name if p and p.exists() else None,
                })
            return bookend_type, options

        # Run intro and outro generation in parallel
        types_to_generate = [(t, e) for t, e in [("intro", generate_intro), ("outro", generate_outro)] if e]

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(_generate_type, t) for t, _ in types_to_generate]
            for future in as_completed(futures):
                bookend_type, options = future.result()
                result[f"{bookend_type}_options"] = options

        result_file = log_dir / "result.json"
        result_file.write_text(json.dumps(result))
        volume.commit()
        write_status("done")
        return result

    except Exception as e:
        write_status("error", str(e))
        raise


LANDING_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Video Generator — AI Marketing Videos</title>
<script src="https://cdn.jsdelivr.net/npm/@clerk/clerk-js@5/dist/clerk.browser.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0f0f0f;color:#e0e0e0;min-height:100vh}

/* Nav */
.nav{display:flex;justify-content:space-between;align-items:center;padding:16px 48px;border-bottom:1px solid #1a1a1a;position:sticky;top:0;background:rgba(15,15,15,.95);backdrop-filter:blur(12px);z-index:100}
.nav-logo{font-size:1.2rem;font-weight:700;background:linear-gradient(135deg,#f97316,#ec4899);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.nav-btns{display:flex;gap:10px}
.nav-btn{padding:8px 20px;border-radius:8px;border:none;font-size:.85rem;font-weight:600;cursor:pointer;transition:all .15s}
.nav-btn-ghost{background:transparent;color:#ccc;border:1px solid #333}
.nav-btn-ghost:hover{border-color:#f97316;color:#fff}
.nav-btn-primary{background:linear-gradient(135deg,#f97316,#ec4899);color:#fff}
.nav-btn-primary:hover{opacity:.9;transform:translateY(-1px)}

/* Hero */
.hero{text-align:center;padding:100px 48px 80px;max-width:900px;margin:0 auto}
.hero h1{font-size:3.2rem;font-weight:800;line-height:1.15;margin-bottom:20px;background:linear-gradient(135deg,#fff 0%,#ccc 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.hero p{font-size:1.15rem;color:#888;line-height:1.6;margin-bottom:36px;max-width:650px;margin-left:auto;margin-right:auto}
.hero-cta{padding:16px 40px;border-radius:12px;border:none;font-size:1.1rem;font-weight:700;cursor:pointer;background:linear-gradient(135deg,#f97316,#ec4899);color:#fff;transition:all .15s;display:inline-block}
.hero-cta:hover{opacity:.9;transform:translateY(-2px);box-shadow:0 8px 30px rgba(249,115,22,.3)}
.hero-sub{font-size:.8rem;color:#555;margin-top:14px}

/* Section */
.landing-section{padding:80px 48px;max-width:1200px;margin:0 auto}
.section-title{font-size:2rem;font-weight:700;text-align:center;margin-bottom:12px}
.section-subtitle{font-size:1rem;color:#888;text-align:center;margin-bottom:48px}

/* Sample Videos */
.samples-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}
.sample-card{background:#161616;border:1px solid #222;border-radius:12px;overflow:hidden;transition:all .15s}
.sample-card:hover{border-color:#f97316;transform:translateY(-4px);box-shadow:0 12px 40px rgba(0,0,0,.4)}
.sample-video-wrap{position:relative;width:100%;aspect-ratio:16/9;background:#0a0a0a;overflow:hidden}
.sample-video-wrap video{width:100%;height:100%;object-fit:cover}
.sample-video-wrap .no-sample{display:flex;align-items:center;justify-content:center;width:100%;height:100%;color:#444;font-size:.85rem}
.sample-info{padding:14px 16px}
.sample-info h3{font-size:1rem;font-weight:600;margin-bottom:4px}
.sample-info p{font-size:.78rem;color:#888;line-height:1.4}

/* Steps */
.steps-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:20px}
.step-card{background:#161616;border:1px solid #222;border-radius:12px;padding:28px 24px;text-align:center;position:relative;transition:all .15s}
.step-card:hover{border-color:#333;transform:translateY(-2px)}
.step-num{width:36px;height:36px;border-radius:50%;background:linear-gradient(135deg,#f97316,#ec4899);color:#fff;font-size:.9rem;font-weight:700;display:flex;align-items:center;justify-content:center;margin:0 auto 16px}
.step-card h3{font-size:1rem;font-weight:600;margin-bottom:8px}
.step-card p{font-size:.82rem;color:#888;line-height:1.5}
.step-arrow{position:absolute;right:-14px;top:50%;transform:translateY(-50%);color:#333;font-size:1.2rem}

/* Features */
.features-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
.feature-card{background:#161616;border:1px solid #222;border-radius:10px;padding:24px;transition:all .15s}
.feature-card:hover{border-color:#333}
.feature-icon{font-size:1.8rem;margin-bottom:12px}
.feature-card h3{font-size:.95rem;font-weight:600;margin-bottom:6px}
.feature-card p{font-size:.8rem;color:#888;line-height:1.5}

/* Footer */
.footer{text-align:center;padding:40px 48px;border-top:1px solid #1a1a1a;color:#555;font-size:.8rem}
.footer a{color:#888;text-decoration:none}
.footer a:hover{color:#f97316}

@media(max-width:768px){
  .hero h1{font-size:2rem}
  .samples-grid,.steps-grid{grid-template-columns:1fr}
  .features-grid{grid-template-columns:1fr 1fr}
  .step-arrow{display:none}
  .nav{padding:12px 20px}
  .hero,.landing-section{padding-left:20px;padding-right:20px}
}
</style>
</head>
<body>

<nav class="nav">
  <div class="nav-logo">Video Generator</div>
  <div class="nav-btns">
    <button class="nav-btn nav-btn-ghost" id="navSignIn">Sign In</button>
    <button class="nav-btn nav-btn-primary" id="navGetStarted">Get Started</button>
  </div>
</nav>

<section class="hero">
  <h1>Turn any content into professional marketing videos</h1>
  <p>Upload images, presentations, or videos. Get AI-generated voiceover, cinematic animation, and background music — in minutes.</p>
  <button class="hero-cta" id="heroCta">Experience it</button>
  <div class="hero-sub">No credit card required. Powered by Gemini, Veo 3.1 &amp; ElevenLabs.</div>
</section>

<section class="landing-section">
  <h2 class="section-title">See it in action</h2>
  <p class="section-subtitle">Sample videos generated by the pipeline — hover to preview</p>
  <div class="samples-grid">
    <div class="sample-card">
      <div class="sample-video-wrap" id="lsv-marketing"><div class="no-sample">Loading...</div></div>
      <div class="sample-info"><h3>Marketing</h3><p>Persuasive pitch with hooks, pain points, proof, and strong CTA</p></div>
    </div>
    <div class="sample-card">
      <div class="sample-video-wrap" id="lsv-feature-explainer"><div class="no-sample">Loading...</div></div>
      <div class="sample-info"><h3>Feature Explainer</h3><p>Product walkthrough showing what each feature does and why it matters</p></div>
    </div>
    <div class="sample-card">
      <div class="sample-video-wrap" id="lsv-tutorial-explainer"><div class="no-sample">Loading...</div></div>
      <div class="sample-info"><h3>Tutorial Explainer</h3><p>Step-by-step guide with clear instructions and practical tips</p></div>
    </div>
  </div>
</section>

<section class="landing-section">
  <h2 class="section-title">How it works</h2>
  <p class="section-subtitle">From raw content to polished video in 4 steps</p>
  <div class="steps-grid">
    <div class="step-card">
      <div class="step-num">1</div>
      <h3>Upload</h3>
      <p>Drop images, PowerPoint, PDF, or video files. Or paste a website URL for auto-capture.</p>
      <span class="step-arrow">&#8594;</span>
    </div>
    <div class="step-card">
      <div class="step-num">2</div>
      <h3>AI Analysis</h3>
      <p>Gemini Vision reads your content, extracts text, and writes a cohesive narrative script.</p>
      <span class="step-arrow">&#8594;</span>
    </div>
    <div class="step-card">
      <div class="step-num">3</div>
      <h3>Animate &amp; Voice</h3>
      <p>Veo 3.1 creates cinematic animations. ElevenLabs generates expressive voiceover.</p>
      <span class="step-arrow">&#8594;</span>
    </div>
    <div class="step-card">
      <div class="step-num">4</div>
      <h3>Download</h3>
      <p>Get your finished video with music, voiceover, and branded intro/outro frames.</p>
    </div>
  </div>
</section>

<section class="landing-section">
  <h2 class="section-title">Everything you need</h2>
  <p class="section-subtitle">A complete video production pipeline in one tool</p>
  <div class="features-grid">
    <div class="feature-card">
      <div class="feature-icon">&#128444;</div>
      <h3>Any Input Type</h3>
      <p>Images, PowerPoint, PDF, videos — mix any combination in one folder</p>
    </div>
    <div class="feature-card">
      <div class="feature-icon">&#127908;</div>
      <h3>Voice Cloning</h3>
      <p>Clone any voice from a sample. Or choose from premium ElevenLabs voices.</p>
    </div>
    <div class="feature-card">
      <div class="feature-icon">&#127925;</div>
      <h3>AI Music</h3>
      <p>Auto-generate background music that matches your tone and style</p>
    </div>
    <div class="feature-card">
      <div class="feature-icon">&#128214;</div>
      <h3>Storyline-Driven</h3>
      <p>Provide a narrative arc — scripts, animation, and music all follow it</p>
    </div>
    <div class="feature-card">
      <div class="feature-icon">&#127916;</div>
      <h3>Branded Frames</h3>
      <p>AI-generated intro and outro cards with your product name and CTA</p>
    </div>
    <div class="feature-card">
      <div class="feature-icon">&#128176;</div>
      <h3>Cost-Effective</h3>
      <p>~$0.25-0.65 per video. Free alternative with Edge TTS available.</p>
    </div>
  </div>
</section>

<footer class="footer">
  <p>Powered by Google Gemini &bull; Veo 3.1 &bull; Imagen 4.0 &bull; ElevenLabs</p>
</footer>

<script>
(async()=>{
  const clerk=new window.Clerk('__CLERK_PK__');
  await clerk.load();

  const navSignIn=document.getElementById('navSignIn');
  const navGetStarted=document.getElementById('navGetStarted');
  const heroCta=document.getElementById('heroCta');

  if(clerk.user){
    navSignIn.style.display='none';
    navGetStarted.textContent='Go to App';
    navGetStarted.onclick=()=>window.location.href='/app';
    heroCta.textContent='Go to App';
    heroCta.onclick=()=>window.location.href='/app';
  }else{
    navSignIn.onclick=()=>clerk.openSignIn({afterSignInUrl:'/app'});
    navGetStarted.onclick=()=>clerk.openSignUp({afterSignUpUrl:'/app'});
    heroCta.onclick=()=>clerk.openSignUp({afterSignUpUrl:'/app'});
  }

  // Load sample videos
  ['marketing','feature-explainer','tutorial-explainer'].forEach(style=>{
    const wrap=document.getElementById('lsv-'+style);
    fetch('/sample/'+style,{method:'HEAD'}).then(r=>{
      if(!r.ok)throw new Error('none');
      wrap.innerHTML='';
      const v=document.createElement('video');
      v.src='/sample/'+style;v.muted=true;v.loop=true;v.playsInline=true;v.preload='none';
      v.style.opacity='0';v.style.transition='opacity .3s';
      v.addEventListener('mouseenter',()=>{v.preload='auto';v.play()});
      v.addEventListener('mouseleave',()=>{v.pause();v.currentTime=0});
      v.addEventListener('loadeddata',()=>{v.style.opacity='1'});
      wrap.appendChild(v);
      if(wrap.closest('.sample-card')===document.querySelector('.sample-card')){v.preload='auto';v.play()}
    }).catch(()=>{
      wrap.innerHTML='<div class="no-sample">Coming soon</div>';
    });
  });
})();
</script>
</body>
</html>"""


APP_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Video Generator</title>
<script src="https://cdn.jsdelivr.net/npm/@clerk/clerk-js@5/dist/clerk.browser.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0f0f0f;color:#e0e0e0;min-height:100vh}
.container{max-width:1600px;margin:0 auto;padding:40px 64px}
h1{font-size:1.8rem;font-weight:700;margin-bottom:8px;background:linear-gradient(135deg,#f97316,#ec4899);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.subtitle{color:#888;margin-bottom:32px;font-size:.95rem}

.section{background:#161616;border:1px solid #222;border-radius:12px;padding:20px;margin-bottom:20px}
.section-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}
.section-head h2{font-size:1.2rem;margin:0}
.step-badge{font-size:.7rem;background:#222;color:#888;padding:3px 10px;border-radius:12px;text-transform:uppercase;letter-spacing:.5px}

/* Voice list */
.voice-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:8px;margin-bottom:16px}
.voice-card{background:#1a1a1a;border:1px solid #333;border-radius:8px;padding:10px 14px;cursor:pointer;transition:all .15s;text-align:center}
.voice-card:hover{border-color:#34d399;background:#1a1e1a}
.voice-card.selected{border-color:#34d399;background:#0d2818}
.voice-name{font-size:.9rem;font-weight:600;color:#e0e0e0}
.voice-cat{font-size:.7rem;color:#666;margin-top:2px}
.voice-loading{color:#666;font-size:.85rem;padding:12px;text-align:center}
.voice-selected-info{font-size:.85rem;color:#34d399;margin-top:8px}

/* Clone section inside voice panel */
.clone-toggle-row{display:flex;align-items:center;gap:8px;margin-top:12px;padding-top:12px;border-top:1px solid #222;cursor:pointer}
.clone-toggle-row:hover .clone-toggle-text{color:#34d399}
.clone-toggle-text{font-size:.9rem;color:#888;transition:color .15s}
.clone-arrow{color:#666;font-size:.7rem;transition:transform .2s}
.clone-arrow.open{transform:rotate(90deg)}
.clone-body{margin-top:16px}
.clone-upload-area{border:2px dashed #333;border-radius:12px;padding:28px;text-align:center;cursor:pointer;transition:all .2s;background:#1a1a1a}
.clone-upload-area:hover{border-color:#34d399;background:#1a1e1a}
.clone-upload-area.has-file{border-color:#34d399;border-style:solid}
.upload-icon{font-size:2rem;margin-bottom:8px;display:block}
.upload-text{font-size:1rem;color:#aaa;margin-bottom:4px}
.upload-hint{font-size:.75rem;color:#666}
.file-list{color:#34d399;font-weight:600;margin-top:6px;font-size:.85rem}
.btn-clone{background:linear-gradient(135deg,#10b981,#34d399);color:#fff;width:100%;margin-top:12px}
.btn-clone:hover{opacity:.9;transform:translateY(-1px)}
.btn-clone:disabled{opacity:.4;cursor:not-allowed;transform:none}
.clone-result{margin-top:12px;padding:10px 14px;border-radius:8px;font-size:.85rem}
.clone-result.success{background:#0d2818;border:1px solid #166534;color:#86efac}
.clone-result.error{background:#2d1111;border:1px solid #7f1d1d;color:#fca5a5}

/* Video gen section */
.upload-area{border:2px dashed #333;border-radius:12px;padding:40px;text-align:center;cursor:pointer;transition:all .2s;background:#1a1a1a;margin-bottom:20px}
.upload-area:hover,.upload-area.dragover{border-color:#f97316;background:#1a1a1e}
.upload-area.has-file{border-color:#34d399;border-style:solid}

.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:20px}
.form-group{display:flex;flex-direction:column;gap:4px}
.form-group.full{grid-column:1/-1}
.form-label{font-size:.75rem;color:#888;text-transform:uppercase;letter-spacing:.5px}
.form-input,.form-select,.form-textarea{background:#1a1a1a;color:#e0e0e0;border:1px solid #333;border-radius:8px;padding:10px 14px;font-size:.9rem;font-family:inherit}
.form-input:focus,.form-select:focus,.form-textarea:focus{outline:none;border-color:#f97316}
.form-textarea{resize:vertical;min-height:60px}

.toggle-row{display:flex;align-items:center;gap:8px;padding:6px 0}
.toggle{position:relative;width:40px;height:22px;cursor:pointer}
.toggle input{opacity:0;width:0;height:0}
.toggle-slider{position:absolute;inset:0;background:#333;border-radius:22px;transition:.2s}
.toggle-slider:before{content:'';position:absolute;height:16px;width:16px;left:3px;bottom:3px;background:#888;border-radius:50%;transition:.2s}
.toggle input:checked+.toggle-slider{background:#f97316}
.toggle input:checked+.toggle-slider:before{transform:translateX(18px);background:#fff}
.toggle-label{font-size:.9rem;color:#ccc}

.btn{padding:12px 28px;border-radius:10px;border:none;font-size:1rem;font-weight:600;cursor:pointer;transition:all .15s}
.btn-primary{background:linear-gradient(135deg,#f97316,#ec4899);color:#fff;width:100%;margin-top:8px}
.btn-primary:hover{opacity:.9;transform:translateY(-1px)}
.btn-primary:disabled{opacity:.4;cursor:not-allowed;transform:none}
.btn-secondary{background:#222;color:#e0e0e0;border:1px solid #333}
.btn-secondary:hover{background:#2a2a2a}
.btn-post{background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#fff;margin-top:8px}
.btn-post:hover{opacity:.9;transform:translateY(-1px)}
.btn-post:disabled{opacity:.4;cursor:not-allowed;transform:none}
.btn-sm{padding:6px 14px;font-size:.8rem;border-radius:6px}

.progress-wrap{display:none;margin:32px 0;text-align:center}
.progress-wrap.active{display:block}
.progress-bar{height:4px;background:#222;border-radius:4px;overflow:hidden;margin-bottom:12px}
.progress-bar-inner{height:100%;width:30%;background:linear-gradient(90deg,#f97316,#ec4899,#f97316);background-size:200% 100%;animation:progress 1.5s ease-in-out infinite;border-radius:4px}
@keyframes progress{0%{background-position:200% 0}100%{background-position:-200% 0}}
.progress-text{font-size:.9rem;color:#888}
.progress-sub{font-size:.8rem;color:#555;margin-top:4px}
.log-panel{background:#0a0a0a;border:1px solid #222;border-radius:8px;margin-top:16px;max-height:300px;overflow-y:auto;text-align:left}
.log-content{padding:12px 16px;font-family:'SF Mono',Monaco,Consolas,monospace;font-size:.78rem;line-height:1.6;color:#9ca3af;white-space:pre-wrap;word-break:break-word}
.log-content .log-line{display:block;padding:1px 0}
.log-content .log-line:last-child{color:#34d399}
.log-content .log-line.error{color:#fca5a5}

.error-msg{background:#2d1111;border:1px solid #7f1d1d;color:#fca5a5;padding:16px;border-radius:12px;margin-bottom:24px;display:none}
.error-msg.active{display:block}

.results{display:none}
.results.active{display:block}
.results-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:24px;flex-wrap:wrap;gap:12px}
.results-header h2{font-size:1.4rem}
.video-wrap{background:#161616;border-radius:12px;overflow:hidden;border:1px solid #222;margin-bottom:16px}
.video-wrap video{width:100%;display:block}
.dl-row{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
.cost-panel{background:#161616;border:1px solid #222;border-radius:10px;padding:16px 20px;margin-top:16px}
.cost-panel h4{font-size:.9rem;color:#34d399;margin-bottom:10px}
.cost-grid{display:grid;grid-template-columns:1fr 100px;gap:6px 20px;font-size:.84rem}
.cost-label{color:#888}.cost-val{color:#e0e0e0;text-align:right;font-family:'SF Mono',Monaco,Consolas,monospace;font-weight:500}
.cost-label.cost-total{color:#e0e0e0;font-weight:600;border-top:1px solid #333;padding-top:8px;margin-top:6px}
.cost-val.cost-total{color:#34d399;font-weight:700;font-size:.95rem;border-top:1px solid #333;padding-top:8px;margin-top:6px}

.avatar-panel{background:#161616;border:1px solid #222;border-radius:12px;padding:20px;margin-top:24px}
.avatar-panel h3{font-size:1.1rem;margin-bottom:12px;color:#60a5fa}
.avatar-guide{background:#0d1117;border:1px solid #1e2a3a;border-radius:8px;padding:14px 16px;margin-bottom:16px}
.avatar-guide-steps{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.avatar-step{display:flex;align-items:center;gap:8px;flex:1;min-width:160px}
.avatar-step-num{width:22px;height:22px;border-radius:50%;background:#3b82f6;color:#fff;font-size:.72rem;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.avatar-step-text{font-size:.78rem;color:#9ca3af;line-height:1.4}
.avatar-step-arrow{color:#444;font-size:1rem;flex-shrink:0}
.avatar-guide-note{font-size:.72rem;color:#555;margin-top:8px;margin-bottom:0}
.avatar-grid{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:12px;margin-bottom:16px;align-items:start}
.avatar-upload-area{background:#0a0a0a;border:1px dashed #333;border-radius:8px;padding:12px;text-align:center;cursor:pointer;transition:border-color .2s}
.avatar-upload-area:hover{border-color:#60a5fa}
.avatar-upload-area.has-file{border-color:#34d399;border-style:solid}
.btn-avatar{background:linear-gradient(135deg,#3b82f6,#6366f1);color:#fff;width:100%}
.btn-avatar:hover{opacity:.9;transform:translateY(-1px)}
.btn-avatar:disabled{opacity:.4;cursor:not-allowed;transform:none}
.post-panel{background:#161616;border:1px solid #222;border-radius:12px;padding:20px;margin-top:24px}
.post-panel h3{font-size:1.1rem;margin-bottom:16px;color:#a78bfa}
.post-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:16px}
.slider-group{display:flex;flex-direction:column;gap:4px}
.slider-group label{font-size:.75rem;color:#888;text-transform:uppercase;letter-spacing:.5px}
.slider-group input[type=range]{width:100%;accent-color:#8b5cf6}
.slider-val{font-size:.85rem;color:#ccc;text-align:center}

/* Style picker with sample videos */
.style-picker{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:20px}
.style-card{background:#1a1a1a;border:2px solid #333;border-radius:10px;overflow:hidden;cursor:pointer;transition:all .15s}
.style-card:hover{border-color:#f97316;transform:translateY(-2px)}
.style-card.selected{border-color:#f97316;box-shadow:0 0 12px rgba(249,115,22,.25)}
.style-video-wrap{position:relative;width:100%;aspect-ratio:16/9;background:#0a0a0a;overflow:hidden}
.style-video-wrap video{width:100%;height:100%;object-fit:cover}
.style-video-wrap .no-sample{display:flex;align-items:center;justify-content:center;width:100%;height:100%;color:#444;font-size:.8rem}
.style-video-wrap .expand-btn{position:absolute;top:6px;right:6px;width:28px;height:28px;border-radius:6px;background:rgba(0,0,0,.6);border:1px solid rgba(255,255,255,.2);color:#fff;display:flex;align-items:center;justify-content:center;cursor:pointer;font-size:.8rem;opacity:0;transition:opacity .2s;z-index:2}
.style-video-wrap:hover .expand-btn{opacity:1}
.style-video-wrap .expand-btn:hover{background:rgba(249,115,22,.8)}
.video-modal-overlay{position:fixed;inset:0;background:rgba(0,0,0,.85);z-index:1000;display:flex;align-items:center;justify-content:center;opacity:0;pointer-events:none;transition:opacity .2s}
.video-modal-overlay.active{opacity:1;pointer-events:auto}
.video-modal{position:relative;width:90%;max-width:900px;border-radius:12px;overflow:hidden;background:#000;box-shadow:0 20px 60px rgba(0,0,0,.8)}
.video-modal video{width:100%;display:block}
.video-modal-close{position:absolute;top:10px;right:10px;width:32px;height:32px;border-radius:50%;background:rgba(0,0,0,.6);border:1px solid rgba(255,255,255,.3);color:#fff;display:flex;align-items:center;justify-content:center;cursor:pointer;font-size:1.1rem;z-index:2}
.video-modal-close:hover{background:rgba(249,115,22,.8)}
.style-info{padding:10px 12px}
.style-info .style-name{font-size:.9rem;font-weight:600;color:#e0e0e0}
.style-info .style-desc{font-size:.72rem;color:#888;margin-top:3px;line-height:1.3}
.style-badge{display:inline-block;font-size:.6rem;background:#f97316;color:#fff;padding:2px 6px;border-radius:4px;margin-top:4px;text-transform:uppercase;letter-spacing:.5px}
.style-upload-hint{font-size:.7rem;color:#555;text-align:center;margin-top:8px}

/* Storyboard section */
.sb-url-row{display:flex;gap:10px;margin-bottom:12px}
.sb-url-row input{flex:1}
.sb-scenes-row{display:flex;gap:12px;align-items:end;margin-bottom:12px}
.sb-scenes-row .form-group{flex:1}
.sb-gallery{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px;margin:16px 0}
.sb-img-card{background:#1a1a1a;border:1px solid #333;border-radius:8px;overflow:hidden;position:relative}
.sb-img-card img{width:100%;aspect-ratio:16/9;object-fit:cover;display:block}
.sb-img-card .sb-img-label{padding:6px 10px;font-size:.72rem;color:#888;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sb-img-card .sb-img-type{position:absolute;top:6px;right:6px;font-size:.6rem;padding:2px 6px;border-radius:4px;text-transform:uppercase;letter-spacing:.5px}
.sb-img-card .sb-img-type.ss{background:rgba(59,130,246,.8);color:#fff}
.sb-img-card .sb-img-type.gen{background:rgba(168,85,247,.8);color:#fff}
.sb-scene-info{margin:16px 0;padding:12px 16px;background:#1a1a1a;border:1px solid #222;border-radius:8px}
.sb-scene-info h4{font-size:.9rem;color:#e0e0e0;margin-bottom:8px}
.sb-scene-row{display:flex;gap:8px;padding:4px 0;font-size:.8rem;border-bottom:1px solid #1e1e1e}
.sb-scene-row:last-child{border:none}
.sb-scene-num{color:#60a5fa;font-weight:600;min-width:20px}
.sb-scene-title{color:#aaa;min-width:120px}
.sb-scene-script{color:#888;flex:1}
.btn-storyboard{background:linear-gradient(135deg,#3b82f6,#6366f1);color:#fff;width:100%;margin-top:8px}
.btn-storyboard:hover{opacity:.9;transform:translateY(-1px)}
.btn-storyboard:disabled{opacity:.4;cursor:not-allowed;transform:none}
.btn-use-sb{background:linear-gradient(135deg,#f97316,#ec4899);color:#fff;width:100%;margin-top:12px}
.btn-use-sb:hover{opacity:.9;transform:translateY(-1px)}

.url-divider{display:flex;align-items:center;gap:12px;margin:14px 0}
.url-divider-line{flex:1;height:1px;background:#333}
.url-divider-text{font-size:.78rem;color:#666;white-space:nowrap}
.url-input-row{display:flex;gap:10px;margin-bottom:12px}
.url-sb-options{background:#161616;border:1px solid #222;border-radius:10px;padding:16px;margin-bottom:16px}
.storyline-label-row{display:flex;align-items:center;gap:8px;margin-bottom:4px}
.storyline-file-btn{width:24px;height:24px;border-radius:6px;background:#252525;border:1px solid #444;color:#aaa;display:flex;align-items:center;justify-content:center;cursor:pointer;font-size:.9rem;font-weight:600;flex-shrink:0;transition:background .2s,border-color .2s}
.storyline-file-btn:hover{background:#333;border-color:#666;color:#fff}
.storyline-file-name{font-size:.75rem;color:#60a5fa;margin-top:4px}
.form-hint{font-size:.72rem;color:#888;margin-top:4px}

/* Bookend gallery */
.bookend-section{margin-top:12px;padding:14px;background:#1a1a1a;border:1px solid #222;border-radius:10px}
.bookend-section h4{font-size:.9rem;color:#f97316;margin-bottom:10px}
.bookend-gallery{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:12px}
.bookend-card{background:#0a0a0a;border:2px solid #333;border-radius:10px;overflow:hidden;cursor:pointer;transition:all .15s}
.bookend-card:hover{border-color:#f97316;transform:translateY(-2px)}
.bookend-card.selected{border-color:#34d399;box-shadow:0 0 12px rgba(52,211,153,.3)}
.bookend-card.disabled{opacity:.4;cursor:not-allowed;pointer-events:none}
.bookend-card img{width:100%;aspect-ratio:16/9;object-fit:cover;display:block}
.bookend-card-info{padding:8px 10px}
.bookend-card-title{font-size:.85rem;font-weight:600;color:#e0e0e0}
.bookend-card-sub{font-size:.72rem;color:#888;margin-top:2px}
.bookend-card-badge{position:absolute;top:6px;left:6px;font-size:.6rem;background:rgba(52,211,153,.9);color:#fff;padding:2px 8px;border-radius:4px;text-transform:uppercase;letter-spacing:.5px;display:none}
.bookend-card.selected .bookend-card-badge{display:block}
.bookend-card{position:relative}
.btn-bookends{background:linear-gradient(135deg,#8b5cf6,#a78bfa);color:#fff;width:100%;margin-top:8px}
.btn-bookends:hover{opacity:.9;transform:translateY(-1px)}
.btn-bookends:disabled{opacity:.4;cursor:not-allowed;transform:none}
.bookend-progress{margin-top:8px}

.hidden{display:none!important}
</style>
</head>
<body>
<div id="authGate" style="display:flex;align-items:center;justify-content:center;min-height:100vh;flex-direction:column;gap:12px">
  <div style="font-size:1.2rem;color:#888">Loading...</div>
</div>
<div class="container" id="appContainer" style="display:none">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
    <div>
      <h1>Video Generator</h1>
      <p class="subtitle">Upload images, videos, or presentations — get a professional marketing video with AI voiceover and music.</p>
    </div>
    <div style="display:flex;align-items:center;gap:10px">
      <span style="font-size:.8rem;color:#888" id="userName"></span>
      <button class="btn btn-secondary" style="padding:6px 14px;font-size:.8rem;border-radius:6px" id="signOutBtn">Sign Out</button>
    </div>
  </div>

  <!-- STEP 1: Voice Selection -->
  <div class="section" id="voiceSection">
    <div class="section-head">
      <h2>Select Voice</h2>
      <span class="step-badge">Step 1</span>
    </div>
    <select class="form-select" id="voiceSelect" style="margin-bottom:12px">
      <option value="Smritika">Loading voices...</option>
    </select>

    <!-- Clone new voice (collapsible) -->
    <div class="clone-toggle-row" id="cloneToggle">
      <span class="clone-arrow" id="cloneArrow">&#9654;</span>
      <span class="clone-toggle-text">Clone a new voice</span>
    </div>
    <div class="clone-body hidden" id="cloneBody">
      <div class="clone-upload-area" id="cloneDropZone">
        <span class="upload-icon">&#127908;</span>
        <div class="upload-text">Drop audio sample(s) here</div>
        <div class="upload-hint">MP3, WAV, M4A &bull; Multiple files for best quality</div>
        <div class="file-list hidden" id="cloneFileList"></div>
        <input type="file" multiple accept=".mp3,.wav,.m4a,.ogg,.flac,.webm" id="cloneFileInput" style="display:none">
      </div>
      <div class="form-grid" style="margin-top:12px">
        <div class="form-group">
          <span class="form-label">Voice Name *</span>
          <input class="form-input" id="cloneName" placeholder="e.g. My Voice">
        </div>
        <div class="form-group">
          <span class="form-label">Accent</span>
          <input class="form-input" id="cloneAccent" placeholder="e.g. British, Indian">
        </div>
        <div class="form-group">
          <span class="form-label">Gender</span>
          <select class="form-select" id="cloneGender">
            <option value="">Select...</option>
            <option value="male">Male</option>
            <option value="female">Female</option>
          </select>
        </div>
        <div class="form-group">
          <span class="form-label">Age</span>
          <select class="form-select" id="cloneAge">
            <option value="">Select...</option>
            <option value="young">Young</option>
            <option value="middle_aged">Middle Aged</option>
            <option value="old">Old</option>
          </select>
        </div>
        <div class="form-group full">
          <span class="form-label">Description</span>
          <input class="form-input" id="cloneDesc" placeholder="e.g. Professional female narrator">
        </div>
      </div>
      <button class="btn btn-clone" id="cloneBtn" disabled>Clone Voice</button>
      <div class="clone-result hidden" id="cloneResult"></div>
    </div>
  </div>

  <!-- STEP 2: Video Generation -->
  <div class="section" id="videoSection">
    <div class="section-head">
      <h2>Generate Video</h2>
      <span class="step-badge">Step 2</span>
    </div>

    <div class="upload-area" id="dropZone">
      <span class="upload-icon">&#127916;</span>
      <div class="upload-text">Drag & drop files here, or click to browse</div>
      <div class="upload-hint">Images (PNG, JPG, WebP) &bull; Videos (MP4, MOV) &bull; PowerPoint (PPTX) &bull; PDF</div>
      <div class="file-list hidden" id="fileList"></div>
      <input type="file" multiple accept=".png,.jpg,.jpeg,.webp,.gif,.bmp,.mp4,.mov,.avi,.mkv,.webm,.m4v,.pptx,.ppt,.pdf,.doc,.docx" id="fileInput" style="display:none">
    </div>
    <div class="url-divider">
      <span class="url-divider-line"></span>
      <span class="url-divider-text">or paste a website URL</span>
      <span class="url-divider-line"></span>
    </div>
    <div class="url-input-row">
      <input class="form-input" id="urlInput" placeholder="https://example.com" style="flex:1">
      <button class="btn btn-storyboard" id="urlSbBtn" style="width:auto;margin:0;padding:8px 20px;white-space:nowrap">Generate Storyboard</button>
    </div>
    <div class="url-sb-options" id="urlSbOptions">
      <div class="form-grid" style="margin-bottom:0">
        <div class="form-group">
          <span class="form-label">Scenes</span>
          <input class="form-input" id="urlSbScenes" type="number" value="6" min="2" max="12">
          <span class="form-hint" id="sceneDurationHint">6 scenes ~ 30s video</span>
        </div>
        <div class="form-group">
          <span class="form-label">Aspect Ratio</span>
          <select class="form-select" id="urlSbAspect">
            <option value="16:9" selected>16:9 (Landscape)</option>
            <option value="9:16">9:16 (Portrait)</option>
            <option value="4:3">4:3</option>
            <option value="1:1">1:1 (Square)</option>
          </select>
        </div>
        <div class="form-group">
          <span class="form-label">Content</span>
          <select class="form-select" id="urlSbContent">
            <option value="both" selected>Screenshots + AI Images</option>
            <option value="screenshots">Screenshots Only</option>
            <option value="imagen">AI Images Only</option>
          </select>
        </div>
      </div>
    </div>
    <div id="urlSbProgress" class="hidden" style="margin-bottom:16px">
      <div class="progress-bar"><div class="progress-bar-inner"></div></div>
      <div class="progress-text" id="urlSbProgressText">Generating storyboard...</div>
      <div class="log-panel" style="margin-top:8px">
        <div class="log-content" id="urlSbLogContent"></div>
      </div>
    </div>
    <div id="urlSbResults" class="hidden" style="margin-bottom:16px">
      <div class="sb-scene-info" id="urlSbSceneInfo"></div>
      <div class="sb-gallery" id="urlSbGallery"></div>
      <button class="btn btn-use-sb" id="urlSbUseBtn">Create Video from Storyboard</button>
    </div>

    <div id="formSection">
      <div class="form-grid">
        <div class="form-group">
          <span class="form-label">Product Name</span>
          <input class="form-input" id="product" placeholder="e.g. My SaaS App">
        </div>
        <div class="form-group full">
          <span class="form-label">Style — pick one</span>
          <div class="style-picker" id="stylePicker">
            <div class="style-card selected" data-style="marketing">
              <div class="style-video-wrap" id="sv-marketing"><div class="no-sample">Hover to preview</div></div>
              <div class="style-info">
                <div class="style-name">Marketing</div>
                <div class="style-desc">Persuasive pitch — hooks, pain points, proof, strong CTA</div>
              </div>
            </div>
            <div class="style-card" data-style="feature-explainer">
              <div class="style-video-wrap" id="sv-feature-explainer"><div class="no-sample">Hover to preview</div></div>
              <div class="style-info">
                <div class="style-name">Feature Explainer</div>
                <div class="style-desc">Product walkthrough — what each feature does and why it matters</div>
              </div>
            </div>
            <div class="style-card" data-style="tutorial-explainer">
              <div class="style-video-wrap" id="sv-tutorial-explainer"><div class="no-sample">Hover to preview</div></div>
              <div class="style-info">
                <div class="style-name">Tutorial Explainer</div>
                <div class="style-desc">Step-by-step guide — clear instructions, practical tips</div>
              </div>
            </div>
          </div>
          <input type="hidden" id="style" value="marketing">
        </div>

        <div class="form-group">
          <span class="form-label">Tone</span>
          <input class="form-input" id="tone" value="professional and engaging">
        </div>
        <div class="form-group">
          <span class="form-label">Resolution</span>
          <select class="form-select" id="resolution">
            <option value="720p">720p</option>
            <option value="1080p" selected>1080p</option>
            <option value="4k">4K</option>
          </select>
        </div>
        <input type="hidden" id="scriptDuration" value="60">
        <div class="form-group full">
          <div class="storyline-label-row">
            <span class="form-label">Storyline</span>
            <label class="storyline-file-btn" title="Upload a text file">
              <span>+</span>
              <input type="file" accept=".txt,.md,.text" id="storylineFile" style="display:none">
            </label>
          </div>
          <textarea class="form-textarea" id="storyline" placeholder="e.g. From chaos to clarity — how one dashboard changed everything"></textarea>
          <div class="storyline-file-name hidden" id="storylineFileName"></div>
        </div>
        <div class="form-group full">
          <div class="toggle-row">
            <label class="toggle"><input type="checkbox" id="generateMusic"><span class="toggle-slider"></span></label>
            <span class="toggle-label">Generate AI Background Music</span>
          </div>
        </div>
        <div class="form-group full hidden" id="musicPromptGroup">
          <span class="form-label">Music Prompt</span>
          <input class="form-input" id="musicPrompt" placeholder="e.g. upbeat corporate (auto-derived from tone if empty)">
        </div>
        <div class="form-group full">
          <div class="toggle-row">
            <label class="toggle"><input type="checkbox" id="enableBookends"><span class="toggle-slider"></span></label>
            <span class="toggle-label">Generate Intro &amp; Outro Frames</span>
            <span class="form-hint" style="margin-left:8px">Branded opening + CTA closing cards</span>
          </div>
        </div>
        <div class="form-group full hidden" id="bookendPanel">
          <div class="form-grid" style="margin-bottom:8px">
            <div class="form-group">
              <div class="toggle-row">
                <label class="toggle"><input type="checkbox" id="generateIntro" checked><span class="toggle-slider"></span></label>
                <span class="toggle-label">Intro Frame</span>
              </div>
              <input class="form-input" id="introPrompt" placeholder="e.g. dark gradient with glowing logo, futuristic vibe" style="margin-top:6px">
              <span class="form-hint">Describe the intro look you want (optional)</span>
              <div class="avatar-upload-area" id="introRefZone" style="margin-top:6px;padding:8px">
                <span style="font-size:.75rem;color:#666">Drop reference image (optional)</span>
                <div class="hidden" id="introRefName" style="font-size:.72rem;color:#60a5fa;margin-top:3px"></div>
                <input type="file" accept=".png,.jpg,.jpeg,.webp" id="introRefInput" style="display:none">
              </div>
            </div>
            <div class="form-group">
              <div class="toggle-row">
                <label class="toggle"><input type="checkbox" id="generateOutro" checked><span class="toggle-slider"></span></label>
                <span class="toggle-label">Outro Frame</span>
              </div>
              <input class="form-input" id="outroPrompt" placeholder="e.g. warm sunset tones, Book a Demo CTA, clean minimal" style="margin-top:6px">
              <span class="form-hint">Describe the outro look you want (optional)</span>
              <div class="avatar-upload-area" id="outroRefZone" style="margin-top:6px;padding:8px">
                <span style="font-size:.75rem;color:#666">Drop reference image (optional)</span>
                <div class="hidden" id="outroRefName" style="font-size:.72rem;color:#60a5fa;margin-top:3px"></div>
                <input type="file" accept=".png,.jpg,.jpeg,.webp" id="outroRefInput" style="display:none">
              </div>
            </div>
          </div>
          <button class="btn btn-bookends" id="bookendGenBtn">Generate Frame Options</button>
          <div class="bookend-progress hidden" id="bookendProgress">
            <div class="progress-bar"><div class="progress-bar-inner"></div></div>
            <div class="progress-text" id="bookendProgressText">Generating frame options...</div>
          </div>
          <div class="hidden" id="bookendResults">
            <div class="bookend-section hidden" id="introSection">
              <h4>Intro Frame — click to select</h4>
              <div class="bookend-gallery" id="introGallery"></div>
            </div>
            <div class="bookend-section hidden" id="outroSection">
              <h4>Outro Frame — click to select</h4>
              <div class="bookend-gallery" id="outroGallery"></div>
            </div>
          </div>
        </div>
      </div>

      <button class="btn btn-primary" id="generateBtn" disabled>Generate Video</button>
    </div>
  </div>

  <div class="progress-wrap" id="progress">
    <div class="progress-bar"><div class="progress-bar-inner"></div></div>
    <div class="progress-text" id="progressText">Generating video...</div>
    <div class="progress-sub" id="progressSub"></div>
    <div class="log-panel hidden" id="logPanel">
      <div class="log-content" id="logContent"></div>
    </div>
  </div>

  <div class="error-msg" id="errorMsg"></div>

  <div class="results" id="results">
    <div class="results-header">
      <h2 id="resultsTitle">Your Video</h2>
      <button class="btn btn-secondary" id="newBtn">New Video</button>
    </div>
    <div class="video-wrap" id="videoWrap"></div>
    <div class="dl-row" id="dlRow"></div>
    <div class="cost-panel hidden" id="costEstimate"></div>

    <div class="avatar-panel" id="avatarPanel">
      <h3>Avatar Overlay</h3>
      <div class="avatar-guide">
        <div class="avatar-guide-steps">
          <div class="avatar-step">
            <span class="avatar-step-num">1</span>
            <span class="avatar-step-text">Download the <strong>audio</strong> above</span>
          </div>
          <div class="avatar-step-arrow">&rarr;</div>
          <div class="avatar-step">
            <span class="avatar-step-num">2</span>
            <span class="avatar-step-text">Create avatar video using the audio (e.g. <a href="https://www.heygen.com" target="_blank" style="color:#60a5fa">HeyGen</a>, <a href="https://www.synthesia.io" target="_blank" style="color:#60a5fa">Synthesia</a>, <a href="https://www.d-id.com" target="_blank" style="color:#60a5fa">D-ID</a>)</span>
          </div>
          <div class="avatar-step-arrow">&rarr;</div>
          <div class="avatar-step">
            <span class="avatar-step-num">3</span>
            <span class="avatar-step-text">Upload the avatar video below &amp; apply</span>
          </div>
        </div>
        <p class="avatar-guide-note">No avatar needed? Just download the video directly above.</p>
      </div>
      <div class="avatar-grid">
        <div class="form-group">
          <span class="form-label">Avatar</span>
          <div class="avatar-upload-area" id="avatarDropZone">
            <span style="font-size:.8rem;color:#666">Drop image/video or click</span>
            <div class="hidden" id="avatarFileName" style="font-size:.75rem;color:#60a5fa;margin-top:4px"></div>
            <input type="file" accept=".png,.jpg,.jpeg,.webp,.gif,.mp4,.mov,.webm" id="avatarFileInput" style="display:none">
          </div>
        </div>
        <div class="form-group">
          <span class="form-label">Position</span>
          <select class="form-select" id="avatarPosition">
            <option value="bottom-right" selected>Bottom Right</option>
            <option value="bottom-left">Bottom Left</option>
            <option value="top-right">Top Right</option>
            <option value="top-left">Top Left</option>
          </select>
        </div>
        <div class="form-group">
          <span class="form-label">Size</span>
          <input type="range" id="avatarScale" min="0.05" max="0.4" step="0.01" value="0.15">
          <div class="slider-val" id="avatarScaleVal">15%</div>
        </div>
        <div class="form-group">
          <span class="form-label">Opacity</span>
          <input type="range" id="avatarOpacity" min="0.1" max="1.0" step="0.05" value="1.0">
          <div class="slider-val" id="avatarOpacityVal">1.0</div>
        </div>
      </div>
      <button class="btn btn-avatar" id="avatarBtn" disabled>Apply Avatar</button>
    </div>

    <div class="post-panel" id="postPanel">
      <h3>Post-Processing</h3>
      <div class="post-grid">
        <div class="slider-group">
          <label>Video Speed</label>
          <input type="range" id="postSpeed" min="0.5" max="2.0" step="0.05" value="1.0">
          <div class="slider-val" id="postSpeedVal">1.0x</div>
        </div>
        <div class="slider-group">
          <label>Voice Volume</label>
          <input type="range" id="postVoiceVol" min="0" max="15" step="0.5" value="5.0">
          <div class="slider-val" id="postVoiceVolVal">5.0</div>
        </div>
        <div class="slider-group">
          <label>Music Volume</label>
          <input type="range" id="postMusicVol" min="0" max="0.2" step="0.005" value="0.03">
          <div class="slider-val" id="postMusicVolVal">0.03</div>
        </div>
      </div>
      <button class="btn btn-post" id="postBtn">Apply Post-Processing</button>
    </div>
  </div>
</div>

<script>
// ── Clerk Auth Gate ──
(async()=>{
  const clerk=new window.Clerk('__CLERK_PK__');
  await clerk.load();
  if(!clerk.user){window.location.href='/';return}
  document.getElementById('authGate').style.display='none';
  document.getElementById('appContainer').style.display='block';
  const nameEl=document.getElementById('userName');
  if(nameEl&&clerk.user.firstName)nameEl.textContent=clerk.user.firstName;
  document.getElementById('signOutBtn').onclick=()=>clerk.signOut().then(()=>window.location.href='/');
})();

const dropZone=document.getElementById('dropZone'),fileInput=document.getElementById('fileInput'),fileList=document.getElementById('fileList'),generateBtn=document.getElementById('generateBtn'),formSection=document.getElementById('formSection'),progress=document.getElementById('progress'),progressText=document.getElementById('progressText'),progressSub=document.getElementById('progressSub'),errorMsg=document.getElementById('errorMsg'),results=document.getElementById('results'),resultsTitle=document.getElementById('resultsTitle'),musicToggle=document.getElementById('generateMusic'),musicPromptGroup=document.getElementById('musicPromptGroup'),voiceSection=document.getElementById('voiceSection'),videoSection=document.getElementById('videoSection');

let selectedFiles=[],currentVideoB64=null,currentAudioB64=null,currentMusicB64=null,currentJobId=null,selectedVoice='Smritika';

// ── Voice Loading ──
const voiceSelect=document.getElementById('voiceSelect');
voiceSelect.addEventListener('change',()=>{selectedVoice=voiceSelect.value});

async function loadVoices(){
  try{
    const res=await fetch('/voices');
    const data=await res.json();
    if(data.voices&&data.voices.length){
      voiceSelect.innerHTML='';
      // Cloned voices first, then premade
      const cloned=data.voices.filter(v=>v.category==='cloned');
      const premade=data.voices.filter(v=>v.category!=='cloned');
      if(cloned.length){
        const g=document.createElement('optgroup');g.label='Cloned Voices';
        cloned.forEach(v=>{const o=document.createElement('option');o.value=v.name;o.textContent=v.name;g.appendChild(o)});
        voiceSelect.appendChild(g);
      }
      if(premade.length){
        const g=document.createElement('optgroup');g.label='Premade Voices';
        premade.forEach(v=>{const o=document.createElement('option');o.value=v.name;o.textContent=v.name;g.appendChild(o)});
        voiceSelect.appendChild(g);
      }
      // Select default
      const def=data.voices.find(v=>v.name===selectedVoice);
      if(def)voiceSelect.value=def.name;
      else{voiceSelect.selectedIndex=0;selectedVoice=voiceSelect.value}
    }else{
      voiceSelect.innerHTML='<option value="Smritika">Smritika (default)</option>';
    }
  }catch(e){
    voiceSelect.innerHTML='<option value="Smritika">Smritika (default)</option>';
  }
}
loadVoices();

// ── Voice Cloning ──
const cloneToggle=document.getElementById('cloneToggle'),cloneBody=document.getElementById('cloneBody'),cloneArrow=document.getElementById('cloneArrow'),cloneDropZone=document.getElementById('cloneDropZone'),cloneFileInput=document.getElementById('cloneFileInput'),cloneFileList=document.getElementById('cloneFileList'),cloneBtn=document.getElementById('cloneBtn'),cloneResult=document.getElementById('cloneResult');
let cloneFiles=[];

cloneToggle.addEventListener('click',()=>{cloneBody.classList.toggle('hidden');cloneArrow.classList.toggle('open')});
cloneDropZone.addEventListener('click',()=>cloneFileInput.click());
cloneDropZone.addEventListener('dragover',e=>{e.preventDefault();cloneDropZone.style.borderColor='#34d399'});
cloneDropZone.addEventListener('dragleave',()=>{cloneDropZone.style.borderColor='#333'});
cloneDropZone.addEventListener('drop',e=>{e.preventDefault();cloneDropZone.style.borderColor='#333';setCloneFiles(e.dataTransfer.files)});
cloneFileInput.addEventListener('change',()=>setCloneFiles(cloneFileInput.files));

function setCloneFiles(fl){
  cloneFiles=Array.from(fl);
  if(!cloneFiles.length)return;
  cloneFileList.innerHTML=cloneFiles.map(f=>f.name).join(', ');
  cloneFileList.classList.remove('hidden');
  cloneDropZone.classList.add('has-file');
  updateCloneBtn();
}
function updateCloneBtn(){cloneBtn.disabled=!(cloneFiles.length&&document.getElementById('cloneName').value.trim())}
document.getElementById('cloneName').addEventListener('input',updateCloneBtn);

cloneBtn.addEventListener('click',async()=>{
  if(!cloneFiles.length||!document.getElementById('cloneName').value.trim())return;
  cloneBtn.disabled=true;
  cloneBtn.textContent='Cloning voice...';
  cloneResult.classList.add('hidden');
  progress.classList.add('active');
  progressText.textContent='Cloning voice...';
  progressSub.textContent='Uploading audio samples to ElevenLabs';

  const fd=new FormData();
  for(const f of cloneFiles)fd.append('audio_files',f);
  fd.append('name',document.getElementById('cloneName').value.trim());
  fd.append('accent',document.getElementById('cloneAccent').value);
  fd.append('gender',document.getElementById('cloneGender').value);
  fd.append('age',document.getElementById('cloneAge').value);
  fd.append('description',document.getElementById('cloneDesc').value);

  try{
    const res=await fetch('/voice-clone',{method:'POST',body:fd});
    if(!res.ok){const t=await res.text();throw new Error(t||'HTTP '+res.status)}
    const data=await res.json();
    cloneResult.classList.remove('hidden','success','error');
    if(data.success){
      cloneResult.classList.add('success');
      cloneResult.textContent='Voice "'+data.voice_name+'" cloned successfully!';
      selectedVoice=data.voice_name;
      // Add to dropdown and select
      const o=document.createElement('option');o.value=data.voice_name;o.textContent=data.voice_name;
      voiceSelect.prepend(o);
      voiceSelect.value=data.voice_name;
    }else{
      cloneResult.classList.add('error');
      cloneResult.textContent='Clone failed: '+data.error;
    }
  }catch(e){
    cloneResult.classList.remove('hidden','success','error');
    cloneResult.classList.add('error');
    cloneResult.textContent='Clone failed: '+e.message;
  }finally{
    progress.classList.remove('active');
    cloneBtn.disabled=false;
    cloneBtn.textContent='Clone Voice';
  }
});

// ── Style Picker ──
const styleInput=document.getElementById('style');
function updateSbOptionsVisibility(){
  const opts=document.getElementById('urlSbOptions');
  const btn=document.getElementById('urlSbBtn');
  if(!opts)return;
  const isMarketing=styleInput.value==='marketing';
  if(isMarketing){opts.classList.remove('hidden');btn.classList.remove('hidden')}
  else{opts.classList.add('hidden');btn.classList.add('hidden')}
}
document.querySelectorAll('.style-card').forEach(card=>{
  card.addEventListener('click',()=>{
    document.querySelectorAll('.style-card').forEach(c=>c.classList.remove('selected'));
    card.classList.add('selected');
    styleInput.value=card.dataset.style;
    updateSbOptionsVisibility();
    // Pause other videos, play selected
    document.querySelectorAll('.style-video-wrap video').forEach(v=>{v.pause();v.currentTime=0});
    const vid=card.querySelector('video');
    if(vid)vid.play();
  });
});

// Load sample videos — check existence first with HEAD, then lazy-load
['marketing','feature-explainer','tutorial-explainer'].forEach(style=>{
  const wrap=document.getElementById('sv-'+style);
  const url='/sample/'+style;
  fetch(url,{method:'HEAD'}).then(r=>{
    if(!r.ok)throw new Error('none');
    wrap.innerHTML='';
    const v=document.createElement('video');
    v.src=url;v.muted=true;v.loop=true;v.playsInline=true;
    v.preload='none';
    v.addEventListener('mouseenter',()=>{v.preload='auto';v.play()});
    v.addEventListener('mouseleave',()=>{v.pause();v.currentTime=0});
    v.addEventListener('loadeddata',()=>{v.style.opacity='1'});
    v.style.opacity='0';v.style.transition='opacity .3s';
    wrap.appendChild(v);
    // Expand button
    const btn=document.createElement('div');
    btn.className='expand-btn';
    btn.innerHTML='&#x26F6;';
    btn.addEventListener('click',e=>{e.stopPropagation();openVideoModal(url)});
    wrap.appendChild(btn);
    if(wrap.closest('.style-card').classList.contains('selected')){v.preload='auto';v.play()}
  }).catch(()=>{
    wrap.innerHTML='<div class="no-sample">No sample yet</div>';
  });
});

// ── File Upload ──
musicToggle.addEventListener('change',()=>{musicPromptGroup.classList.toggle('hidden',!musicToggle.checked)});

const urlInput=document.getElementById('urlInput');
const urlSbBtn=document.getElementById('urlSbBtn');
const urlSbProgress=document.getElementById('urlSbProgress');
const urlSbProgressText=document.getElementById('urlSbProgressText');
const urlSbLogContent=document.getElementById('urlSbLogContent');
const urlSbResults=document.getElementById('urlSbResults');
const urlSbGallery=document.getElementById('urlSbGallery');
const urlSbSceneInfo=document.getElementById('urlSbSceneInfo');
const urlSbUseBtn=document.getElementById('urlSbUseBtn');
let urlSbJobId=null;

// ── Scene duration hint ──
const sceneDurationHint=document.getElementById('sceneDurationHint');
document.getElementById('urlSbScenes').addEventListener('input',function(){
  const n=parseInt(this.value)||6;
  const secs=n*5;
  sceneDurationHint.textContent=n+' scenes ~ '+secs+'s video';
});

// ── Storyline file upload ──
document.getElementById('storylineFile').addEventListener('change',function(){
  const f=this.files[0];
  if(!f)return;
  const nameEl=document.getElementById('storylineFileName');
  const reader=new FileReader();
  reader.onload=e=>{
    document.getElementById('storyline').value=e.target.result;
    nameEl.textContent=f.name;
    nameEl.classList.remove('hidden');
  };
  reader.readAsText(f);
});

dropZone.addEventListener('click',()=>fileInput.click());
dropZone.addEventListener('dragover',e=>{e.preventDefault();dropZone.classList.add('dragover')});
dropZone.addEventListener('dragleave',()=>dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop',e=>{e.preventDefault();dropZone.classList.remove('dragover');setFiles(e.dataTransfer.files)});
fileInput.addEventListener('change',()=>setFiles(fileInput.files));

urlInput.addEventListener('input',()=>{updateSbOptionsVisibility()});
// Show options on load if marketing is default
updateSbOptionsVisibility();

urlSbBtn.addEventListener('click',async()=>{
  const url=urlInput.value.trim();
  if(!url)return;
  urlSbBtn.disabled=true;
  urlSbBtn.textContent='Generating...';
  urlSbResults.classList.add('hidden');
  urlSbProgress.classList.remove('hidden');
  urlSbLogContent.innerHTML='';
  urlSbProgressText.textContent='Submitting storyboard job...';

  const contentMode=document.getElementById('urlSbContent').value;
  const fd=new FormData();
  fd.append('url',url);
  fd.append('storyline',document.getElementById('storyline').value);
  fd.append('product',document.getElementById('product').value);
  fd.append('scenes',document.getElementById('urlSbScenes').value||'6');
  fd.append('style',styleInput.value);
  fd.append('aspect_ratio',document.getElementById('urlSbAspect').value);
  fd.append('skip_screenshots',contentMode==='imagen'?'true':'false');
  fd.append('skip_imagen',contentMode==='screenshots'?'true':'false');

  try{
    const res=await fetch('/storyboard',{method:'POST',body:fd});
    if(!res.ok){const t=await res.text();throw new Error(t||'HTTP '+res.status)}
    const data=await res.json();
    if(data.job_id){
      urlSbJobId=data.job_id;
      urlSbProgressText.textContent='Generating storyboard...';
      startUrlSbPolling(data.job_id);
    }
  }catch(e){
    urlSbProgressText.textContent='Failed: '+e.message;
    urlSbBtn.disabled=false;
    urlSbBtn.textContent='Generate Storyboard';
  }
});

function startUrlSbPolling(jobId){
  let prevLen=0;
  const timer=setInterval(async()=>{
    try{
      const res=await fetch('/storyboard-status/'+jobId);
      if(!res.ok)return;
      const data=await res.json();
      if(data.logs&&data.logs.length>prevLen){
        const lines=data.logs.trim().split('\\n');
        urlSbLogContent.innerHTML=lines.map(l=>'<span class="log-line">'+escHtml(l)+'</span>').join('');
        urlSbLogContent.parentElement.scrollTop=urlSbLogContent.parentElement.scrollHeight;
        prevLen=data.logs.length;
        urlSbProgressText.textContent=lines[lines.length-1]||'Working...';
      }
      if(data.state==='done'){
        clearInterval(timer);
        urlSbProgress.classList.add('hidden');
        urlSbBtn.disabled=false;
        urlSbBtn.textContent='Generate Storyboard';
        if(data.result)renderUrlStoryboard(data.result,jobId);
      }else if(data.state==='error'){
        clearInterval(timer);
        urlSbProgressText.textContent='Error: '+(data.error||'Unknown');
        urlSbBtn.disabled=false;
        urlSbBtn.textContent='Generate Storyboard';
      }
    }catch(e){}
  },3000);
}

function renderUrlStoryboard(result,jobId){
  urlSbResults.classList.remove('hidden');
  // Scene info
  if(result.scenes&&result.scenes.length){
    let html='<h4>Scene Plan ('+result.scenes.length+' scenes)</h4>';
    result.scenes.forEach(s=>{
      html+='<div class="sb-scene-row"><span class="sb-scene-num">'+s.scene_number+'</span><span class="sb-scene-title">'+escHtml(s.title)+'</span><span class="sb-scene-script">'+escHtml(s.voiceover_script)+'</span></div>';
    });
    urlSbSceneInfo.innerHTML=html;
  }
  urlSbGallery.innerHTML='';
  // Screenshots section
  const ssFiles=(result.images||[]).filter(f=>f.startsWith('ss_'));
  if(ssFiles.length){
    const ssHeader=document.createElement('div');
    ssHeader.style.cssText='grid-column:1/-1;font-size:.85rem;color:#60a5fa;font-weight:600;margin-top:4px';
    ssHeader.textContent='Screenshots ('+ssFiles.length+')';
    urlSbGallery.appendChild(ssHeader);
    ssFiles.forEach(fname=>{
      const card=document.createElement('div');
      card.className='sb-img-card';
      card.innerHTML='<img src="/storyboard-image/'+jobId+'/'+fname+'" loading="lazy"><span class="sb-img-type ss">Screenshot</span><div class="sb-img-label">'+escHtml(fname)+'</div>';
      urlSbGallery.appendChild(card);
    });
  }
  // Sequence section (screenshots + AI images selected per scene)
  const seqFiles=result.sequence_files||[];
  if(seqFiles.length){
    const seqHeader=document.createElement('div');
    seqHeader.style.cssText='grid-column:1/-1;font-size:.85rem;color:#a78bfa;font-weight:600;margin-top:12px';
    seqHeader.textContent='Video Sequence ('+seqFiles.length+' files)';
    urlSbGallery.appendChild(seqHeader);
    seqFiles.forEach(fname=>{
      const card=document.createElement('div');
      card.className='sb-img-card';
      const isSs=fname.includes('screenshot');
      const typeLabel=isSs?'Screenshot':'AI Generated';
      const typeCls=isSs?'ss':'gen';
      card.innerHTML='<img src="/storyboard-image/'+jobId+'/'+fname+'" loading="lazy"><span class="sb-img-type '+typeCls+'">'+typeLabel+'</span><div class="sb-img-label">'+escHtml(fname)+'</div>';
      urlSbGallery.appendChild(card);
    });
  }
  if(!ssFiles.length&&!seqFiles.length){
    urlSbGallery.innerHTML='<div style="color:#666;font-size:.85rem">No images generated</div>';
  }
}

urlSbUseBtn.addEventListener('click',async()=>{
  if(!urlSbJobId)return;
  urlSbUseBtn.disabled=true;
  urlSbUseBtn.textContent='Creating video...';
  voiceSection.classList.add('hidden');
  videoSection.classList.add('hidden');
  results.classList.remove('active');
  progress.classList.add('active');
  logPanel.classList.remove('hidden');
  logContent.innerHTML='';
  progressText.textContent='Starting video from storyboard...';
  progressSub.textContent='';
  hideError();

  const fd=new FormData();
  fd.append('storyboard_job_id',urlSbJobId);
  fd.append('voice',selectedVoice);
  fd.append('style',styleInput.value);
  fd.append('tone',document.getElementById('tone').value);
  fd.append('resolution',document.getElementById('resolution').value);
  fd.append('script_duration',document.getElementById('scriptDuration').value);
  fd.append('storyline',document.getElementById('storyline').value);
  fd.append('product',document.getElementById('product').value);
  fd.append('generate_music',musicToggle.checked?'true':'false');
  fd.append('music_prompt',document.getElementById('musicPrompt').value);
  if(enableBookends.checked&&bookendJobId){
    fd.append('bookend_job_id',bookendJobId);
    if(selectedIntro){fd.append('intro_option',selectedIntro.option_number.toString());fd.append('intro_veo_prompt',selectedIntro.veo_motion_prompt||'')}
    if(selectedOutro){fd.append('outro_option',selectedOutro.option_number.toString());fd.append('outro_veo_prompt',selectedOutro.veo_motion_prompt||'')}
  }
  fd.append('generate_intro',enableBookends.checked&&selectedIntro?'true':'false');
  fd.append('generate_outro',enableBookends.checked&&selectedOutro?'true':'false');

  try{
    const res=await fetch('/create-from-storyboard',{method:'POST',body:fd});
    if(!res.ok){const t=await res.text();throw new Error(t||'HTTP '+res.status)}
    const data=await res.json();
    if(data.job_id){
      progressText.textContent='Generating video...';
      progressSub.textContent='Polling for pipeline logs';
      startPolling(data.job_id);
    }
  }catch(e){
    showError('Video creation failed: '+e.message);
    resetUI();
    progress.classList.remove('active');
    urlSbUseBtn.disabled=false;
    urlSbUseBtn.textContent='Create Video from Storyboard';
  }
});

function setFiles(fl){
  selectedFiles=Array.from(fl);
  if(!selectedFiles.length)return;
  fileList.innerHTML=selectedFiles.map(f=>f.name).join(', ');
  fileList.classList.remove('hidden');
  dropZone.classList.add('has-file');
  generateBtn.disabled=false;
  hideError();
}

// ── Generate Video ──
const logPanel=document.getElementById('logPanel'),logContent=document.getElementById('logContent');
let pollTimer=null;

generateBtn.addEventListener('click',async()=>{
  if(!selectedFiles.length)return;
  generateBtn.disabled=true;
  voiceSection.classList.add('hidden');
  videoSection.classList.add('hidden');
  results.classList.remove('active');
  progress.classList.add('active');
  logPanel.classList.remove('hidden');
  logContent.innerHTML='';
  progressText.textContent='Submitting job...';
  progressSub.textContent='';
  hideError();

  const fd=new FormData();
  for(const f of selectedFiles)fd.append('files',f);
  fd.append('product',document.getElementById('product').value);
  fd.append('voice',selectedVoice);
  fd.append('style',document.getElementById('style').value);
  fd.append('tone',document.getElementById('tone').value);
  fd.append('resolution',document.getElementById('resolution').value);
  fd.append('script_duration',document.getElementById('scriptDuration').value);
  fd.append('storyline',document.getElementById('storyline').value);
  fd.append('generate_music',musicToggle.checked?'true':'false');
  fd.append('music_prompt',document.getElementById('musicPrompt').value);
  // Bookend selection
  if(enableBookends.checked&&bookendJobId){
    fd.append('bookend_job_id',bookendJobId);
    if(selectedIntro){fd.append('intro_option',selectedIntro.option_number.toString());fd.append('intro_veo_prompt',selectedIntro.veo_motion_prompt||'')}
    if(selectedOutro){fd.append('outro_option',selectedOutro.option_number.toString());fd.append('outro_veo_prompt',selectedOutro.veo_motion_prompt||'')}
  }
  fd.append('generate_intro',enableBookends.checked&&selectedIntro?'true':'false');
  fd.append('generate_outro',enableBookends.checked&&selectedOutro?'true':'false');

  try{
    const res=await fetch('/create',{method:'POST',body:fd});
    if(!res.ok){const t=await res.text();throw new Error(t||'HTTP '+res.status)}
    const data=await res.json();
    if(data.job_id){
      progressText.textContent='Generating video...';
      progressSub.textContent='Polling for pipeline logs';
      startPolling(data.job_id);
    }else if(data.video){
      currentVideoB64=data.video;
      currentAudioB64=data.audio||null;
      currentMusicB64=data.music||null;
      renderResults(data);
      progress.classList.remove('active');
    }
  }catch(e){
    showError('Generation failed: '+e.message);
    resetUI();
    progress.classList.remove('active');
  }
});

function startPolling(jobId){
  let prevLen=0;
  pollTimer=setInterval(async()=>{
    try{
      const res=await fetch('/status/'+jobId);
      if(!res.ok)return;
      const data=await res.json();

      // Update logs
      if(data.logs&&data.logs.length>prevLen){
        const lines=data.logs.trim().split('\\n');
        logContent.innerHTML=lines.map((l,i)=>{
          const cls=l.startsWith('ERROR')?'log-line error':'log-line';
          return '<span class="'+cls+'">'+escHtml(l)+'</span>';
        }).join('');
        logPanel.scrollTop=logPanel.scrollHeight;
        prevLen=data.logs.length;
        // Show latest line as progress sub
        const last=lines[lines.length-1];
        if(last)progressSub.textContent=last;
      }

      if(data.state==='done'){
        clearInterval(pollTimer);
        pollTimer=null;
        progress.classList.remove('active');
        if(data.result){
          currentJobId=jobId;
          renderResultsFromJob(jobId,data.result);
          resultsTitle.textContent='Your Video';
        }else{
          showError('Job completed but no result returned');
          resetUI();
        }
      }else if(data.state==='error'){
        clearInterval(pollTimer);
        pollTimer=null;
        progress.classList.remove('active');
        showError('Generation failed: '+(data.error||'Unknown error'));
        resetUI();
      }
    }catch(e){}
  },3000);
}

function escHtml(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}

// ── Avatar Overlay ──
const avatarDropZone=document.getElementById('avatarDropZone');
const avatarFileInput=document.getElementById('avatarFileInput');
const avatarFileName=document.getElementById('avatarFileName');
const avatarBtn=document.getElementById('avatarBtn');
let avatarFile=null;

avatarDropZone.addEventListener('click',()=>avatarFileInput.click());
avatarDropZone.addEventListener('dragover',e=>{e.preventDefault();avatarDropZone.style.borderColor='#60a5fa'});
avatarDropZone.addEventListener('dragleave',()=>{avatarDropZone.style.borderColor=''});
avatarDropZone.addEventListener('drop',e=>{e.preventDefault();avatarDropZone.style.borderColor='';setAvatarFile(e.dataTransfer.files[0])});
avatarFileInput.addEventListener('change',()=>{if(avatarFileInput.files[0])setAvatarFile(avatarFileInput.files[0])});

function setAvatarFile(f){
  avatarFile=f;
  avatarFileName.textContent=f.name;
  avatarFileName.classList.remove('hidden');
  avatarDropZone.classList.add('has-file');
  avatarBtn.disabled=false;
}

document.getElementById('avatarScale').addEventListener('input',e=>{document.getElementById('avatarScaleVal').textContent=Math.round(e.target.value*100)+'%'});
document.getElementById('avatarOpacity').addEventListener('input',e=>{document.getElementById('avatarOpacityVal').textContent=e.target.value});

avatarBtn.addEventListener('click',async()=>{
  if(!currentVideoB64||!avatarFile)return;
  avatarBtn.disabled=true;
  avatarBtn.textContent='Applying...';
  progress.classList.add('active');
  progressText.textContent='Applying avatar overlay...';
  progressSub.textContent='';
  hideError();

  const fd=new FormData();
  fd.append('video',b64toBlob(currentVideoB64,'video/mp4'),'video.mp4');
  fd.append('avatar',avatarFile);
  fd.append('position',document.getElementById('avatarPosition').value);
  fd.append('scale',document.getElementById('avatarScale').value);
  fd.append('opacity',document.getElementById('avatarOpacity').value);

  try{
    const res=await fetch('/avatar',{method:'POST',body:fd});
    if(!res.ok){const t=await res.text();throw new Error(t||'HTTP '+res.status)}
    const data=await res.json();
    if(data.video)currentVideoB64=data.video;
    renderResults({video:currentVideoB64,audio:currentAudioB64,music:currentMusicB64});
    resultsTitle.textContent='Video with Avatar';
  }catch(e){
    showError('Avatar overlay failed: '+e.message);
  }finally{
    progress.classList.remove('active');
    avatarBtn.disabled=false;
    avatarBtn.textContent='Apply Avatar';
  }
});

// ── Post-process ──
document.getElementById('postSpeed').addEventListener('input',e=>{document.getElementById('postSpeedVal').textContent=e.target.value+'x'});
document.getElementById('postVoiceVol').addEventListener('input',e=>{document.getElementById('postVoiceVolVal').textContent=e.target.value});
document.getElementById('postMusicVol').addEventListener('input',e=>{document.getElementById('postMusicVolVal').textContent=e.target.value});

document.getElementById('postBtn').addEventListener('click',async()=>{
  if(!currentVideoB64)return;
  const postBtn=document.getElementById('postBtn');
  postBtn.disabled=true;
  postBtn.textContent='Processing...';
  progress.classList.add('active');
  progressText.textContent='Applying post-processing...';
  progressSub.textContent='Adjusting speed and audio levels';
  hideError();

  const speed=parseFloat(document.getElementById('postSpeed').value);
  const voiceVol=parseFloat(document.getElementById('postVoiceVol').value);
  const musicVol=parseFloat(document.getElementById('postMusicVol').value);

  const fd=new FormData();
  const videoBlob=b64toBlob(currentVideoB64,'video/mp4');
  fd.append('video',videoBlob,'video.mp4');
  fd.append('video_speed',speed.toString());
  fd.append('voice_volume',voiceVol.toString());
  fd.append('music_volume',musicVol.toString());

  if(currentAudioB64)fd.append('voice_audio',b64toBlob(currentAudioB64,'audio/mpeg'),'voice.mp3');
  if(currentMusicB64)fd.append('music_audio',b64toBlob(currentMusicB64,'audio/mpeg'),'music.mp3');

  try{
    const res=await fetch('/post',{method:'POST',body:fd});
    if(!res.ok){const t=await res.text();throw new Error(t||'HTTP '+res.status)}
    const data=await res.json();
    if(data.video)currentVideoB64=data.video;
    if(data.audio)currentAudioB64=data.audio;
    renderResults({video:currentVideoB64,audio:currentAudioB64,music:currentMusicB64});
    resultsTitle.textContent='Post-Processed Video';
  }catch(e){
    showError('Post-processing failed: '+e.message);
  }finally{
    progress.classList.remove('active');
    postBtn.disabled=false;
    postBtn.textContent='Apply Post-Processing';
  }
});

// ── Helpers ──
function b64toBlob(b64,mime){
  const bytes=atob(b64);
  const arr=new Uint8Array(bytes.length);
  for(let i=0;i<bytes.length;i++)arr[i]=bytes.charCodeAt(i);
  return new Blob([arr],{type:mime});
}

function renderResults(data){
  results.classList.add('active');
  voiceSection.classList.add('hidden');
  videoSection.classList.add('hidden');

  const videoWrap=document.getElementById('videoWrap');
  videoWrap.innerHTML='';
  if(data.video){
    const v=document.createElement('video');
    v.src='data:video/mp4;base64,'+data.video;
    v.controls=true;v.autoplay=true;
    videoWrap.appendChild(v);
  }

  const dlRow=document.getElementById('dlRow');
  dlRow.innerHTML='';
  if(data.video)dlRow.appendChild(makeDlBtn(data.video,'video/mp4','video.mp4','Download Video'));
  if(data.audio)dlRow.appendChild(makeDlBtn(data.audio,'audio/mpeg','audio.mp3','Download Audio'));
  if(data.music)dlRow.appendChild(makeDlBtn(data.music,'audio/mpeg','music.mp3','Download Music'));

  // Cost estimation
  const costEl=document.getElementById('costEstimate');
  if(data.cost&&costEl){
    const c=data.cost;
    let html='<h4>Estimated Cost</h4><div class="cost-grid">';
    html+='<span class="cost-label">Gemini Vision ('+c.num_scenes+' scenes)</span><span class="cost-val">$'+c.gemini_vision.toFixed(3)+'</span>';
    if(c.veo_animation>0)html+='<span class="cost-label">Veo 3.1 Animation</span><span class="cost-val">$'+c.veo_animation.toFixed(3)+'</span>';
    if(c.tts>0)html+='<span class="cost-label">ElevenLabs TTS</span><span class="cost-val">$'+c.tts.toFixed(3)+'</span>';
    if(c.music>0)html+='<span class="cost-label">Music Generation</span><span class="cost-val">$'+c.music.toFixed(3)+'</span>';
    html+='<span class="cost-label cost-total">Total</span><span class="cost-val cost-total">$'+c.total.toFixed(2)+'</span>';
    html+='</div>';
    costEl.innerHTML=html;
    costEl.classList.remove('hidden');
  }
}

function renderResultsFromJob(jobId,resultMeta){
  results.classList.add('active');
  voiceSection.classList.add('hidden');
  videoSection.classList.add('hidden');

  const videoWrap=document.getElementById('videoWrap');
  videoWrap.innerHTML='';
  if(resultMeta.has_video){
    const v=document.createElement('video');
    v.src='/download/'+jobId+'/video';
    v.controls=true;v.autoplay=true;
    videoWrap.appendChild(v);
  }

  const dlRow=document.getElementById('dlRow');
  dlRow.innerHTML='';
  if(resultMeta.has_video)dlRow.appendChild(makeStreamDlBtn('/download/'+jobId+'/video','video.mp4','Download Video'));
  if(resultMeta.has_audio)dlRow.appendChild(makeStreamDlBtn('/download/'+jobId+'/audio','audio.mp3','Download Audio'));
  if(resultMeta.has_music)dlRow.appendChild(makeStreamDlBtn('/download/'+jobId+'/music','music.mp3','Download Music'));

  // Cost estimation
  const costEl=document.getElementById('costEstimate');
  if(resultMeta.cost&&costEl){
    const c=resultMeta.cost;
    let html='<h4>Estimated Cost</h4><div class="cost-grid">';
    html+='<span class="cost-label">Gemini Vision ('+c.num_scenes+' scenes)</span><span class="cost-val">$'+c.gemini_vision.toFixed(3)+'</span>';
    if(c.veo_animation>0)html+='<span class="cost-label">Veo 3.1 Animation</span><span class="cost-val">$'+c.veo_animation.toFixed(3)+'</span>';
    if(c.tts>0)html+='<span class="cost-label">ElevenLabs TTS</span><span class="cost-val">$'+c.tts.toFixed(3)+'</span>';
    if(c.music>0)html+='<span class="cost-label">Music Generation</span><span class="cost-val">$'+c.music.toFixed(3)+'</span>';
    html+='<span class="cost-label cost-total">Total</span><span class="cost-val cost-total">$'+c.total.toFixed(2)+'</span>';
    html+='</div>';
    costEl.innerHTML=html;
    costEl.classList.remove('hidden');
  }

  // Load video as base64 for post-processing/avatar (fetch in background)
  if(resultMeta.has_video){
    fetch('/download/'+jobId+'/video').then(r=>r.blob()).then(blob=>{
      const reader=new FileReader();
      reader.onload=()=>{currentVideoB64=reader.result.split(',')[1]};
      reader.readAsDataURL(blob);
    });
  }
  if(resultMeta.has_audio){
    fetch('/download/'+jobId+'/audio').then(r=>r.blob()).then(blob=>{
      const reader=new FileReader();
      reader.onload=()=>{currentAudioB64=reader.result.split(',')[1]};
      reader.readAsDataURL(blob);
    });
  }
  if(resultMeta.has_music){
    fetch('/download/'+jobId+'/music').then(r=>r.blob()).then(blob=>{
      const reader=new FileReader();
      reader.onload=()=>{currentMusicB64=reader.result.split(',')[1]};
      reader.readAsDataURL(blob);
    });
  }
}

function makeStreamDlBtn(url,filename,label){
  const btn=document.createElement('button');
  btn.className='btn btn-secondary';
  btn.textContent=label;
  btn.onclick=()=>{const a=document.createElement('a');a.href=url;a.download=filename;a.click()};
  return btn;
}

function makeDlBtn(b64,mime,filename,label){
  const btn=document.createElement('button');
  btn.className='btn btn-secondary';
  btn.textContent=label;
  btn.onclick=()=>{const a=document.createElement('a');a.href='data:'+mime+';base64,'+b64;a.download=filename;a.click()};
  return btn;
}

document.getElementById('newBtn').addEventListener('click',()=>{
  selectedFiles=[];fileInput.value='';currentVideoB64=null;currentAudioB64=null;currentMusicB64=null;currentJobId=null;
  fileList.classList.add('hidden');
  dropZone.classList.remove('has-file');
  results.classList.remove('active');
  resetUI();
});

function resetUI(){voiceSection.classList.remove('hidden');videoSection.classList.remove('hidden');generateBtn.disabled=true;urlSbUseBtn.disabled=false;urlSbUseBtn.textContent='Create Video from Storyboard'}
function showError(msg){errorMsg.textContent=msg;errorMsg.classList.add('active')}
function hideError(){errorMsg.classList.remove('active')}
// ── Bookend Gallery ──
const enableBookends=document.getElementById('enableBookends');
const bookendPanel=document.getElementById('bookendPanel');
const bookendGenBtn=document.getElementById('bookendGenBtn');
const bookendProgress=document.getElementById('bookendProgress');
const bookendProgressText=document.getElementById('bookendProgressText');
const bookendResults=document.getElementById('bookendResults');
const introSection=document.getElementById('introSection');
const outroSection=document.getElementById('outroSection');
const introGallery=document.getElementById('introGallery');
const outroGallery=document.getElementById('outroGallery');
let bookendJobId=null,selectedIntro=null,selectedOutro=null,bookendData=null;
let introRefFile=null,outroRefFile=null;

// Reference image uploads
const introRefZone=document.getElementById('introRefZone');
const introRefInput=document.getElementById('introRefInput');
const introRefName=document.getElementById('introRefName');
const outroRefZone=document.getElementById('outroRefZone');
const outroRefInput=document.getElementById('outroRefInput');
const outroRefName=document.getElementById('outroRefName');

introRefZone.addEventListener('click',()=>introRefInput.click());
introRefZone.addEventListener('dragover',e=>{e.preventDefault();introRefZone.style.borderColor='#60a5fa'});
introRefZone.addEventListener('dragleave',()=>{introRefZone.style.borderColor=''});
introRefZone.addEventListener('drop',e=>{e.preventDefault();introRefZone.style.borderColor='';if(e.dataTransfer.files[0])setIntroRef(e.dataTransfer.files[0])});
introRefInput.addEventListener('change',()=>{if(introRefInput.files[0])setIntroRef(introRefInput.files[0])});
function setIntroRef(f){introRefFile=f;introRefName.textContent=f.name;introRefName.classList.remove('hidden');introRefZone.classList.add('has-file')}

outroRefZone.addEventListener('click',()=>outroRefInput.click());
outroRefZone.addEventListener('dragover',e=>{e.preventDefault();outroRefZone.style.borderColor='#60a5fa'});
outroRefZone.addEventListener('dragleave',()=>{outroRefZone.style.borderColor=''});
outroRefZone.addEventListener('drop',e=>{e.preventDefault();outroRefZone.style.borderColor='';if(e.dataTransfer.files[0])setOutroRef(e.dataTransfer.files[0])});
outroRefInput.addEventListener('change',()=>{if(outroRefInput.files[0])setOutroRef(outroRefInput.files[0])});
function setOutroRef(f){outroRefFile=f;outroRefName.textContent=f.name;outroRefName.classList.remove('hidden');outroRefZone.classList.add('has-file')}

enableBookends.addEventListener('change',()=>{
  bookendPanel.classList.toggle('hidden',!enableBookends.checked);
  if(!enableBookends.checked){bookendJobId=null;selectedIntro=null;selectedOutro=null;bookendData=null}
});

bookendGenBtn.addEventListener('click',async()=>{
  const wantIntro=document.getElementById('generateIntro').checked;
  const wantOutro=document.getElementById('generateOutro').checked;
  if(!wantIntro&&!wantOutro)return;
  bookendGenBtn.disabled=true;
  bookendGenBtn.textContent='Generating...';
  bookendProgress.classList.remove('hidden');
  bookendResults.classList.add('hidden');
  introSection.classList.add('hidden');
  outroSection.classList.add('hidden');
  selectedIntro=null;selectedOutro=null;bookendData=null;

  const fd=new FormData();
  fd.append('product',document.getElementById('product').value);
  fd.append('storyline',document.getElementById('storyline').value);
  fd.append('tone',document.getElementById('tone').value);
  fd.append('style',document.getElementById('style').value);
  fd.append('generate_intro',wantIntro?'true':'false');
  fd.append('generate_outro',wantOutro?'true':'false');
  fd.append('intro_prompt',document.getElementById('introPrompt').value);
  fd.append('outro_prompt',document.getElementById('outroPrompt').value);
  if(introRefFile)fd.append('intro_ref',introRefFile);
  if(outroRefFile)fd.append('outro_ref',outroRefFile);

  try{
    const res=await fetch('/bookends',{method:'POST',body:fd});
    if(!res.ok){const t=await res.text();throw new Error(t||'HTTP '+res.status)}
    const data=await res.json();
    if(data.job_id){
      bookendJobId=data.job_id;
      bookendProgressText.textContent='Generating frame options...';
      startBookendPolling(data.job_id);
    }
  }catch(e){
    bookendProgressText.textContent='Failed: '+e.message;
    bookendGenBtn.disabled=false;
    bookendGenBtn.textContent='Generate Frame Options';
  }
});

function startBookendPolling(jobId){
  const timer=setInterval(async()=>{
    try{
      const res=await fetch('/bookend-status/'+jobId);
      if(!res.ok)return;
      const data=await res.json();
      if(data.state==='done'){
        clearInterval(timer);
        bookendProgress.classList.add('hidden');
        bookendGenBtn.disabled=false;
        bookendGenBtn.textContent='Regenerate Frame Options';
        if(data.result)renderBookendGallery(data.result,jobId);
      }else if(data.state==='error'){
        clearInterval(timer);
        bookendProgressText.textContent='Error: '+(data.error||'Unknown');
        bookendGenBtn.disabled=false;
        bookendGenBtn.textContent='Generate Frame Options';
      }
    }catch(e){}
  },3000);
}

function renderBookendGallery(result,jobId){
  bookendData=result;
  bookendResults.classList.remove('hidden');

  // Render intro options
  if(result.intro_options&&result.intro_options.length){
    introSection.classList.remove('hidden');
    introGallery.innerHTML='';
    result.intro_options.forEach((opt,i)=>{
      if(!opt.image_filename)return;
      const card=document.createElement('div');
      card.className='bookend-card'+(i===0?' selected':'');
      card.innerHTML='<span class="bookend-card-badge">Selected</span><img src="/bookend-image/'+jobId+'/'+opt.image_filename+'" loading="lazy"><div class="bookend-card-info"><div class="bookend-card-title">'+escHtml(opt.title_text)+'</div><div class="bookend-card-sub">'+escHtml(opt.subtitle_text)+'</div></div>';
      card.addEventListener('click',()=>{
        introGallery.querySelectorAll('.bookend-card').forEach(c=>c.classList.remove('selected'));
        card.classList.add('selected');
        selectedIntro=opt;
      });
      introGallery.appendChild(card);
    });
    // Auto-select first
    const firstValid=result.intro_options.find(o=>o.image_filename);
    if(firstValid)selectedIntro=firstValid;
  }

  // Render outro options
  if(result.outro_options&&result.outro_options.length){
    outroSection.classList.remove('hidden');
    outroGallery.innerHTML='';
    result.outro_options.forEach((opt,i)=>{
      if(!opt.image_filename)return;
      const card=document.createElement('div');
      card.className='bookend-card'+(i===0?' selected':'');
      card.innerHTML='<span class="bookend-card-badge">Selected</span><img src="/bookend-image/'+jobId+'/'+opt.image_filename+'" loading="lazy"><div class="bookend-card-info"><div class="bookend-card-title">'+escHtml(opt.title_text)+'</div><div class="bookend-card-sub">'+escHtml(opt.subtitle_text)+'</div></div>';
      card.addEventListener('click',()=>{
        outroGallery.querySelectorAll('.bookend-card').forEach(c=>c.classList.remove('selected'));
        card.classList.add('selected');
        selectedOutro=opt;
      });
      outroGallery.appendChild(card);
    });
    const firstValid=result.outro_options.find(o=>o.image_filename);
    if(firstValid)selectedOutro=firstValid;
  }
}

// ── Video Modal (expand sample with sound) ──
const videoModalOverlay=document.createElement('div');
videoModalOverlay.className='video-modal-overlay';
videoModalOverlay.innerHTML='<div class="video-modal"><button class="video-modal-close">&times;</button><video controls autoplay></video></div>';
document.body.appendChild(videoModalOverlay);
const modalVideo=videoModalOverlay.querySelector('video');
const modalClose=videoModalOverlay.querySelector('.video-modal-close');

function openVideoModal(src){
  modalVideo.src=src;
  modalVideo.muted=false;
  modalVideo.currentTime=0;
  videoModalOverlay.classList.add('active');
  modalVideo.play();
}
function closeVideoModal(){
  videoModalOverlay.classList.remove('active');
  modalVideo.pause();
  modalVideo.src='';
}
modalClose.addEventListener('click',closeVideoModal);
videoModalOverlay.addEventListener('click',e=>{if(e.target===videoModalOverlay)closeVideoModal()});
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeVideoModal()});
</script>
</body>
</html>"""


@app.function(image=image, secrets=[secrets], timeout=1800, volumes={"/cache": volume})
@asgi_app(custom_domains=["video-generator.transilienceapi.com"])
def fastapi_app():
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse, HTMLResponse

    web_app = FastAPI()

    from fastapi.middleware.cors import CORSMiddleware
    web_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    import os as _os
    clerk_pk = _os.environ.get("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", _os.environ.get("CLERK_PUBLISHABLE_KEY", ""))

    @web_app.get("/", response_class=HTMLResponse)
    async def index():
        return LANDING_HTML.replace("__CLERK_PK__", clerk_pk)

    @web_app.get("/app", response_class=HTMLResponse)
    async def app_page():
        return APP_HTML.replace("__CLERK_PK__", clerk_pk)

    @web_app.get("/health")
    async def health():
        return {"status": "ok", "service": "video-generator"}

    @web_app.post("/create")
    async def create(request: Request):
        import uuid
        form = await request.form()

        uploaded_files = form.getlist("files")
        files_dict = {}
        for f in uploaded_files:
            data = await f.read()
            files_dict[f.filename] = data

        if not files_dict:
            return JSONResponse(status_code=400, content={"error": "No files uploaded"})

        job_id = str(uuid.uuid4())[:12]

        product = form.get("product", "")
        voice = form.get("voice", "Smritika")
        style = form.get("style", "marketing")
        tone = form.get("tone", "professional and engaging")
        resolution = form.get("resolution", "1080p")
        script_duration = int(form.get("script_duration", "60"))
        storyline = form.get("storyline", "")
        generate_music = form.get("generate_music", "false") == "true"
        music_prompt = form.get("music_prompt", "")
        generate_intro = form.get("generate_intro", "false") == "true"
        generate_outro = form.get("generate_outro", "false") == "true"
        bookend_job_id = form.get("bookend_job_id", "")
        intro_option = int(form.get("intro_option", "0"))
        outro_option = int(form.get("outro_option", "0"))
        intro_veo_prompt = form.get("intro_veo_prompt", "")
        outro_veo_prompt = form.get("outro_veo_prompt", "")

        # Spawn async — don't wait
        create_video_worker.spawn(
            job_id=job_id,
            files=files_dict,
            voice=voice,
            product=product,
            style=style,
            tone=tone,
            resolution=resolution,
            script_duration=script_duration,
            storyline=storyline,
            generate_music=generate_music,
            music_prompt=music_prompt,
            generate_intro=generate_intro,
            generate_outro=generate_outro,
            bookend_job_id=bookend_job_id,
            intro_option=intro_option,
            outro_option=outro_option,
            intro_veo_prompt=intro_veo_prompt,
            outro_veo_prompt=outro_veo_prompt,
        )

        return JSONResponse(content={"job_id": job_id})

    @web_app.get("/status/{job_id}")
    async def job_status(job_id: str):
        import json
        from pathlib import Path

        log_dir = Path(f"/cache/jobs/{job_id}")
        volume.reload()

        # Read logs
        log_file = log_dir / "log.txt"
        logs = ""
        if log_file.exists():
            logs = log_file.read_text()

        # Read status
        status_file = log_dir / "status.json"
        state = "pending"
        error = ""
        if status_file.exists():
            st = json.loads(status_file.read_text())
            state = st.get("state", "pending")
            error = st.get("error", "")

        resp = {"state": state, "logs": logs, "error": error}

        # If done, include result (don't cleanup — images needed for preview + create)
        if state == "done":
            result_file = log_dir / "result.json"
            if result_file.exists():
                resp["result"] = json.loads(result_file.read_text())

        return JSONResponse(content=resp)

    @web_app.get("/download/{job_id}/{file_type}")
    async def download_file(job_id: str, file_type: str):
        """Stream video/audio/music files from a completed job."""
        from fastapi.responses import StreamingResponse
        from pathlib import Path

        allowed_types = {
            "video": ("output.mp4", "video/mp4"),
            "audio": ("output.mp3", "audio/mpeg"),
            "music": ("output_music.mp3", "audio/mpeg"),
        }
        if file_type not in allowed_types:
            return JSONResponse(status_code=400, content={"error": "Invalid file type"})

        volume.reload()
        filename, mime = allowed_types[file_type]
        file_path = Path(f"/cache/jobs/{job_id}/{filename}")
        if not file_path.exists():
            return JSONResponse(status_code=404, content={"error": "File not found"})

        file_size = file_path.stat().st_size

        def iterfile():
            with open(file_path, "rb") as f:
                while chunk := f.read(1024 * 1024):
                    yield chunk

        return StreamingResponse(
            iterfile(),
            media_type=mime,
            headers={
                "Content-Length": str(file_size),
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )

    @web_app.get("/sample/{style}")
    async def get_sample(style: str):
        from fastapi.responses import StreamingResponse
        from pathlib import Path

        allowed = {"marketing", "feature-explainer", "tutorial-explainer"}
        if style not in allowed:
            return JSONResponse(status_code=404, content={"error": "Unknown style"})

        volume.reload()
        sample_path = Path(f"/cache/samples/{style}.mp4")
        if not sample_path.exists():
            return JSONResponse(status_code=404, content={"error": "No sample video"})

        file_size = sample_path.stat().st_size

        def iterfile():
            with open(sample_path, "rb") as f:
                while chunk := f.read(1024 * 1024):  # 1MB chunks
                    yield chunk

        return StreamingResponse(
            iterfile(),
            media_type="video/mp4",
            headers={
                "Cache-Control": "public, max-age=3600",
                "Content-Length": str(file_size),
                "Accept-Ranges": "bytes",
            },
        )

    @web_app.head("/sample/{style}")
    async def head_sample(style: str):
        """Quick check if sample exists without downloading."""
        from fastapi.responses import Response
        from pathlib import Path

        allowed = {"marketing", "feature-explainer", "tutorial-explainer"}
        if style not in allowed:
            return JSONResponse(status_code=404, content={"error": "Unknown style"})

        volume.reload()
        sample_path = Path(f"/cache/samples/{style}.mp4")
        if not sample_path.exists():
            return JSONResponse(status_code=404, content={"error": "No sample video"})

        return Response(
            headers={"Content-Length": str(sample_path.stat().st_size)},
            media_type="video/mp4",
        )

    @web_app.post("/upload-sample")
    async def upload_sample(request: Request):
        from pathlib import Path

        form = await request.form()
        style = form.get("style", "")
        allowed = {"marketing", "feature-explainer", "tutorial-explainer"}
        if style not in allowed:
            return JSONResponse(status_code=400, content={"error": "Invalid style"})

        video_file = form.get("video")
        if not video_file:
            return JSONResponse(status_code=400, content={"error": "No video uploaded"})

        data = await video_file.read()
        sample_dir = Path("/cache/samples")
        sample_dir.mkdir(parents=True, exist_ok=True)
        (sample_dir / f"{style}.mp4").write_bytes(data)
        volume.commit()

        return JSONResponse(content={"success": True, "style": style})

    @web_app.get("/voices")
    async def list_voices():
        voices = list_voices_worker.remote()
        return JSONResponse(content={"voices": voices})

    @web_app.post("/voice-clone")
    async def voice_clone(request: Request):
        form = await request.form()

        uploaded_files = form.getlist("audio_files")
        audio_dict = {}
        for f in uploaded_files:
            data = await f.read()
            audio_dict[f.filename] = data

        if not audio_dict:
            return JSONResponse(status_code=400, content={"error": "No audio files uploaded"})

        name = form.get("name", "").strip()
        if not name:
            return JSONResponse(status_code=400, content={"error": "Voice name is required"})

        result = voice_clone_worker.remote(
            audio_files=audio_dict,
            name=name,
            description=form.get("description", ""),
            accent=form.get("accent", ""),
            gender=form.get("gender", ""),
            age=form.get("age", ""),
        )

        return JSONResponse(content=result)

    @web_app.post("/storyboard")
    async def create_storyboard(request: Request):
        import uuid
        form = await request.form()

        url = form.get("url", "").strip()
        if not url:
            return JSONResponse(status_code=400, content={"error": "URL is required"})
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url

        job_id = f"sb-{str(uuid.uuid4())[:10]}"

        storyboard_worker.spawn(
            job_id=job_id,
            url=url,
            storyline=form.get("storyline", ""),
            product=form.get("product", ""),
            num_scenes=int(form.get("scenes", "6")),
            tone=form.get("tone", "professional and engaging"),
            style=form.get("style", "marketing"),
            aspect_ratio=form.get("aspect_ratio", "16:9"),
            skip_screenshots=form.get("skip_screenshots", "false") == "true",
            skip_imagen=form.get("skip_imagen", "false") == "true",
        )

        return JSONResponse(content={"job_id": job_id})

    @web_app.get("/storyboard-status/{job_id}")
    async def storyboard_status(job_id: str):
        import json as _json
        from pathlib import Path

        log_dir = Path(f"/cache/storyboard/{job_id}")
        volume.reload()

        log_file = log_dir / "log.txt"
        logs = ""
        if log_file.exists():
            logs = log_file.read_text()

        status_file = log_dir / "status.json"
        state = "pending"
        error = ""
        if status_file.exists():
            st = _json.loads(status_file.read_text())
            state = st.get("state", "pending")
            error = st.get("error", "")

        resp = {"state": state, "logs": logs, "error": error}

        if state == "done":
            result_file = log_dir / "result.json"
            if result_file.exists():
                resp["result"] = _json.loads(result_file.read_text())

        return JSONResponse(content=resp)

    @web_app.get("/storyboard-image/{job_id}/{filename}")
    async def get_storyboard_image(job_id: str, filename: str):
        from fastapi.responses import Response
        from pathlib import Path
        import re as _re

        # Sanitize filename
        if not _re.match(r'^[\w\-\.]+$', filename):
            return JSONResponse(status_code=400, content={"error": "Invalid filename"})

        volume.reload()
        img_path = Path(f"/cache/storyboard/{job_id}/images/{filename}")
        if not img_path.exists():
            img_path = Path(f"/cache/storyboard/{job_id}/sequence/{filename}")
        if not img_path.exists():
            return JSONResponse(status_code=404, content={"error": "Image not found"})

        return Response(
            content=img_path.read_bytes(),
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=3600"},
        )

    @web_app.post("/create-from-storyboard")
    async def create_from_storyboard(request: Request):
        """Create video using storyboard sequence images."""
        import uuid
        import json as _json
        from pathlib import Path

        form = await request.form()
        sb_job_id = form.get("storyboard_job_id", "").strip()
        if not sb_job_id:
            return JSONResponse(status_code=400, content={"error": "storyboard_job_id is required"})

        volume.reload()
        seq_dir = Path(f"/cache/storyboard/{sb_job_id}/sequence")
        if not seq_dir.exists():
            return JSONResponse(status_code=404, content={"error": "Storyboard sequence not found"})

        # Read sequence images into files dict
        files_dict = {}
        for f in sorted(seq_dir.iterdir()):
            if f.suffix.lower() in ('.png', '.jpg', '.jpeg'):
                files_dict[f.name] = f.read_bytes()

        if not files_dict:
            return JSONResponse(status_code=400, content={"error": "No images in storyboard sequence"})

        job_id = str(uuid.uuid4())[:12]

        product = form.get("product", "")
        voice = form.get("voice", "Smritika")
        style = form.get("style", "marketing")
        tone = form.get("tone", "professional and engaging")
        resolution = form.get("resolution", "1080p")
        script_duration = int(form.get("script_duration", "60"))
        storyline = form.get("storyline", "")
        generate_music = form.get("generate_music", "false") == "true"
        music_prompt = form.get("music_prompt", "")
        generate_intro = form.get("generate_intro", "false") == "true"
        generate_outro = form.get("generate_outro", "false") == "true"
        bookend_job_id = form.get("bookend_job_id", "")
        intro_option = int(form.get("intro_option", "0"))
        outro_option = int(form.get("outro_option", "0"))
        intro_veo_prompt = form.get("intro_veo_prompt", "")
        outro_veo_prompt = form.get("outro_veo_prompt", "")

        create_video_worker.spawn(
            job_id=job_id,
            files=files_dict,
            voice=voice,
            product=product,
            style=style,
            tone=tone,
            resolution=resolution,
            script_duration=script_duration,
            storyline=storyline,
            generate_music=generate_music,
            music_prompt=music_prompt,
            ai_order=True,
            generate_intro=generate_intro,
            generate_outro=generate_outro,
            bookend_job_id=bookend_job_id,
            intro_option=intro_option,
            outro_option=outro_option,
            intro_veo_prompt=intro_veo_prompt,
            outro_veo_prompt=outro_veo_prompt,
        )

        return JSONResponse(content={"job_id": job_id})

    @web_app.post("/bookends")
    async def create_bookends(request: Request):
        """Generate bookend frame options (Gemini + Imagen only, no Veo)."""
        import uuid
        from pathlib import Path as _Path

        form = await request.form()
        job_id = f"bk-{str(uuid.uuid4())[:10]}"

        # Save reference images to volume so worker can access them
        ref_images = {}
        for key in ("intro_ref", "outro_ref"):
            ref_file = form.get(key)
            if ref_file and hasattr(ref_file, "read"):
                data = await ref_file.read()
                if data:
                    ref_dir = _Path(f"/cache/bookends/{job_id}/refs")
                    ref_dir.mkdir(parents=True, exist_ok=True)
                    ref_path = ref_dir / f"{key}{_Path(ref_file.filename).suffix}"
                    ref_path.write_bytes(data)
                    ref_images[key] = str(ref_path)
        if ref_images:
            volume.commit()

        bookend_worker.spawn(
            job_id=job_id,
            product=form.get("product", ""),
            storyline=form.get("storyline", ""),
            tone=form.get("tone", "professional and engaging"),
            style=form.get("style", "marketing"),
            generate_intro=form.get("generate_intro", "true") == "true",
            generate_outro=form.get("generate_outro", "true") == "true",
            intro_prompt=form.get("intro_prompt", ""),
            outro_prompt=form.get("outro_prompt", ""),
            intro_ref_path=ref_images.get("intro_ref", ""),
            outro_ref_path=ref_images.get("outro_ref", ""),
        )

        return JSONResponse(content={"job_id": job_id})

    @web_app.get("/bookend-status/{job_id}")
    async def bookend_status(job_id: str):
        import json as _json
        from pathlib import Path

        log_dir = Path(f"/cache/bookends/{job_id}")
        volume.reload()

        status_file = log_dir / "status.json"
        state = "pending"
        error = ""
        if status_file.exists():
            st = _json.loads(status_file.read_text())
            state = st.get("state", "pending")
            error = st.get("error", "")

        resp = {"state": state, "error": error}

        if state == "done":
            result_file = log_dir / "result.json"
            if result_file.exists():
                resp["result"] = _json.loads(result_file.read_text())

        return JSONResponse(content=resp)

    @web_app.get("/bookend-image/{job_id}/{filename}")
    async def get_bookend_image(job_id: str, filename: str):
        from fastapi.responses import Response
        from pathlib import Path
        import re as _re

        if not _re.match(r'^[\w\-\.]+$', filename):
            return JSONResponse(status_code=400, content={"error": "Invalid filename"})

        volume.reload()
        img_path = Path(f"/cache/bookends/{job_id}/images/{filename}")
        if not img_path.exists():
            return JSONResponse(status_code=404, content={"error": "Image not found"})

        return Response(
            content=img_path.read_bytes(),
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=3600"},
        )

    @web_app.post("/post")
    async def post_process(request: Request):
        form = await request.form()

        video_file = form.get("video")
        if not video_file:
            return JSONResponse(status_code=400, content={"error": "No video uploaded"})

        video_bytes = await video_file.read()
        video_speed = float(form.get("video_speed", "1.0"))
        voice_volume = float(form.get("voice_volume", "5.0"))
        music_volume = float(form.get("music_volume", "0.03"))

        voice_audio_bytes = b""
        music_audio_bytes = b""

        voice_audio_file = form.get("voice_audio")
        if voice_audio_file:
            voice_audio_bytes = await voice_audio_file.read()

        music_audio_file = form.get("music_audio")
        if music_audio_file:
            music_audio_bytes = await music_audio_file.read()

        result = post_video_worker.remote(
            video_bytes=video_bytes,
            video_speed=video_speed,
            voice_volume=voice_volume,
            music_volume=music_volume,
            voice_audio_bytes=voice_audio_bytes,
            music_audio_bytes=music_audio_bytes,
        )

        return JSONResponse(content=result)

    @web_app.post("/avatar")
    async def avatar_overlay(request: Request):
        import base64
        import tempfile
        from pathlib import Path

        form = await request.form()

        video_file = form.get("video")
        avatar_file = form.get("avatar")
        if not video_file or not avatar_file:
            return JSONResponse(status_code=400, content={"error": "Video and avatar are required"})

        video_bytes = await video_file.read()
        avatar_bytes = await avatar_file.read()
        position = form.get("position", "bottom-right")
        scale = float(form.get("scale", "0.15"))
        opacity = float(form.get("opacity", "1.0"))

        work_dir = Path(tempfile.mkdtemp())
        input_path = work_dir / "input.mp4"
        avatar_ext = Path(avatar_file.filename).suffix or ".png"
        avatar_path = work_dir / f"avatar{avatar_ext}"
        output_path = work_dir / "output.mp4"

        input_path.write_bytes(video_bytes)
        avatar_path.write_bytes(avatar_bytes)

        try:
            from src.processing.avatar_overlay import overlay_avatar as do_overlay
            do_overlay(
                input_video=input_path,
                avatar_source=avatar_path,
                output_video=output_path,
                position=position,
                scale=scale,
                opacity=opacity,
            )

            result = {}
            if output_path.exists():
                result["video"] = base64.b64encode(output_path.read_bytes()).decode()

            import shutil
            shutil.rmtree(str(work_dir), ignore_errors=True)
            return JSONResponse(content=result)

        except Exception as e:
            import shutil
            shutil.rmtree(str(work_dir), ignore_errors=True)
            return JSONResponse(status_code=500, content={"error": str(e)})

    return web_app

