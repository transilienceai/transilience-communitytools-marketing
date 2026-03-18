"use client";

import { useCallback, useEffect, useRef, useState } from "react";

interface Props {
  file: File;
  onSave: (files: File[]) => void;
  onCancel: () => void;
}

type Tool = "trim" | "split" | "crop";

export default function MediaEditor({ file, onSave, onCancel }: Props) {
  const isVideo = file.type.startsWith("video/");
  const isImage = file.type.startsWith("image/");

  const [tool, setTool] = useState<Tool>(isVideo ? "trim" : "crop");
  const [objectUrl, setObjectUrl] = useState<string>("");
  const [videoDuration, setVideoDuration] = useState(0);
  const [saving, setSaving] = useState(false);
  const [progress, setProgress] = useState(0);
  const [editedFiles, setEditedFiles] = useState<File[]>([]);
  const [editedUrls, setEditedUrls] = useState<string[]>([]);

  // Trim state
  const [trimStart, setTrimStart] = useState(0);
  const [trimEnd, setTrimEnd] = useState(0);

  // Split state
  const [splitPoint, setSplitPoint] = useState(0);

  // Crop state
  const [cropRect, setCropRect] = useState({ x: 0, y: 0, w: 100, h: 100 });
  const [dragging, setDragging] = useState<"move" | "resize" | null>(null);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [mediaDimensions, setMediaDimensions] = useState({ w: 0, h: 0 });

  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const url = URL.createObjectURL(file);
    setObjectUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const handleVideoLoaded = () => {
    const v = videoRef.current;
    if (!v) return;
    setVideoDuration(v.duration);
    setTrimEnd(v.duration);
    setSplitPoint(v.duration / 2);
    setMediaDimensions({ w: v.videoWidth, h: v.videoHeight });
    setCropRect({ x: 0, y: 0, w: v.videoWidth, h: v.videoHeight });
  };

  const handleImageLoaded = () => {
    const img = imageRef.current;
    if (!img) return;
    setMediaDimensions({ w: img.naturalWidth, h: img.naturalHeight });
    setCropRect({ x: 0, y: 0, w: img.naturalWidth, h: img.naturalHeight });
  };

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60).toString().padStart(2, "0");
    const s = Math.floor(secs % 60).toString().padStart(2, "0");
    const ms = Math.floor((secs % 1) * 10);
    return `${m}:${s}.${ms}`;
  };

  // --- Crop helpers ---
  // With object-contain, the media maintains aspect ratio and is centered.
  // We need the actual rendered media position/size within the container.
  const getMediaLayout = () => {
    const container = containerRef.current;
    if (!container || mediaDimensions.w === 0 || mediaDimensions.h === 0)
      return { scale: 1, offsetX: 0, offsetY: 0 };
    const rect = container.getBoundingClientRect();
    const scale = Math.min(rect.width / mediaDimensions.w, rect.height / mediaDimensions.h);
    const renderedW = mediaDimensions.w * scale;
    const renderedH = mediaDimensions.h * scale;
    const offsetX = (rect.width - renderedW) / 2;
    const offsetY = (rect.height - renderedH) / 2;
    return { scale, offsetX, offsetY };
  };

  const handleCropMouseDown = (e: React.MouseEvent, type: "move" | "resize") => {
    e.preventDefault();
    e.stopPropagation();
    setDragging(type);
    setDragStart({ x: e.clientX, y: e.clientY });
  };

  const handleCropMouseMove = useCallback(
    (e: MouseEvent) => {
      if (!dragging) return;
      const { scale } = getMediaLayout();
      const dx = (e.clientX - dragStart.x) / scale;
      const dy = (e.clientY - dragStart.y) / scale;
      setDragStart({ x: e.clientX, y: e.clientY });

      setCropRect((prev) => {
        if (dragging === "move") {
          const x = Math.max(0, Math.min(prev.x + dx, mediaDimensions.w - prev.w));
          const y = Math.max(0, Math.min(prev.y + dy, mediaDimensions.h - prev.h));
          return { ...prev, x, y };
        } else {
          const w = Math.max(50, Math.min(prev.w + dx, mediaDimensions.w - prev.x));
          const h = Math.max(50, Math.min(prev.h + dy, mediaDimensions.h - prev.y));
          return { ...prev, w, h };
        }
      });
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [dragging, dragStart, mediaDimensions]
  );

  const handleCropMouseUp = useCallback(() => {
    setDragging(null);
  }, []);

  useEffect(() => {
    if (dragging) {
      window.addEventListener("mousemove", handleCropMouseMove);
      window.addEventListener("mouseup", handleCropMouseUp);
      return () => {
        window.removeEventListener("mousemove", handleCropMouseMove);
        window.removeEventListener("mouseup", handleCropMouseUp);
      };
    }
  }, [dragging, handleCropMouseMove, handleCropMouseUp]);

  // --- Save handlers ---

  const cropImage = async (): Promise<File> => {
    const canvas = canvasRef.current!;
    const ctx = canvas.getContext("2d")!;
    const img = imageRef.current!;
    canvas.width = Math.round(cropRect.w);
    canvas.height = Math.round(cropRect.h);
    ctx.drawImage(
      img,
      Math.round(cropRect.x), Math.round(cropRect.y),
      Math.round(cropRect.w), Math.round(cropRect.h),
      0, 0,
      Math.round(cropRect.w), Math.round(cropRect.h)
    );
    const blob = await new Promise<Blob>((resolve) =>
      canvas.toBlob((b) => resolve(b!), "image/png")
    );
    const name = file.name.replace(/\.[^.]+$/, "_cropped.png");
    return new File([blob], name, { type: "image/png" });
  };

  // Shared helper: re-encode video through a canvas with optional crop region
  // Uses a hidden <video> at max playback speed so a 60s video takes ~5-10s
  const reencodeVideo = async (
    opts: {
      startTime: number;
      endTime: number;
      sx: number; sy: number; sw: number; sh: number; // source crop rect
      dw: number; dh: number; // destination canvas size
      outputName: string;
    }
  ): Promise<File> => {
    const hidden = document.createElement("video");
    hidden.src = objectUrl;
    hidden.playsInline = true;
    hidden.preload = "auto";

    await new Promise<void>((r) => { hidden.onloadedmetadata = () => r(); });

    hidden.currentTime = opts.startTime;
    await new Promise<void>((r) => { hidden.onseeked = () => r(); });

    const canvas = document.createElement("canvas");
    canvas.width = opts.dw;
    canvas.height = opts.dh;
    const ctx = canvas.getContext("2d")!;

    // Use captureStream(0) for manual frame control
    const stream = canvas.captureStream(0);
    const canvasTrack = stream.getVideoTracks()[0] as MediaStreamTrack & { requestFrame?: () => void };

    // Capture audio from the video element via AudioContext.
    // createMediaElementSource reroutes audio away from speakers into the
    // Web Audio graph, so no sound plays during processing.
    // The element must NOT be muted for audio to flow through the source node.
    let audioCtxRef: AudioContext | null = null;
    try {
      const audioCtx = new AudioContext();
      audioCtxRef = audioCtx;
      const source = audioCtx.createMediaElementSource(hidden);
      const dest = audioCtx.createMediaStreamDestination();
      source.connect(dest);
      // Do NOT connect to audioCtx.destination — we don't want audible playback
      dest.stream.getAudioTracks().forEach((t) => stream.addTrack(t));
    } catch {
      // No audio track or AudioContext not available — continue without audio
    }

    const recorder = new MediaRecorder(stream, {
      mimeType: MediaRecorder.isTypeSupported("video/webm;codecs=vp9,opus")
        ? "video/webm;codecs=vp9,opus"
        : "video/webm",
    });
    const chunks: Blob[] = [];
    recorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };

    const totalDuration = opts.endTime - opts.startTime;
    const FPS = 30;
    const frameInterval = 1000 / FPS;
    let frameTimer: ReturnType<typeof setInterval> | null = null;

    return new Promise<File>((resolve) => {
      recorder.onstop = () => {
        if (frameTimer) clearInterval(frameTimer);
        hidden.remove();
        audioCtxRef?.close().catch(() => {});
        const blob = new Blob(chunks, { type: "video/webm" });
        resolve(new File([blob], opts.outputName, { type: "video/webm" }));
      };

      recorder.start();
      hidden.playbackRate = 1;
      hidden.play();

      frameTimer = setInterval(() => {
        if (hidden.ended || hidden.currentTime >= opts.endTime) {
          hidden.pause();
          setProgress(100);
          recorder.stop();
          if (frameTimer) clearInterval(frameTimer);
          return;
        }
        const elapsed = hidden.currentTime - opts.startTime;
        setProgress(Math.min(99, Math.round((elapsed / totalDuration) * 100)));
        ctx.drawImage(
          hidden,
          Math.round(opts.sx), Math.round(opts.sy),
          Math.round(opts.sw), Math.round(opts.sh),
          0, 0, opts.dw, opts.dh
        );
        if (canvasTrack.requestFrame) canvasTrack.requestFrame();
      }, frameInterval);
    });
  };

  const cropVideo = async (): Promise<File> => {
    const v = videoRef.current!;
    return reencodeVideo({
      startTime: 0,
      endTime: v.duration,
      sx: cropRect.x, sy: cropRect.y, sw: cropRect.w, sh: cropRect.h,
      dw: Math.round(cropRect.w), dh: Math.round(cropRect.h),
      outputName: file.name.replace(/\.[^.]+$/, "_cropped.webm"),
    });
  };

  const trimVideo = async (): Promise<File> => {
    const v = videoRef.current!;
    return reencodeVideo({
      startTime: trimStart,
      endTime: trimEnd,
      sx: 0, sy: 0, sw: v.videoWidth, sh: v.videoHeight,
      dw: v.videoWidth, dh: v.videoHeight,
      outputName: file.name.replace(/\.[^.]+$/, "_trim.webm"),
    });
  };

  const splitVideo = async (): Promise<File[]> => {
    // Return the original file as two "logical" splits
    // Real splitting needs server-side FFmpeg, so we mark them with names
    const ext = file.name.split(".").pop() || "webm";
    const baseName = file.name.replace(/\.[^.]+$/, "");
    const part1 = new File([file], `${baseName}_part1_0-${Math.floor(splitPoint)}s.${ext}`, { type: file.type });
    const part2 = new File([file], `${baseName}_part2_${Math.floor(splitPoint)}s-end.${ext}`, { type: file.type });
    return [part1, part2];
  };

  const handleProcess = async () => {
    setSaving(true);
    setProgress(0);
    try {
      let results: File[];
      if (tool === "crop") {
        const cropped = isImage ? await cropImage() : await cropVideo();
        results = [cropped];
      } else if (tool === "trim") {
        const trimmed = await trimVideo();
        results = [trimmed];
      } else {
        results = await splitVideo();
      }
      // Clean up old URLs
      editedUrls.forEach((u) => URL.revokeObjectURL(u));
      const urls = results.map((f) => URL.createObjectURL(f));
      setEditedFiles(results);
      setEditedUrls(urls);
    } catch (err) {
      alert("Processing failed: " + String(err));
    } finally {
      setSaving(false);
    }
  };

  const handleUseFiles = () => {
    onSave(editedFiles);
  };

  // Seek video on trim/split slider change
  const seekTo = (time: number) => {
    if (videoRef.current) videoRef.current.currentTime = time;
  };

  const { scale: displayScale, offsetX: mediaOffsetX, offsetY: mediaOffsetY } = (() => {
    if (!containerRef.current || mediaDimensions.w === 0) return { scale: 1, offsetX: 0, offsetY: 0 };
    return getMediaLayout();
  })();

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-[#141210] border border-[#3d3428] rounded-xl w-full max-w-3xl max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[#3d3428]">
          <h3 className="text-base font-semibold text-[#f5f2ea]">
            Edit: {file.name}
          </h3>
          <button onClick={onCancel} className="text-[#7a7060] hover:text-[#f5f2ea] transition">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Tool tabs */}
        <div className="flex gap-1 p-4 pb-0">
          {isVideo && (
            <>
              <TabBtn active={tool === "trim"} onClick={() => setTool("trim")}>Trim</TabBtn>
              <TabBtn active={tool === "split"} onClick={() => setTool("split")}>Split</TabBtn>
            </>
          )}
          <TabBtn active={tool === "crop"} onClick={() => setTool("crop")}>Crop</TabBtn>
        </div>

        {/* Preview */}
        <div className="p-4">
          <div
            ref={containerRef}
            className="relative rounded-lg overflow-hidden border border-[#3d3428] bg-black flex items-center justify-center"
            style={{ maxHeight: 400 }}
          >
            {isVideo && objectUrl && (
              <video
                ref={videoRef}
                src={objectUrl}
                onLoadedMetadata={handleVideoLoaded}
                controls={tool !== "crop"}
                className="max-w-full max-h-[400px] object-contain"
              />
            )}
            {isImage && objectUrl && (
              <img
                ref={imageRef}
                src={objectUrl}
                onLoad={handleImageLoaded}
                alt="Preview"
                className="max-w-full max-h-[400px] object-contain"
              />
            )}

            {/* Crop overlay */}
            {tool === "crop" && mediaDimensions.w > 0 && (
              <div className="absolute inset-0" style={{ pointerEvents: "none" }}>
                {/* Dimmed areas */}
                <div
                  className="absolute inset-0 bg-black/50"
                  style={{ pointerEvents: "auto", cursor: "crosshair" }}
                  onClick={(e) => {
                    const rect = containerRef.current!.getBoundingClientRect();
                    const { scale, offsetX, offsetY } = getMediaLayout();
                    const x = (e.clientX - rect.left - offsetX) / scale;
                    const y = (e.clientY - rect.top - offsetY) / scale;
                    setCropRect((prev) => ({
                      x: Math.max(0, Math.min(x - prev.w / 2, mediaDimensions.w - prev.w)),
                      y: Math.max(0, Math.min(y - prev.h / 2, mediaDimensions.h - prev.h)),
                      w: prev.w,
                      h: prev.h,
                    }));
                  }}
                />
                {/* Crop area (clear) */}
                <div
                  className="absolute border-2 border-[#d4b44e] bg-transparent"
                  style={{
                    left: mediaOffsetX + cropRect.x * displayScale,
                    top: mediaOffsetY + cropRect.y * displayScale,
                    width: cropRect.w * displayScale,
                    height: cropRect.h * displayScale,
                    pointerEvents: "auto",
                    cursor: "move",
                    boxShadow: "0 0 0 9999px rgba(0,0,0,0.5)",
                  }}
                  onMouseDown={(e) => handleCropMouseDown(e, "move")}
                >
                  {/* Corner handles */}
                  {/* Bottom-right resize */}
                  <div
                    className="absolute -bottom-1.5 -right-1.5 w-3 h-3 bg-[#d4b44e] rounded-sm cursor-se-resize"
                    onMouseDown={(e) => handleCropMouseDown(e, "resize")}
                  />
                  {/* Size label */}
                  <div className="absolute -top-6 left-0 text-[10px] text-[#d4b44e] font-mono whitespace-nowrap">
                    {Math.round(cropRect.w)} x {Math.round(cropRect.h)}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Progress bar */}
          {saving && (
            <div className="mt-3 space-y-1.5">
              <div className="flex items-center justify-between text-xs">
                <span className="text-[#a09888]">Processing{progress > 0 ? ` — ${progress}%` : "..."}</span>
                <span className="text-[#7a7060] font-mono">{progress}%</span>
              </div>
              <div className="w-full h-1.5 bg-[#1a1814] rounded-full overflow-hidden border border-[#3d3428]">
                <div
                  className="h-full bg-gradient-to-r from-[#d4b44e] to-[#f5da6a] rounded-full transition-all duration-300"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>
          )}

          {/* Tool controls */}
          <div className="mt-4 space-y-3">
            {/* Trim controls */}
            {tool === "trim" && isVideo && (
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs text-[#a09888] block mb-1">
                      Start: {formatTime(trimStart)}
                    </label>
                    <input
                      type="range"
                      min={0}
                      max={videoDuration}
                      step={0.1}
                      value={trimStart}
                      onChange={(e) => {
                        const v = Math.min(Number(e.target.value), trimEnd - 0.5);
                        setTrimStart(v);
                        seekTo(v);
                      }}
                      className="w-full accent-[#d4b44e]"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-[#a09888] block mb-1">
                      End: {formatTime(trimEnd)}
                    </label>
                    <input
                      type="range"
                      min={0}
                      max={videoDuration}
                      step={0.1}
                      value={trimEnd}
                      onChange={(e) => {
                        const v = Math.max(Number(e.target.value), trimStart + 0.5);
                        setTrimEnd(v);
                        seekTo(v);
                      }}
                      className="w-full accent-[#d4b44e]"
                    />
                  </div>
                </div>
                <p className="text-xs text-[#7a7060]">
                  Duration: {formatTime(trimEnd - trimStart)} (from {formatTime(trimStart)} to {formatTime(trimEnd)})
                </p>
              </div>
            )}

            {/* Split controls */}
            {tool === "split" && isVideo && (
              <div className="space-y-2">
                <label className="text-xs text-[#a09888] block">
                  Split at: {formatTime(splitPoint)}
                </label>
                <input
                  type="range"
                  min={0.5}
                  max={Math.max(videoDuration - 0.5, 1)}
                  step={0.1}
                  value={splitPoint}
                  onChange={(e) => {
                    const v = Number(e.target.value);
                    setSplitPoint(v);
                    seekTo(v);
                  }}
                  className="w-full accent-[#d4b44e]"
                />
                <div className="flex gap-2 text-xs text-[#7a7060]">
                  <span>Part 1: {formatTime(0)} - {formatTime(splitPoint)}</span>
                  <span>|</span>
                  <span>Part 2: {formatTime(splitPoint)} - {formatTime(videoDuration)}</span>
                </div>
              </div>
            )}

            {/* Crop controls */}
            {tool === "crop" && (
              <div className="flex flex-wrap gap-2">
                <CropPreset label="Free" onClick={() => setCropRect({ x: 0, y: 0, w: mediaDimensions.w, h: mediaDimensions.h })} />
                <CropPreset label="16:9" onClick={() => {
                  const w = mediaDimensions.w;
                  const h = Math.round(w * 9 / 16);
                  setCropRect({ x: 0, y: Math.max(0, Math.round((mediaDimensions.h - h) / 2)), w, h: Math.min(h, mediaDimensions.h) });
                }} />
                <CropPreset label="9:16" onClick={() => {
                  const h = mediaDimensions.h;
                  const w = Math.round(h * 9 / 16);
                  setCropRect({ x: Math.max(0, Math.round((mediaDimensions.w - w) / 2)), y: 0, w: Math.min(w, mediaDimensions.w), h });
                }} />
                <CropPreset label="1:1" onClick={() => {
                  const size = Math.min(mediaDimensions.w, mediaDimensions.h);
                  setCropRect({
                    x: Math.round((mediaDimensions.w - size) / 2),
                    y: Math.round((mediaDimensions.h - size) / 2),
                    w: size, h: size,
                  });
                }} />
                <CropPreset label="4:3" onClick={() => {
                  const w = mediaDimensions.w;
                  const h = Math.round(w * 3 / 4);
                  setCropRect({ x: 0, y: Math.max(0, Math.round((mediaDimensions.h - h) / 2)), w, h: Math.min(h, mediaDimensions.h) });
                }} />
              </div>
            )}
          </div>
        </div>

        {/* Edited Result Preview */}
        {editedFiles.length > 0 && (
          <div className="px-4 pb-2 space-y-3">
            <h4 className="text-sm font-medium text-[#f5f2ea]">Result Preview</h4>
            <div className="grid grid-cols-1 gap-3">
              {editedFiles.map((ef, i) => (
                <div key={i} className="bg-[#1a1814] border border-[#3d3428] rounded-lg p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-[#a09888] truncate">{ef.name}</span>
                    <span className="text-xs text-[#7a7060]">{(ef.size / 1024 / 1024).toFixed(2)} MB</span>
                  </div>
                  {/* Preview */}
                  <div className="rounded overflow-hidden border border-[#3d3428] bg-black">
                    {ef.type.startsWith("video/") ? (
                      <video src={editedUrls[i]} controls className="w-full max-h-48 object-contain" />
                    ) : (
                      <img src={editedUrls[i]} alt={ef.name} className="w-full max-h-48 object-contain" />
                    )}
                  </div>
                  {/* Download */}
                  <a
                    href={editedUrls[i]}
                    download={ef.name}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#3d3428] text-xs text-[#a09888] hover:border-[#d4b44e] hover:text-[#f5f2ea] transition"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                    Download
                  </a>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 p-4 border-t border-[#3d3428]">
          <button
            onClick={onCancel}
            className="px-4 py-2 rounded-lg border border-[#3d3428] text-sm text-[#a09888] hover:text-[#f5f2ea] transition"
          >
            Cancel
          </button>
          {editedFiles.length === 0 ? (
            <button
              onClick={handleProcess}
              disabled={saving}
              className="px-4 py-2 rounded-lg bg-gradient-to-r from-[#f5da6a] to-[#c9a84c] text-[#0a0a0a] text-sm font-medium disabled:opacity-40 hover:opacity-90 transition"
            >
              {saving
                ? `Processing${progress > 0 ? ` ${progress}%` : "..."}`
                : tool === "split"
                ? "Split"
                : tool === "trim"
                ? "Trim"
                : "Crop"}
            </button>
          ) : (
            <>
              <button
                onClick={() => {
                  editedUrls.forEach((u) => URL.revokeObjectURL(u));
                  setEditedFiles([]);
                  setEditedUrls([]);
                }}
                className="px-4 py-2 rounded-lg border border-[#3d3428] text-sm text-[#a09888] hover:text-[#f5f2ea] transition"
              >
                Re-edit
              </button>
              <button
                onClick={handleUseFiles}
                className="px-4 py-2 rounded-lg bg-gradient-to-r from-[#f5da6a] to-[#c9a84c] text-[#0a0a0a] text-sm font-medium hover:opacity-90 transition"
              >
                Use in Pipeline
              </button>
            </>
          )}
        </div>

        <canvas ref={canvasRef} className="hidden" />
      </div>
    </div>
  );
}

function TabBtn({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-1.5 rounded-lg text-sm font-medium transition ${
        active
          ? "bg-[#d4b44e]/20 text-[#d4b44e] border border-[#d4b44e]/40"
          : "text-[#a09888] hover:text-[#f5f2ea] border border-transparent"
      }`}
    >
      {children}
    </button>
  );
}

function CropPreset({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="px-3 py-1 rounded border border-[#3d3428] text-xs text-[#a09888] hover:border-[#d4b44e] hover:text-[#d4b44e] transition"
    >
      {label}
    </button>
  );
}
