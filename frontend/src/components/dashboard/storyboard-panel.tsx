"use client";

import { useCallback, useState } from "react";
import {
  createStoryboard,
  getStoryboardStatus,
  storyboardImageUrl,
} from "@/lib/api";
import { usePolling } from "@/hooks/use-polling";
import type { JobStatus } from "@/lib/types";

interface Props {
  product: string;
  storyline: string;
  tone: string;
  style: string;
  hasFiles: boolean;
  files: File[];
  onStoryboardReady: (jobId: string) => void;
}

export default function StoryboardPanel({
  product,
  storyline,
  tone,
  style,
  hasFiles,
  files,
  onStoryboardReady,
}: Props) {
  const [url, setUrl] = useState("");
  const [scenes, setScenes] = useState(6);
  const [source, setSource] = useState<"both" | "screenshots" | "imagen">("both");
  const [jobId, setJobId] = useState<string | null>(null);
  const [images, setImages] = useState<string[]>([]);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewImage, setPreviewImage] = useState<string | null>(null);
  const [showImages, setShowImages] = useState(true);
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
    () => (jobId ? getStoryboardStatus(jobId) : Promise.reject()),
    [jobId]
  );

  const { data, isPolling } = usePolling<JobStatus>(
    jobId ? fetcher : null,
    3000,
    {
      onDone: (d) => {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const result = d.result as any;
        const files: string[] = result?.sequence_files ?? result?.images ?? [];
        setImages(files);
        if (jobId) onStoryboardReady(jobId);
        setGenerating(false);
      },
      onError: (err) => {
        const msg = String(err);
        if (msg.includes("ERR_CONNECTION_REFUSED"))
          setError("Could not connect to the website. Make sure the URL is publicly accessible.");
        else if (msg.includes("ERR_NAME_NOT_RESOLVED"))
          setError("Website not found. Please check the URL and try again.");
        else if (msg.includes("timeout") || msg.includes("TIMEOUT"))
          setError("Website took too long to respond. Please try again.");
        else
          setError(msg);
        setGenerating(false);
      },
    }
  );

  const validateUrl = (input: string): string | null => {
    if (!input.trim()) return "Please enter a website URL.";
    try {
      const parsed = new URL(input);
      if (!["http:", "https:"].includes(parsed.protocol))
        return "URL must start with http:// or https://";
      if (["localhost", "127.0.0.1", "0.0.0.0"].includes(parsed.hostname))
        return "Cannot crawl localhost. Please enter a publicly accessible URL.";
      if (!parsed.hostname.includes("."))
        return "Please enter a valid domain (e.g. https://example.com).";
      return null;
    } catch {
      return "Invalid URL format. Example: https://example.com";
    }
  };

  const handleGenerate = async () => {
    if (url) {
      const urlError = validateUrl(url);
      if (urlError) {
        setError(urlError);
        return;
      }
    } else if (!hasFiles) {
      setError("Please enter a website URL or upload images.");
      return;
    }
    setError(null);
    setGenerating(true);
    try {
      const form = new FormData();
      if (url) form.append("url", url);
      form.append("storyline", storyline);
      form.append("product", product);
      form.append("scenes", String(scenes));
      form.append("tone", tone);
      form.append("style", style);
      if (source === "screenshots") form.append("skip_imagen", "true");
      if (source === "imagen") form.append("skip_screenshots", "true");
      if (!url && files.length > 0) {
        const imageFiles = files.filter((f) => f.type.startsWith("image/"));
        imageFiles.forEach((f) => form.append("files", f));

        if (analyzeVideos) {
          const videoFiles = files.filter((f) => f.type.startsWith("video/"));
          if (videoFiles.length > 0) {
            setFrameStatus(`Extracting frames from ${videoFiles.length} video(s)...`);
            for (const vf of videoFiles) {
              const frames = await extractFrames(vf);
              frames.forEach((f) => form.append("files", f));
            }
            setFrameStatus("");
          }
        }
      }
      const id = await createStoryboard(form);
      setJobId(id);
    } catch (err) {
      const msg = String(err);
      if (msg.includes("ERR_CONNECTION_REFUSED"))
        setError("Could not connect to the website. Make sure the URL is publicly accessible.");
      else if (msg.includes("ERR_NAME_NOT_RESOLVED"))
        setError("Website not found. Please check the URL and try again.");
      else if (msg.includes("TIMEOUT") || msg.includes("timeout"))
        setError("Website took too long to respond. Please try again.");
      else
        setError(msg);
      setGenerating(false);
    }
  };

  return (
    <div className="border border-[#3d3428] rounded-lg p-4 space-y-4">
      <p className="text-xs text-[#a09888] font-medium">
        {hasFiles ? "Generate storyboard from uploaded images or a website URL" : "Or generate from a website URL"}
      </p>

      <div className="grid grid-cols-4 gap-4">
        {/* Website URL */}
        <div className="col-span-2">
          <label className="block text-xs text-[#7a7060] mb-1">Website URL {!hasFiles && <span className="text-[#d4b44e]">*</span>}</label>
          <input
            value={url}
            onChange={(e) => {
              setUrl(e.target.value);
              setError(null);
            }}
            placeholder="https://example.com"
            className={`input-field w-full ${error ? "border-red-400" : ""}`}
          />
        </div>

        {/* Scenes */}
        <div>
          <label className="block text-xs text-[#7a7060] mb-1">Scenes <span className="text-[#d4b44e]">*</span></label>
          <input
            type="number"
            value={scenes}
            onChange={(e) => setScenes(Number(e.target.value))}
            min={3}
            max={15}
            className="input-field w-full"
          />
          <p className="text-xs text-[#7a7060] mt-1">{scenes} scenes ~ {scenes * 5}s video</p>
        </div>

        {/* Source */}
        <div>
          <label className="block text-xs text-[#7a7060] mb-1">Source</label>
          <select
            value={source}
            onChange={(e) => setSource(e.target.value as "both" | "screenshots" | "imagen")}
            className="input-field w-full"
          >
            <option value="both">Screenshots + Imagen</option>
            <option value="screenshots">Screenshots Only</option>
            <option value="imagen">Imagen Only</option>
          </select>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <button
          onClick={handleGenerate}
          disabled={(!url && !hasFiles) || generating}
          className="px-4 py-2 rounded-lg bg-gradient-to-r from-[#f5da6a] to-[#c9a84c] text-[#0a0a0a] text-sm font-medium disabled:opacity-40 hover:opacity-90 transition whitespace-nowrap"
        >
          {generating ? "Generating..." : "Generate Storyboard"}
        </button>
        {hasVideos && !url && (
          <label className="flex items-center gap-2 text-xs text-[#a09888]">
            <input
              type="checkbox"
              checked={analyzeVideos}
              onChange={(e) => setAnalyzeVideos(e.target.checked)}
              className="accent-[#d4b44e]"
            />
            Include video frames (1 frame/3s)
          </label>
        )}
        {frameStatus && (
          <span className="text-xs text-[#7a7060]">{frameStatus}</span>
        )}
      </div>

      {error && (
        <div className="flex items-center gap-2 text-sm text-red-400 bg-red-500/5 border border-red-500/20 rounded-lg px-3 py-2">
          <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
          </svg>
          {error}
        </div>
      )}

      {isPolling && data && (
        <p className="text-xs text-[#7a7060]">
          {data.state === "running" ? "Crawling & generating..." : data.state}
        </p>
      )}

      {images.length > 0 && jobId && (
        <div>
          <button
            onClick={() => setShowImages(!showImages)}
            className="flex items-center gap-1.5 text-xs text-[#a09888] hover:text-[#f5f2ea] transition mb-2"
          >
            <svg
              className={`w-3.5 h-3.5 transition-transform ${showImages ? "rotate-180" : ""}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
            {showImages ? "Hide" : "Show"} {images.length} storyboard images
          </button>
        </div>
      )}

      {images.length > 0 && jobId && showImages && (
        <div className="grid grid-cols-3 md:grid-cols-6 gap-2 mt-2">
          {images.map((filename) => (
            <img
              key={filename}
              src={storyboardImageUrl(jobId, filename)}
              alt={filename}
              onClick={() => setPreviewImage(storyboardImageUrl(jobId, filename))}
              className="rounded border border-[#3d3428] w-full aspect-video object-cover cursor-pointer hover:border-[#d4b44e] transition"
            />
          ))}
        </div>
      )}

      {/* Image Preview Modal */}
      {previewImage && (
        <div
          onClick={() => setPreviewImage(null)}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm cursor-pointer"
        >
          <div className="relative max-w-4xl max-h-[85vh] p-2">
            <img
              src={previewImage}
              alt="Preview"
              className="max-w-full max-h-[85vh] rounded-lg object-contain"
            />
            <button
              onClick={() => setPreviewImage(null)}
              className="absolute top-4 right-4 w-8 h-8 flex items-center justify-center rounded-full bg-[#141210] border border-[#3d3428] text-[#a09888] hover:text-[#f5f2ea] transition"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
