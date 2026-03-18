"use client";

import { useRef, useState } from "react";
import { applyAvatar } from "@/lib/api";

interface Props {
  jobId: string;
  videoUrl: string;
}

export default function AvatarOverlay({ jobId, videoUrl }: Props) {
  const avatarInputRef = useRef<HTMLInputElement>(null);
  const [avatarFile, setAvatarFile] = useState<File | null>(null);
  const [position, setPosition] = useState("bottom-right");
  const [scale, setScale] = useState(0.15);
  const [opacity, setOpacity] = useState(1.0);
  const [applying, setApplying] = useState(false);
  const [resultVideoUrl, setResultVideoUrl] = useState<string | null>(null);

  const handleApply = async () => {
    if (!avatarFile) return;
    setApplying(true);
    try {
      // Fetch the video blob
      const videoRes = await fetch(videoUrl);
      const videoBlob = await videoRes.blob();

      const form = new FormData();
      form.append("video", new File([videoBlob], "video.mp4", { type: "video/mp4" }));
      form.append("avatar", avatarFile);
      form.append("position", position);
      form.append("scale", String(scale));
      form.append("opacity", String(opacity));

      const result = await applyAvatar(form);
      if (result.video) {
        // Convert base64 to blob URL
        const binary = atob(result.video);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
        const blob = new Blob([bytes], { type: "video/mp4" });
        setResultVideoUrl(URL.createObjectURL(blob));
      }
    } catch (err) {
      alert(String(err));
    } finally {
      setApplying(false);
    }
  };

  return (
    <div className="bg-[#141210] border border-[#3d3428] rounded-xl p-6 space-y-4">
      <h2 className="text-lg font-semibold text-[#f5f2ea]">Avatar Overlay</h2>

      <div className="text-xs text-[#a09888] space-y-1">
        <p>1. Download the audio above</p>
        <p>2. Create an avatar video (HeyGen, Synthesia, D-ID)</p>
        <p>3. Upload the avatar below and apply</p>
      </div>

      <div>
        <button
          onClick={() => avatarInputRef.current?.click()}
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg border border-dashed border-[#3d3428] text-sm text-[#a09888] hover:border-[#d4b44e] hover:text-[#f5f2ea] transition"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
          </svg>
          {avatarFile ? avatarFile.name : "Upload avatar image or video"}
        </button>
        <input
          ref={avatarInputRef}
          type="file"
          accept="image/*,video/*"
          onChange={(e) => setAvatarFile(e.target.files?.[0] ?? null)}
          className="hidden"
        />
      </div>

      {avatarFile && (
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="text-xs text-[#a09888]">Position</label>
            <select
              value={position}
              onChange={(e) => setPosition(e.target.value)}
              className="input-field mt-1"
            >
              <option value="bottom-right">Bottom Right</option>
              <option value="bottom-left">Bottom Left</option>
              <option value="top-right">Top Right</option>
              <option value="top-left">Top Left</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-[#a09888]">Scale: {Math.round(scale * 100)}%</label>
            <input
              type="range"
              min={0.05}
              max={0.4}
              step={0.01}
              value={scale}
              onChange={(e) => setScale(Number(e.target.value))}
              className="w-full mt-2 accent-[#d4b44e]"
            />
          </div>
          <div>
            <label className="text-xs text-[#a09888]">Opacity: {opacity.toFixed(1)}</label>
            <input
              type="range"
              min={0.1}
              max={1}
              step={0.1}
              value={opacity}
              onChange={(e) => setOpacity(Number(e.target.value))}
              className="w-full mt-2 accent-[#d4b44e]"
            />
          </div>
        </div>
      )}

      {avatarFile && (
        <button
          onClick={handleApply}
          disabled={applying}
          className="px-4 py-2 rounded-lg bg-gradient-to-r from-[#f5da6a] to-[#c9a84c] text-[#0a0a0a] text-sm font-medium disabled:opacity-40 hover:opacity-90 transition"
        >
          {applying ? "Applying..." : "Apply Avatar"}
        </button>
      )}

      {resultVideoUrl && (
        <div>
          <p className="text-sm text-[#f5f2ea] mb-2">Result with Avatar:</p>
          <video src={resultVideoUrl} controls className="w-full rounded-lg" />
          <a
            href={resultVideoUrl}
            download="video_with_avatar.mp4"
            className="inline-block mt-2 px-4 py-2 rounded-lg bg-gradient-to-r from-[#f5da6a] to-[#c9a84c] text-[#0a0a0a] text-sm font-medium hover:opacity-90 transition"
          >
            Download
          </a>
        </div>
      )}
    </div>
  );
}
