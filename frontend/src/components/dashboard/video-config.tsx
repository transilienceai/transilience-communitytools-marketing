"use client";

import { RESOLUTIONS } from "@/lib/constants";
import { analyzeContent } from "@/lib/api";
import { useRef, useState } from "react";

interface Props {
  product: string;
  onProductChange: (v: string) => void;
  tone: string;
  onToneChange: (v: string) => void;
  resolution: string;
  onResolutionChange: (v: string) => void;
  scriptDuration: number;
  onScriptDurationChange: (v: number) => void;
  storyline: string;
  onStorylineChange: (v: string) => void;
  generateMusic: boolean;
  onGenerateMusicChange: (v: boolean) => void;
  musicPrompt: string;
  onMusicPromptChange: (v: string) => void;
  generateIntro: boolean;
  onGenerateIntroChange: (v: boolean) => void;
  generateOutro: boolean;
  onGenerateOutroChange: (v: boolean) => void;
  maxWorkers: number;
  onMaxWorkersChange: (v: number) => void;
  files: File[];
  style: string;
}

export default function VideoConfig(props: Props) {
  const storyFileRef = useRef<HTMLInputElement>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeVideos, setAnalyzeVideos] = useState(true);
  const [analyzeStatus, setAnalyzeStatus] = useState("");

  const hasVideos = props.files.some((f) => f.type.startsWith("video/"));

  /** Extract 1 frame every 3 seconds from a video file */
  const extractFrames = (file: File, intervalSec = 3): Promise<File[]> => {
    return new Promise((resolve) => {
      const video = document.createElement("video");
      video.muted = true;
      video.preload = "auto";
      const url = URL.createObjectURL(file);
      video.src = url;

      video.onloadedmetadata = () => {
        const canvas = document.createElement("canvas");
        const ctx = canvas.getContext("2d")!;
        canvas.width = Math.min(video.videoWidth, 1280);
        canvas.height = Math.round(canvas.width * (video.videoHeight / video.videoWidth));

        const frames: File[] = [];
        const dur = Number.isFinite(video.duration) ? video.duration : 0;
        const times: number[] = [];
        for (let t = 0; t < dur; t += intervalSec) {
          times.push(t);
        }
        if (times.length === 0) times.push(0);
        // Limit to 10 frames max
        const selectedTimes = times.slice(0, 10);
        let idx = 0;

        const captureNext = () => {
          if (idx >= selectedTimes.length) {
            URL.revokeObjectURL(url);
            resolve(frames);
            return;
          }
          video.currentTime = selectedTimes[idx];
        };

        video.onseeked = () => {
          ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
          canvas.toBlob((blob) => {
            if (blob) {
              const name = file.name.replace(/\.[^.]+$/, `_frame_${Math.floor(selectedTimes[idx])}s.png`);
              frames.push(new File([blob], name, { type: "image/png" }));
            }
            idx++;
            captureNext();
          }, "image/png");
        };

        captureNext();
      };

      video.onerror = () => {
        URL.revokeObjectURL(url);
        resolve([]);
      };
    });
  };

  const handleAutoFill = async () => {
    if (props.files.length === 0) return;
    setAnalyzing(true);
    setAnalyzeStatus("");
    try {
      const imageFiles = props.files.filter((f) => f.type.startsWith("image/"));
      const videoFiles = props.files.filter((f) => f.type.startsWith("video/"));

      let allFiles = [...imageFiles];

      if (analyzeVideos && videoFiles.length > 0) {
        setAnalyzeStatus(`Extracting frames from ${videoFiles.length} video(s)...`);
        for (const vf of videoFiles) {
          const frames = await extractFrames(vf);
          allFiles.push(...frames);
        }
      }

      if (allFiles.length === 0) {
        alert("No images or video frames to analyze.");
        return;
      }

      setAnalyzeStatus("Analyzing content...");
      const suggestions = await analyzeContent(allFiles, props.style);
      if (suggestions.product_name) props.onProductChange(suggestions.product_name);
      if (suggestions.tone) props.onToneChange(suggestions.tone);
      if (suggestions.storyline) props.onStorylineChange(suggestions.storyline);
      if (suggestions.script_duration) props.onScriptDurationChange(suggestions.script_duration);
      if (suggestions.music_prompt) {
        const musicPrompt = suggestions.music_prompt.replace(/,?\s*(no voice|no vocals).*$/i, "");
        props.onMusicPromptChange(`${musicPrompt}, no voice, ASMR sound only`);
        if (!props.generateMusic) props.onGenerateMusicChange(true);
      }
    } catch (err) {
      alert(String(err));
    } finally {
      setAnalyzing(false);
      setAnalyzeStatus("");
    }
  };

  const handleStorylineFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      props.onStorylineChange(ev.target?.result as string);
    };
    reader.readAsText(file);
  };

  const sceneCount = Math.ceil(props.scriptDuration / 5);

  return (
    <div className="space-y-4">
      {/* AI Auto-Fill */}
      {props.files.length > 0 && (
        <div className="flex items-center gap-4">
          <button
            onClick={handleAutoFill}
            disabled={analyzing}
            className="flex items-center gap-2 px-4 py-2 rounded-lg border border-[#d4b44e]/40 text-sm text-[#d4b44e] hover:bg-[#d4b44e]/10 disabled:opacity-40 transition"
          >
            <svg className={`w-4 h-4 ${analyzing ? "animate-spin" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
            {analyzing ? "Analyzing content..." : "AI Auto-Fill from content"}
          </button>
          {hasVideos && (
            <label className="flex items-center gap-2 text-xs text-[#a09888]">
              <input
                type="checkbox"
                checked={analyzeVideos}
                onChange={(e) => setAnalyzeVideos(e.target.checked)}
                className="accent-[#d4b44e]"
              />
              Analyze videos (1 frame/3s)
            </label>
          )}
          {analyzeStatus && (
            <span className="text-xs text-[#7a7060]">{analyzeStatus}</span>
          )}
        </div>
      )}

      {/* Row 1: Product + Tone + Resolution + Duration + Speed */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <Field label="Product Name" required>
          <input
            value={props.product}
            onChange={(e) => props.onProductChange(e.target.value)}
            placeholder="My SaaS App"
            className="input-field w-full"
          />
        </Field>
        <Field label="Tone">
          <input
            value={props.tone}
            onChange={(e) => props.onToneChange(e.target.value)}
            placeholder="professional and engaging"
            className="input-field w-full"
          />
        </Field>
        <Field label="Resolution">
          <select
            value={props.resolution}
            onChange={(e) => props.onResolutionChange(e.target.value)}
            className="input-field w-full"
          >
            {RESOLUTIONS.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </Field>
        <Field label={`Duration — ${sceneCount} scenes ~ ${sceneCount * 5}s`}>
          <input
            type="number"
            value={props.scriptDuration}
            onChange={(e) => props.onScriptDurationChange(Number(e.target.value))}
            min={10}
            max={300}
            className="input-field w-full"
          />
        </Field>
        <Field label={`Speed — ${props.maxWorkers} parallel`}>
          <input
            type="range"
            min={1}
            max={10}
            step={1}
            value={props.maxWorkers}
            onChange={(e) => props.onMaxWorkersChange(Number(e.target.value))}
            className="w-full mt-2 accent-[#d4b44e]"
          />
          <div className="flex justify-between text-xs text-[#7a7060] mt-1">
            <span>Slow</span>
            <span>Fast</span>
          </div>
        </Field>
      </div>

      {/* Storyline */}
      <Field label="Storyline">
        <div className="flex gap-2">
          <textarea
            value={props.storyline}
            onChange={(e) => props.onStorylineChange(e.target.value)}
            placeholder="A small team discovers AI automation and scales to 10x productivity..."
            rows={3}
            className="input-field flex-1 resize-none"
          />
          <button
            onClick={() => storyFileRef.current?.click()}
            className="self-start px-2 py-2 rounded border border-[#3d3428] text-[#a09888] hover:text-[#f5f2ea] hover:border-[#d4b44e] text-xs transition"
            title="Upload .txt/.md storyline file"
          >
            +
          </button>
          <input
            ref={storyFileRef}
            type="file"
            accept=".txt,.md"
            className="hidden"
            onChange={handleStorylineFile}
          />
        </div>
      </Field>

      {/* Toggles */}
      <div className="flex flex-wrap gap-6">
        <Toggle
          label="Generate Music"
          checked={props.generateMusic}
          onChange={props.onGenerateMusicChange}
        />
        <Toggle
          label="Intro Frame"
          checked={props.generateIntro}
          onChange={props.onGenerateIntroChange}
        />
        <Toggle
          label="Outro Frame"
          checked={props.generateOutro}
          onChange={props.onGenerateOutroChange}
        />
      </div>

      {/* Music prompt */}
      {props.generateMusic && (
        <Field label="Music Prompt">
          <input
            value={props.musicPrompt}
            onChange={(e) => props.onMusicPromptChange(e.target.value)}
            placeholder="upbeat corporate, no voice, ASMR sound only"
            className="input-field"
          />
        </Field>
      )}
    </div>
  );
}

function Field({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-xs text-[#a09888] mb-1">
        {label} {required && <span className="text-[#d4b44e]">*</span>}
      </label>
      {children}
    </div>
  );
}

function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-2 text-sm text-[#f5f2ea] cursor-pointer">
      <div
        onClick={() => onChange(!checked)}
        className={`w-9 h-5 rounded-full transition relative ${
          checked ? "bg-[#d4b44e]" : "bg-[#2a2418]"
        }`}
      >
        <div
          className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
            checked ? "translate-x-4" : "translate-x-0.5"
          }`}
        />
      </div>
      {label}
    </label>
  );
}
