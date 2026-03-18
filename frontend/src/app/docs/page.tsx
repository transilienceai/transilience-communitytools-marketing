import Link from "next/link";

const BASE_URL = "https://video-generator.transilienceapi.com";

const endpoints = [
  {
    category: "Health",
    items: [
      {
        method: "GET",
        path: "/health",
        desc: "Health check",
        params: [],
        response: `{ "status": "ok", "service": "video-generator" }`,
      },
    ],
  },
  {
    category: "Video Generation",
    items: [
      {
        method: "POST",
        path: "/create",
        desc: "Start a video generation job from uploaded files. Returns a job ID for polling.",
        params: [
          { name: "files", type: "File[]", required: true, desc: "Content files (images, videos, PDFs, PPTX)" },
          { name: "voice", type: "string", required: false, desc: 'TTS voice name (default: "Smritika")' },
          { name: "style", type: "string", required: false, desc: '"marketing" | "feature-explainer" | "tutorial-explainer"' },
          { name: "product", type: "string", required: false, desc: "Product/service name for scripts" },
          { name: "tone", type: "string", required: false, desc: 'Script tone (default: "professional and engaging")' },
          { name: "resolution", type: "string", required: false, desc: '"720p" | "1080p" | "4k" (default: "1080p")' },
          { name: "script_duration", type: "int", required: false, desc: "Target narration duration in seconds (default: 60)" },
          { name: "storyline", type: "string", required: false, desc: "Narrative storyline to guide scripts and animation" },
          { name: "generate_music", type: "bool", required: false, desc: '"true" to generate AI background music' },
          { name: "music_prompt", type: "string", required: false, desc: 'Music style prompt (e.g. "upbeat corporate")' },
          { name: "generate_intro", type: "bool", required: false, desc: '"true" to add branded intro frame' },
          { name: "generate_outro", type: "bool", required: false, desc: '"true" to add branded outro frame' },
          { name: "bookend_job_id", type: "string", required: false, desc: "Job ID from /bookends for pre-generated frames" },
          { name: "intro_option", type: "int", required: false, desc: "Selected intro option index (0-2)" },
          { name: "outro_option", type: "int", required: false, desc: "Selected outro option index (0-2)" },
          { name: "intro_veo_prompt", type: "string", required: false, desc: "Veo animation prompt for intro" },
          { name: "outro_veo_prompt", type: "string", required: false, desc: "Veo animation prompt for outro" },
        ],
        response: `{ "job_id": "a1b2c3d4e5f6" }`,
        example: `curl -X POST ${BASE_URL}/create \\
  -F "files=@screenshot1.png" \\
  -F "files=@screenshot2.png" \\
  -F "product=My App" \\
  -F "style=marketing" \\
  -F "storyline=AI transforms how teams work" \\
  -F "generate_music=true"`,
      },
      {
        method: "POST",
        path: "/create-from-storyboard",
        desc: "Create video using images from a completed storyboard job. Same parameters as /create, plus storyboard_job_id.",
        params: [
          { name: "storyboard_job_id", type: "string", required: true, desc: "Job ID from /storyboard" },
          { name: "voice", type: "string", required: false, desc: "Same as /create" },
          { name: "style", type: "string", required: false, desc: "Same as /create" },
          { name: "product", type: "string", required: false, desc: "Same as /create" },
          { name: "tone", type: "string", required: false, desc: "Same as /create" },
          { name: "resolution", type: "string", required: false, desc: "Same as /create" },
          { name: "storyline", type: "string", required: false, desc: "Same as /create" },
          { name: "generate_music", type: "bool", required: false, desc: "Same as /create" },
        ],
        response: `{ "job_id": "a1b2c3d4e5f6" }`,
      },
      {
        method: "GET",
        path: "/status/{job_id}",
        desc: "Poll the status of a video generation job. Returns logs, state, and result when done.",
        params: [
          { name: "job_id", type: "string", required: true, desc: "Job ID from /create" },
        ],
        response: `{
  "state": "done",
  "logs": "Step 1: Scanning files...\\nStep 2: ...",
  "error": "",
  "result": {
    "has_video": true,
    "has_audio": true,
    "has_music": true,
    "cost": {
      "num_scenes": 5,
      "gemini_vision": 0.03,
      "veo_animation": 0.25,
      "tts": 0.02,
      "music": 0.03,
      "total": 0.33
    }
  }
}`,
        example: `curl ${BASE_URL}/status/a1b2c3d4e5f6`,
      },
      {
        method: "GET",
        path: "/download/{job_id}/{file_type}",
        desc: "Stream download a completed file. Returns binary data with appropriate Content-Type.",
        params: [
          { name: "job_id", type: "string", required: true, desc: "Job ID from /create" },
          { name: "file_type", type: "string", required: true, desc: '"video" (MP4) | "audio" (MP3 with voice+music) | "music" (MP3 music only)' },
        ],
        response: "Binary stream (video/mp4 or audio/mpeg)",
        example: `curl -o output.mp4 ${BASE_URL}/download/a1b2c3d4e5f6/video
curl -o output.mp3 ${BASE_URL}/download/a1b2c3d4e5f6/audio`,
      },
    ],
  },
  {
    category: "Storyboard",
    items: [
      {
        method: "POST",
        path: "/storyboard",
        desc: "Generate a storyboard from a website URL. Crawls the site, plans scenes with Gemini Vision, generates images with Imagen 4.0.",
        params: [
          { name: "url", type: "string", required: true, desc: "Website URL to capture" },
          { name: "storyline", type: "string", required: false, desc: "Narrative storyline" },
          { name: "product", type: "string", required: false, desc: "Product name" },
          { name: "scenes", type: "int", required: false, desc: "Number of scenes (default: 6)" },
          { name: "tone", type: "string", required: false, desc: "Script tone" },
          { name: "style", type: "string", required: false, desc: "Video style" },
          { name: "aspect_ratio", type: "string", required: false, desc: 'Aspect ratio (default: "16:9")' },
          { name: "skip_screenshots", type: "bool", required: false, desc: "Skip website screenshots" },
          { name: "skip_imagen", type: "bool", required: false, desc: "Skip Imagen generation" },
        ],
        response: `{ "job_id": "sb-a1b2c3d4e5" }`,
        example: `curl -X POST ${BASE_URL}/storyboard \\
  -F "url=https://example.com" \\
  -F "storyline=AI transforms compliance" \\
  -F "product=My App" \\
  -F "scenes=9"`,
      },
      {
        method: "GET",
        path: "/storyboard-status/{job_id}",
        desc: "Poll storyboard generation status. When done, result includes scene data and image filenames.",
        params: [
          { name: "job_id", type: "string", required: true, desc: "Storyboard job ID" },
        ],
        response: `{
  "state": "done",
  "logs": "...",
  "error": "",
  "result": {
    "scenes": [...],
    "images": ["scene_001.png", ...],
    "sequence_files": ["001_hook_screenshot.png", ...]
  }
}`,
      },
      {
        method: "GET",
        path: "/storyboard-image/{job_id}/{filename}",
        desc: "Serve a generated storyboard image.",
        params: [
          { name: "job_id", type: "string", required: true, desc: "Storyboard job ID" },
          { name: "filename", type: "string", required: true, desc: "Image filename from storyboard result" },
        ],
        response: "image/png binary",
      },
    ],
  },
  {
    category: "Bookend Frames",
    items: [
      {
        method: "POST",
        path: "/bookends",
        desc: "Generate 3 intro and/or 3 outro frame options using Gemini + Imagen 4.0. Select one of each before creating the video.",
        params: [
          { name: "product", type: "string", required: false, desc: "Product name" },
          { name: "storyline", type: "string", required: false, desc: "Video storyline" },
          { name: "tone", type: "string", required: false, desc: "Script tone" },
          { name: "style", type: "string", required: false, desc: "Video style" },
          { name: "generate_intro", type: "bool", required: false, desc: '"true" to generate intro options' },
          { name: "generate_outro", type: "bool", required: false, desc: '"true" to generate outro options' },
          { name: "intro_prompt", type: "string", required: false, desc: "Custom prompt for intro frame" },
          { name: "outro_prompt", type: "string", required: false, desc: "Custom prompt for outro frame" },
          { name: "intro_ref", type: "File", required: false, desc: "Reference image for intro" },
          { name: "outro_ref", type: "File", required: false, desc: "Reference image for outro" },
        ],
        response: `{ "job_id": "bk-a1b2c3d4e5" }`,
        example: `curl -X POST ${BASE_URL}/bookends \\
  -F "product=My App" \\
  -F "tone=energetic" \\
  -F "generate_intro=true" \\
  -F "generate_outro=true"`,
      },
      {
        method: "GET",
        path: "/bookend-status/{job_id}",
        desc: "Poll bookend generation status. When done, result includes options with image filenames and Veo prompts.",
        params: [
          { name: "job_id", type: "string", required: true, desc: "Bookend job ID" },
        ],
        response: `{
  "state": "done",
  "error": "",
  "result": {
    "intro_options": [
      {
        "option_number": 1,
        "title_text": "My App",
        "subtitle_text": "Transform your workflow",
        "image_filename": "intro_option_1.png",
        "veo_motion_prompt": "Elegant branded intro..."
      }
    ],
    "outro_options": [...]
  }
}`,
      },
      {
        method: "GET",
        path: "/bookend-image/{job_id}/{filename}",
        desc: "Serve a generated bookend image.",
        params: [
          { name: "job_id", type: "string", required: true, desc: "Bookend job ID" },
          { name: "filename", type: "string", required: true, desc: "Image filename from bookend result" },
        ],
        response: "image/png binary",
      },
    ],
  },
  {
    category: "Voices",
    items: [
      {
        method: "GET",
        path: "/voices",
        desc: "List all available TTS voices (cloned and premade).",
        params: [],
        response: `{
  "voices": [
    { "name": "Smritika", "category": "cloned", "voice_id": "abc123" },
    { "name": "Rachel", "category": "premade", "voice_id": "def456" }
  ]
}`,
        example: `curl ${BASE_URL}/voices`,
      },
      {
        method: "POST",
        path: "/voice-clone",
        desc: "Clone a voice from audio samples. The cloned voice becomes available for TTS.",
        params: [
          { name: "audio_files", type: "File[]", required: true, desc: "Audio samples for cloning (MP3, WAV, etc.)" },
          { name: "name", type: "string", required: true, desc: "Name for the cloned voice" },
          { name: "description", type: "string", required: false, desc: "Voice description" },
          { name: "accent", type: "string", required: false, desc: 'Accent (e.g. "British", "Indian")' },
          { name: "gender", type: "string", required: false, desc: '"male" | "female"' },
          { name: "age", type: "string", required: false, desc: '"young" | "middle_aged" | "old"' },
        ],
        response: `{ "name": "Aman", "voice_id": "abc123" }`,
        example: `curl -X POST ${BASE_URL}/voice-clone \\
  -F "audio_files=@sample.mp3" \\
  -F "name=Aman" \\
  -F "accent=Indian" \\
  -F "gender=male"`,
      },
    ],
  },
  {
    category: "Post-Processing",
    items: [
      {
        method: "POST",
        path: "/post",
        desc: "Adjust video speed, voice volume, and music volume on a generated video.",
        params: [
          { name: "video", type: "File", required: true, desc: "Video file (MP4)" },
          { name: "video_speed", type: "float", required: false, desc: "Playback speed multiplier (default: 1.0)" },
          { name: "voice_volume", type: "float", required: false, desc: "Voice volume (default: 5.0)" },
          { name: "music_volume", type: "float", required: false, desc: "Music volume (default: 0.03)" },
          { name: "voice_audio", type: "File", required: false, desc: "Voice audio file (MP3)" },
          { name: "music_audio", type: "File", required: false, desc: "Music audio file (MP3)" },
        ],
        response: `{ "video": "<base64 encoded MP4>" }`,
      },
      {
        method: "POST",
        path: "/avatar",
        desc: "Overlay an avatar (image or video) on top of a video.",
        params: [
          { name: "video", type: "File", required: true, desc: "Video file (MP4)" },
          { name: "avatar", type: "File", required: true, desc: "Avatar image (PNG/JPG) or video (MP4)" },
          { name: "position", type: "string", required: false, desc: '"top-left" | "top-right" | "bottom-left" | "bottom-right"' },
          { name: "scale", type: "float", required: false, desc: "Avatar size as fraction of video width (default: 0.15)" },
          { name: "opacity", type: "float", required: false, desc: "Avatar opacity 0.0-1.0 (default: 1.0, images only)" },
        ],
        response: `{ "video": "<base64 encoded MP4>" }`,
        example: `curl -X POST ${BASE_URL}/avatar \\
  -F "video=@video.mp4" \\
  -F "avatar=@avatar.png" \\
  -F "position=bottom-right" \\
  -F "scale=0.15"`,
      },
    ],
  },
  {
    category: "Samples",
    items: [
      {
        method: "GET",
        path: "/sample/{style}",
        desc: "Stream a sample video for a given style.",
        params: [
          { name: "style", type: "string", required: true, desc: '"marketing" | "feature-explainer" | "tutorial-explainer"' },
        ],
        response: "video/mp4 stream",
      },
      {
        method: "HEAD",
        path: "/sample/{style}",
        desc: "Check if a sample video exists without downloading.",
        params: [
          { name: "style", type: "string", required: true, desc: "Style name" },
        ],
        response: "200 with Content-Length header, or 404",
      },
      {
        method: "POST",
        path: "/upload-sample",
        desc: "Upload a sample video for a style.",
        params: [
          { name: "style", type: "string", required: true, desc: '"marketing" | "feature-explainer" | "tutorial-explainer"' },
          { name: "video", type: "File", required: true, desc: "Sample video (MP4)" },
        ],
        response: `{ "success": true, "style": "marketing" }`,
      },
    ],
  },
];

const methodColors: Record<string, string> = {
  GET: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  POST: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  HEAD: "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
};

export default function DocsPage() {
  return (
    <main className="min-h-screen bg-[#0c0c0c]">
      {/* Nav */}
      <nav className="flex items-center justify-between px-8 py-6 max-w-7xl mx-auto border-b border-[#3d3428]">
        <Link href="/" className="flex items-center gap-3">
          <img src="/logo.png" alt="Transilience" className="h-7 w-auto" />
          <span className="text-lg font-semibold text-[#f5f2ea]">Transilience</span>
          <span className="text-[#333]">|</span>
          <span className="text-lg font-bold bg-gradient-to-r from-[#f5da6a] to-[#d4b44e] bg-clip-text text-transparent">
            VideoGen
          </span>
        </Link>
        <Link
          href="/dashboard"
          className="px-4 py-2 text-sm rounded-full bg-gradient-to-r from-[#f5da6a] to-[#c9a84c] text-[#0a0a0a] font-medium hover:opacity-90 transition"
        >
          Dashboard
        </Link>
      </nav>

      <div className="max-w-5xl mx-auto px-6 py-12">
        {/* Header */}
        <div className="mb-12">
          <h1 className="text-4xl font-bold mb-3 text-[#f5f2ea]">API Reference</h1>
          <p className="text-[#a09888] text-lg mb-4">
            VideoGen REST API for programmatic video generation, storyboarding, voice cloning, and post-processing.
          </p>
          <div className="flex items-center gap-3">
            <span className="text-xs text-[#7a7060]">Base URL</span>
            <code className="px-3 py-1.5 rounded-lg bg-[#141210] border border-[#3d3428] text-sm text-[#d4b44e] font-mono">
              {BASE_URL}
            </code>
          </div>
        </div>

        {/* Quick Nav */}
        <div className="bg-[#141210] border border-[#3d3428] rounded-xl p-6 mb-12">
          <h2 className="text-sm font-semibold text-[#a09888] uppercase tracking-wider mb-4">Endpoints</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {endpoints.map((cat) =>
              cat.items.map((ep) => (
                <a
                  key={`${ep.method}-${ep.path}`}
                  href={`#${ep.method.toLowerCase()}-${ep.path.replace(/[/{}/]/g, "-")}`}
                  className="flex items-center gap-2 text-sm text-[#a09888] hover:text-[#f5f2ea] transition py-1"
                >
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold border ${methodColors[ep.method]}`}>
                    {ep.method}
                  </span>
                  <span className="font-mono text-xs">{ep.path}</span>
                </a>
              ))
            )}
          </div>
        </div>

        {/* Typical Workflow */}
        <div className="bg-[#141210] border border-[#3d3428] rounded-xl p-6 mb-12">
          <h2 className="text-lg font-semibold mb-4 text-[#f5f2ea]">Typical Workflow</h2>
          <div className="space-y-3 text-sm text-[#a09888]">
            <div className="flex gap-3">
              <span className="text-[#d4b44e] font-mono w-6 shrink-0">1.</span>
              <span><code className="text-blue-400">POST /create</code> with files and options — returns <code className="text-[#f5f2ea]">job_id</code></span>
            </div>
            <div className="flex gap-3">
              <span className="text-[#d4b44e] font-mono w-6 shrink-0">2.</span>
              <span><code className="text-emerald-400">GET /status/&#123;job_id&#125;</code> — poll every 3s until <code className="text-[#f5f2ea]">state: &quot;done&quot;</code></span>
            </div>
            <div className="flex gap-3">
              <span className="text-[#d4b44e] font-mono w-6 shrink-0">3.</span>
              <span><code className="text-emerald-400">GET /download/&#123;job_id&#125;/video</code> — stream the MP4</span>
            </div>
          </div>
          <div className="mt-4 pt-4 border-t border-[#3d3428] text-sm text-[#7a7060]">
            Optional: Use <code className="text-[#a09888]">/bookends</code> before <code className="text-[#a09888]">/create</code> for branded intro/outro frames.
            Use <code className="text-[#a09888]">/storyboard</code> to generate visuals from a URL first.
          </div>
        </div>

        {/* Endpoints */}
        {endpoints.map((cat) => (
          <div key={cat.category} className="mb-16">
            <h2 className="text-2xl font-bold mb-6 pb-3 border-b border-[#3d3428] text-[#f5f2ea]">{cat.category}</h2>

            {cat.items.map((ep) => (
              <div
                key={`${ep.method}-${ep.path}`}
                id={`${ep.method.toLowerCase()}-${ep.path.replace(/[/{}/]/g, "-")}`}
                className="mb-10 scroll-mt-8"
              >
                {/* Method + Path */}
                <div className="flex items-center gap-3 mb-3">
                  <span className={`px-2 py-1 rounded text-xs font-bold border ${methodColors[ep.method]}`}>
                    {ep.method}
                  </span>
                  <code className="text-lg font-mono text-[#f5f2ea]">{ep.path}</code>
                </div>

                <p className="text-sm text-[#a09888] mb-4">{ep.desc}</p>

                {/* Parameters */}
                {ep.params.length > 0 && (
                  <div className="mb-4">
                    <h4 className="text-xs text-[#7a7060] uppercase tracking-wider font-semibold mb-2">
                      Parameters {ep.method === "POST" ? "(multipart/form-data)" : "(path)"}
                    </h4>
                    <div className="bg-[#141210] border border-[#3d3428] rounded-lg overflow-hidden">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-[#3d3428] text-left">
                            <th className="px-4 py-2 text-xs text-[#7a7060] font-medium">Name</th>
                            <th className="px-4 py-2 text-xs text-[#7a7060] font-medium">Type</th>
                            <th className="px-4 py-2 text-xs text-[#7a7060] font-medium">Required</th>
                            <th className="px-4 py-2 text-xs text-[#7a7060] font-medium">Description</th>
                          </tr>
                        </thead>
                        <tbody>
                          {ep.params.map((p) => (
                            <tr key={p.name} className="border-b border-[#0a0908]">
                              <td className="px-4 py-2 font-mono text-[#d4b44e] text-xs">{p.name}</td>
                              <td className="px-4 py-2 text-[#a09888] text-xs">{p.type}</td>
                              <td className="px-4 py-2">
                                {p.required ? (
                                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/10 text-red-400 border border-red-500/20">required</span>
                                ) : (
                                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#1a1814] text-[#7a7060]">optional</span>
                                )}
                              </td>
                              <td className="px-4 py-2 text-[#a09888] text-xs">{p.desc}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* Response */}
                <div className="mb-4">
                  <h4 className="text-xs text-[#7a7060] uppercase tracking-wider font-semibold mb-2">Response</h4>
                  <pre className="bg-[#141210] border border-[#3d3428] rounded-lg p-4 text-xs text-[#f5f2ea] font-mono overflow-x-auto whitespace-pre-wrap">
                    {ep.response}
                  </pre>
                </div>

                {/* Example */}
                {ep.example && (
                  <div>
                    <h4 className="text-xs text-[#7a7060] uppercase tracking-wider font-semibold mb-2">Example</h4>
                    <pre className="bg-[#141210] border border-[#3d3428] rounded-lg p-4 text-xs text-emerald-300 font-mono overflow-x-auto whitespace-pre-wrap">
                      {ep.example}
                    </pre>
                  </div>
                )}
              </div>
            ))}
          </div>
        ))}

        {/* Rate Limits & Notes */}
        <div className="bg-[#141210] border border-[#3d3428] rounded-xl p-6 mb-12">
          <h2 className="text-lg font-semibold mb-4 text-[#f5f2ea]">Notes</h2>
          <ul className="space-y-2 text-sm text-[#a09888]">
            <li className="flex gap-2">
              <span className="text-[#d4b44e]">-</span>
              All POST endpoints use <code className="text-[#f5f2ea]">multipart/form-data</code> (not JSON)
            </li>
            <li className="flex gap-2">
              <span className="text-[#d4b44e]">-</span>
              Video generation is async — POST returns immediately with a job_id, poll /status for progress
            </li>
            <li className="flex gap-2">
              <span className="text-[#d4b44e]">-</span>
              Jobs timeout after 30 minutes. Typical generation takes 8-16 minutes for 10 scenes.
            </li>
            <li className="flex gap-2">
              <span className="text-[#d4b44e]">-</span>
              Generated files are stored temporarily and may be cleaned up after 24 hours
            </li>
            <li className="flex gap-2">
              <span className="text-[#d4b44e]">-</span>
              CORS is enabled for all origins. No authentication required (Clerk auth is frontend-only).
            </li>
            <li className="flex gap-2">
              <span className="text-[#d4b44e]">-</span>
              Cost per video: ~$0.25-0.65 (Gemini Vision + Veo 3.1 + TTS + Music)
            </li>
          </ul>
        </div>

        {/* Footer */}
        <div className="text-center text-xs text-[#5a5040] py-8 border-t border-[#3d3428]">
          Transilience | VideoGen API
        </div>
      </div>
    </main>
  );
}
