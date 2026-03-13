"use client";

import type { JobResult } from "@/lib/types";
import AvatarOverlay from "./avatar-overlay";

interface Props {
  jobId: string;
  result: JobResult | null;
  videoUrl: string;
  audioUrl: string;
  musicUrl: string;
  onNewVideo: () => void;
}

export default function ResultsPanel({
  jobId,
  result,
  videoUrl,
  audioUrl,
  musicUrl,
  onNewVideo,
}: Props) {
  return (
    <div className="space-y-6">
      {/* Video Player */}
      <div className="bg-[#161616] border border-[#222] rounded-xl p-6">
        <h2 className="text-lg font-semibold mb-4">Your Video</h2>
        <video
          src={videoUrl}
          controls
          className="w-full rounded-lg bg-black"
          autoPlay
        />
      </div>

      {/* Downloads */}
      <div className="bg-[#161616] border border-[#222] rounded-xl p-6">
        <h2 className="text-lg font-semibold mb-4">Downloads</h2>
        <div className="flex flex-wrap gap-3">
          <DownloadButton href={videoUrl} label="Video (MP4)" />
          {result?.has_audio && (
            <DownloadButton href={audioUrl} label="Audio (MP3)" />
          )}
          {result?.has_music && (
            <DownloadButton href={musicUrl} label="Music (MP3)" />
          )}
        </div>
      </div>

      {/* Cost */}
      {result?.cost && (
        <div className="bg-[#161616] border border-[#222] rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-4">Cost Estimate</h2>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-center">
            <CostItem label="Gemini Vision" value={result.cost.gemini_vision} />
            <CostItem label="Veo Animation" value={result.cost.veo_animation} />
            <CostItem label="TTS" value={result.cost.tts} />
            <CostItem label="Music" value={result.cost.music} />
            <CostItem
              label="Total"
              value={result.cost.total}
              highlight
            />
          </div>
        </div>
      )}

      {/* Avatar Overlay */}
      <AvatarOverlay jobId={jobId} videoUrl={videoUrl} />

      {/* New Video */}
      <button
        onClick={onNewVideo}
        className="w-full py-3 rounded-lg border border-[#333] text-gray-300 hover:text-white hover:border-orange-500 transition font-medium"
      >
        Create New Video
      </button>
    </div>
  );
}

function DownloadButton({ href, label }: { href: string; label: string }) {
  return (
    <a
      href={href}
      download
      className="px-4 py-2 rounded-lg bg-gradient-to-r from-orange-500 to-pink-500 text-white text-sm font-medium hover:opacity-90 transition"
    >
      {label}
    </a>
  );
}

function CostItem({
  label,
  value,
  highlight,
}: {
  label: string;
  value: number;
  highlight?: boolean;
}) {
  return (
    <div>
      <p className="text-xs text-gray-400">{label}</p>
      <p
        className={`text-lg font-semibold ${
          highlight ? "text-orange-400" : "text-gray-200"
        }`}
      >
        ${value.toFixed(2)}
      </p>
    </div>
  );
}
