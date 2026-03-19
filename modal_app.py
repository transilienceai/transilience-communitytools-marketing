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
    .add_local_dir("project/videogen/src", remote_path="/app/src")
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
    max_workers: int = 5,
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
    no_voiceover_files: list = None,
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
        log_file.parent.mkdir(parents=True, exist_ok=True)
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
            no_voiceover_files=no_voiceover_files or [],
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
    url: str = "",
    storyline: str = "",
    product: str = "",
    num_scenes: int = 6,
    tone: str = "professional and engaging",
    style: str = "marketing",
    aspect_ratio: str = "16:9",
    skip_screenshots: bool = False,
    skip_imagen: bool = False,
    uploaded_paths: list = [],
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
        log_file.parent.mkdir(parents=True, exist_ok=True)
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

        # Use uploaded files as captures if provided
        if uploaded_paths and not all_captures:
            append_log(f"Using {len(uploaded_paths)} uploaded images as captures...")
            volume.reload()
            for i, upath in enumerate(uploaded_paths):
                p = Path(upath)
                if p.exists():
                    all_captures.append(p)
                    capture_labels.append(p.stem)
                    dest = images_dir / f"ss_{i:03d}_{p.stem}.png"
                    shutil.copy2(str(p), str(dest))
            append_log(f"Loaded {len(all_captures)} uploaded images")
            _do_flush()

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

            from concurrent.futures import ThreadPoolExecutor, as_completed

            def _generate_one_scene(scene):
                slug = re.sub(r'[^\w\s-]', '', scene.title.lower())
                slug = re.sub(r'[\s_-]+', '_', slug).strip('_')[:40]
                filename = f"scene_{scene.scene_number:03d}_{slug}.png"
                filepath = generated_dir / filename

                prefix = _style_prefixes[(scene.scene_number - 1) % len(_style_prefixes)]
                story_context = storyline[:120].rstrip()
                product_tag = f", related to {product}" if product else ""
                imagen_prompt = f"{prefix} {scene.image_description} Context: {story_context}{product_tag}."

                append_log(f"  Generating scene {scene.scene_number}: {scene.title}...")
                generate_image(
                    prompt=imagen_prompt,
                    output_path=filepath,
                    aspect_ratio=aspect_ratio,
                )
                dest = images_dir / f"gen_{scene.scene_number:03d}_{slug}.png"
                shutil.copy2(str(filepath), str(dest))
                append_log(f"  Generated scene {scene.scene_number}")
                return scene.scene_number, filepath

            with ThreadPoolExecutor(max_workers=len(sb.scenes)) as executor:
                futures = {executor.submit(_generate_one_scene, scene): scene for scene in sb.scenes}
                for future in as_completed(futures):
                    scene = futures[future]
                    try:
                        scene_num, filepath = future.result()
                        generated_images[scene_num] = filepath
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


@app.function(image=image, secrets=[secrets], timeout=1800, volumes={"/cache": volume})
@asgi_app(custom_domains=["video-generator.transilienceapi.com"])
def fastapi_app():
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    web_app = FastAPI()

    from fastapi.middleware.cors import CORSMiddleware
    web_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @web_app.get("/")
    async def index():
        return {"status": "ok", "service": "video-generator", "docs": "/docs"}

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
        no_voiceover_files_raw = form.get("no_voiceover_files", "[]")
        try:
            import json as _json
            no_voiceover_files = _json.loads(no_voiceover_files_raw) if no_voiceover_files_raw else []
        except Exception:
            no_voiceover_files = []

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
            no_voiceover_files=no_voiceover_files,
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

    @web_app.get("/recent-jobs")
    async def recent_jobs():
        """List the last 10 completed video jobs."""
        import json as _json
        from pathlib import Path

        volume.reload()
        jobs_dir = Path("/cache/jobs")
        if not jobs_dir.exists():
            return JSONResponse(content={"jobs": []})

        job_entries = []
        for job_dir in sorted(jobs_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if not job_dir.is_dir():
                continue
            status_file = job_dir / "status.json"
            if not status_file.exists():
                continue
            try:
                status = _json.loads(status_file.read_text())
            except Exception:
                continue
            if status.get("state") != "done":
                continue

            has_video = (job_dir / "output.mp4").exists()
            has_audio = (job_dir / "output.mp3").exists()
            has_music = (job_dir / "output_music.mp3").exists()

            if not has_video:
                continue

            job_entries.append({
                "job_id": job_dir.name,
                "created_at": job_dir.stat().st_mtime,
                "has_video": has_video,
                "has_audio": has_audio,
                "has_music": has_music,
            })

            if len(job_entries) >= 10:
                break

        return JSONResponse(content={"jobs": job_entries})

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
        if url and not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url

        # Collect uploaded files
        uploaded_files = form.getlist("files")
        uploaded_paths = []

        job_id = f"sb-{str(uuid.uuid4())[:10]}"

        if uploaded_files and hasattr(uploaded_files[0], "read"):
            from pathlib import Path
            upload_dir = Path(f"/cache/storyboard/{job_id}/uploads")
            upload_dir.mkdir(parents=True, exist_ok=True)
            for i, f in enumerate(uploaded_files):
                fname = getattr(f, "filename", f"file_{i}.png")
                dest = upload_dir / fname
                content = await f.read()
                dest.write_bytes(content)
                uploaded_paths.append(str(dest))
            try:
                volume.commit()
            except Exception:
                pass

        if not url and not uploaded_paths:
            return JSONResponse(status_code=400, content={"error": "Please provide a website URL or upload images"})

        storyboard_worker.spawn(
            job_id=job_id,
            url=url,
            storyline=form.get("storyline", ""),
            product=form.get("product", ""),
            num_scenes=int(form.get("scenes", "6")),
            tone=form.get("tone", "professional and engaging"),
            style=form.get("style", "marketing"),
            aspect_ratio=form.get("aspect_ratio", "16:9"),
            skip_screenshots=form.get("skip_screenshots", "false") == "true" or (not url),
            skip_imagen=form.get("skip_imagen", "false") == "true",
            uploaded_paths=uploaded_paths,
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

    @web_app.post("/analyze-content")
    async def analyze_content(request: Request):
        """Analyze uploaded files with Gemini Vision and suggest video config."""
        import json as _json
        import base64
        import tempfile
        from pathlib import Path

        form = await request.form()
        files = form.getlist("files")
        style = form.get("style", "marketing")

        if not files or not hasattr(files[0], "read"):
            return JSONResponse(status_code=400, content={"error": "No files to analyze"})

        # Read up to 5 images for analysis
        image_parts = []
        filenames = []
        for f in files[:5]:
            content = await f.read()
            fname = getattr(f, "filename", "file.png")
            filenames.append(fname)
            ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else "png"
            mime = {
                "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                "webp": "image/webp", "gif": "image/gif", "bmp": "image/bmp",
                "pdf": "application/pdf",
            }.get(ext, "image/png")
            b64 = base64.b64encode(content).decode()
            image_parts.append({"inline_data": {"mime_type": mime, "data": b64}})

        prompt = f"""Analyze these {len(image_parts)} images/files that will be used to create a {style} video.
Based on what you see, suggest the following configuration values:

1. product_name: What product/service/brand is shown? Give a concise name.
2. tone: What tone fits best? (e.g. "professional and engaging", "energetic and bold", "calm and informative", "inspiring and motivational")
3. storyline: Write a 1-2 sentence narrative arc for a marketing video based on these visuals.
4. music_prompt: Suggest a music style that fits (e.g. "upbeat corporate ASMR, no voice", "calm ambient piano ASMR, no voice"). IMPORTANT: Always include "no voice" and "ASMR sound only" in the music prompt.
5. script_duration: Suggest total narration duration in seconds based on content complexity ({len(image_parts)} images, 5s per scene).
6. intro_prompt: Suggest an intro frame visual description (e.g. "Clean gradient background with centered product logo, modern minimal style")
7. outro_prompt: Suggest an outro/CTA frame visual description (e.g. "Bold call-to-action text with warm gradient, product name prominent")

Return ONLY valid JSON with these exact keys: product_name, tone, storyline, music_prompt, script_duration (integer), intro_prompt, outro_prompt.
No markdown, no explanation, just the JSON object."""

        content_parts = []
        for img in image_parts:
            content_parts.append(img)
        content_parts.append({"text": prompt})

        try:
            import google.genai as genai
            import os
            client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[{"parts": content_parts}],
            )
            text = response.text.strip()
            # Clean markdown code blocks if present
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3].strip()
            if text.startswith("json"):
                text = text[4:].strip()

            suggestions = _json.loads(text)
            return JSONResponse(content=suggestions)
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": f"Analysis failed: {str(e)}"})

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

