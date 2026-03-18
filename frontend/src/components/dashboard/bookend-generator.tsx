"use client";

import { useCallback, useRef, useState } from "react";
import {
  analyzeContent,
  bookendImageUrl,
  createBookends,
  getBookendStatus,
} from "@/lib/api";
import { usePolling } from "@/hooks/use-polling";
import type { BookendOption } from "@/lib/types";

interface Props {
  product: string;
  storyline: string;
  tone: string;
  style: string;
  generateIntro: boolean;
  generateOutro: boolean;
  files: File[];
  onBookendReady: (
    jobId: string,
    introOption: number,
    outroOption: number,
    introVeoPrompt: string,
    outroVeoPrompt: string
  ) => void;
}

export default function BookendGenerator({
  product,
  storyline,
  tone,
  style,
  generateIntro,
  generateOutro,
  files,
  onBookendReady,
}: Props) {
  const [jobId, setJobId] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [introPrompt, setIntroPrompt] = useState("");
  const [outroPrompt, setOutroPrompt] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [introRef, setIntroRef] = useState<File | null>(null);
  const [outroRef, setOutroRef] = useState<File | null>(null);
  const introFileRef = useRef<HTMLInputElement>(null);
  const outroFileRef = useRef<HTMLInputElement>(null);

  const [introOptions, setIntroOptions] = useState<BookendOption[]>([]);
  const [outroOptions, setOutroOptions] = useState<BookendOption[]>([]);
  const [selectedIntro, setSelectedIntro] = useState(0);
  const [selectedOutro, setSelectedOutro] = useState(0);
  const [analyzeVideos, setAnalyzeVideos] = useState(true);
  const [frameStatus, setFrameStatus] = useState("");

  const hasVideos = files.some((f) => f.type.startsWith("video/"));

  /** Extract 1 frame every 3 seconds from a video file (max 10 frames) */
  const extractFrames = (file: File, intervalSec = 3): Promise<File[]> => {
    return new Promise((resolve) => {
      const video = document.createElement("video");
      video.muted = true;
      video.preload = "auto";
      const blobUrl = URL.createObjectURL(file);
      video.src = blobUrl;

      video.onloadedmetadata = () => {
        const canvas = document.createElement("canvas");
        const ctx = canvas.getContext("2d")!;
        canvas.width = Math.min(video.videoWidth, 1280);
        canvas.height = Math.round(canvas.width * (video.videoHeight / video.videoWidth));

        const frames: File[] = [];
        const dur = Number.isFinite(video.duration) ? video.duration : 0;
        const times: number[] = [];
        for (let t = 0; t < dur; t += intervalSec) times.push(t);
        if (times.length === 0) times.push(0);
        const selectedTimes = times.slice(0, 10);
        let idx = 0;

        const captureNext = () => {
          if (idx >= selectedTimes.length) {
            URL.revokeObjectURL(blobUrl);
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
        URL.revokeObjectURL(blobUrl);
        resolve([]);
      };
    });
  };

  const fetcher = useCallback(
    () => (jobId ? getBookendStatus(jobId) : Promise.reject()),
    [jobId]
  );

  usePolling(jobId ? fetcher : null, 3000, {
    onDone: (d) => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const result = (d as any).result;
      if (result?.intro_options) setIntroOptions(result.intro_options);
      if (result?.outro_options) setOutroOptions(result.outro_options);
      setGenerating(false);
    },
    onError: () => setGenerating(false),
  });

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const form = new FormData();
      form.append("product", product);
      form.append("storyline", storyline);
      form.append("tone", tone);
      form.append("style", style);
      form.append("generate_intro", String(generateIntro));
      form.append("generate_outro", String(generateOutro));
      if (introPrompt) form.append("intro_prompt", introPrompt);
      if (outroPrompt) form.append("outro_prompt", outroPrompt);
      if (introRef) form.append("intro_ref", introRef);
      if (outroRef) form.append("outro_ref", outroRef);

      const id = await createBookends(form);
      setJobId(id);
    } catch (err) {
      alert(String(err));
      setGenerating(false);
    }
  };

  const handleConfirm = () => {
    if (!jobId) return;
    const introVeo = introOptions[selectedIntro]?.veo_motion_prompt ?? "";
    const outroVeo = outroOptions[selectedOutro]?.veo_motion_prompt ?? "";
    onBookendReady(jobId, selectedIntro, selectedOutro, introVeo, outroVeo);
  };

  const hasResults = introOptions.length > 0 || outroOptions.length > 0;

  const handleAutoFill = async () => {
    if (files.length === 0) return;
    setAnalyzing(true);
    setFrameStatus("");
    try {
      const imageFiles = files.filter((f) => f.type.startsWith("image/"));
      const videoFiles = files.filter((f) => f.type.startsWith("video/"));

      let allFiles = [...imageFiles];

      if (analyzeVideos && videoFiles.length > 0) {
        setFrameStatus(`Extracting frames from ${videoFiles.length} video(s)...`);
        for (const vf of videoFiles) {
          const frames = await extractFrames(vf);
          allFiles.push(...frames);
        }
      }

      if (allFiles.length === 0) {
        alert("No images or video frames to analyze.");
        return;
      }

      setFrameStatus("Analyzing content...");
      const suggestions = await analyzeContent(allFiles, style);
      if (suggestions.intro_prompt && generateIntro) setIntroPrompt(suggestions.intro_prompt);
      if (suggestions.outro_prompt && generateOutro) setOutroPrompt(suggestions.outro_prompt);
    } catch (err) {
      alert(String(err));
    } finally {
      setAnalyzing(false);
      setFrameStatus("");
    }
  };

  return (
    <div className="space-y-4">
      {/* AI Auto-Fill */}
      {files.length > 0 && (
        <div className="flex items-center gap-4">
          <button
            onClick={handleAutoFill}
            disabled={analyzing}
            className="flex items-center gap-2 px-4 py-2 rounded-lg border border-[#d4b44e]/40 text-sm text-[#d4b44e] hover:bg-[#d4b44e]/10 disabled:opacity-40 transition"
          >
            <svg className={`w-4 h-4 ${analyzing ? "animate-spin" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
            {analyzing ? "Analyzing..." : "AI Suggest Prompts"}
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
          {frameStatus && (
            <span className="text-xs text-[#7a7060]">{frameStatus}</span>
          )}
        </div>
      )}

      {/* Prompts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {generateIntro && (
          <div className="space-y-2">
            <label className="text-xs text-[#a09888]">Intro Prompt (optional)</label>
            <input
              value={introPrompt}
              onChange={(e) => setIntroPrompt(e.target.value)}
              placeholder="Clean gradient with logo..."
              className="input-field"
            />
            <div>
              <button
                onClick={() => introFileRef.current?.click()}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-dashed border-[#3d3428] text-xs text-[#a09888] hover:border-[#d4b44e] hover:text-[#f5f2ea] transition"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                {introRef ? introRef.name : "Upload reference image"}
              </button>
              <input
                ref={introFileRef}
                type="file"
                accept="image/*"
                onChange={(e) => setIntroRef(e.target.files?.[0] ?? null)}
                className="hidden"
              />
            </div>
          </div>
        )}
        {generateOutro && (
          <div className="space-y-2">
            <label className="text-xs text-[#a09888]">Outro Prompt (optional)</label>
            <input
              value={outroPrompt}
              onChange={(e) => setOutroPrompt(e.target.value)}
              placeholder="CTA with warm tones..."
              className="input-field"
            />
            <div>
              <button
                onClick={() => outroFileRef.current?.click()}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-dashed border-[#3d3428] text-xs text-[#a09888] hover:border-[#d4b44e] hover:text-[#f5f2ea] transition"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                {outroRef ? outroRef.name : "Upload reference image"}
              </button>
              <input
                ref={outroFileRef}
                type="file"
                accept="image/*"
                onChange={(e) => setOutroRef(e.target.files?.[0] ?? null)}
                className="hidden"
              />
            </div>
          </div>
        )}
      </div>

      <button
        onClick={handleGenerate}
        disabled={generating}
        className="px-4 py-2 rounded-lg bg-gradient-to-r from-[#f5da6a] to-[#c9a84c] text-[#0a0a0a] text-sm font-medium disabled:opacity-40 hover:opacity-90 transition"
      >
        {generating ? "Generating Frames..." : "Generate Frame Options"}
      </button>

      {/* Intro Gallery */}
      {introOptions.length > 0 && jobId && (
        <OptionGallery
          title="Intro Options"
          options={introOptions}
          jobId={jobId}
          selected={selectedIntro}
          onSelect={setSelectedIntro}
        />
      )}

      {/* Outro Gallery */}
      {outroOptions.length > 0 && jobId && (
        <OptionGallery
          title="Outro Options"
          options={outroOptions}
          jobId={jobId}
          selected={selectedOutro}
          onSelect={setSelectedOutro}
        />
      )}

      {hasResults && (
        <button
          onClick={handleConfirm}
          className="px-4 py-2 rounded-lg border border-[#d4b44e] text-[#d4b44e] text-sm font-medium hover:bg-[#d4b44e]/10 transition"
        >
          Confirm Selection
        </button>
      )}
    </div>
  );
}

function OptionGallery({
  title,
  options,
  jobId,
  selected,
  onSelect,
}: {
  title: string;
  options: BookendOption[];
  jobId: string;
  selected: number;
  onSelect: (i: number) => void;
}) {
  return (
    <div>
      <p className="text-sm text-[#f5f2ea] mb-2">{title}</p>
      <div className="grid grid-cols-3 gap-3">
        {options.map((opt, i) => (
          <div
            key={i}
            onClick={() => onSelect(i)}
            className={`cursor-pointer rounded-lg border overflow-hidden transition ${
              selected === i
                ? "border-[#d4b44e] ring-1 ring-[#d4b44e]"
                : "border-[#3d3428] hover:border-[#d4b44e]/40"
            }`}
          >
            <img
              src={bookendImageUrl(jobId, opt.image_filename)}
              alt={opt.title_text}
              className="w-full aspect-video object-cover"
            />
            <div className="p-2">
              <p className="text-xs font-medium truncate text-[#f5f2ea]">{opt.title_text}</p>
              <p className="text-xs text-[#7a7060] truncate">
                {opt.subtitle_text}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
