"use client";

import { useEffect, useRef, useState } from "react";
import type { JobResult } from "@/lib/types";
import AvatarOverlay from "./avatar-overlay";
import PostProcessing from "./post-processing";

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
      <VideoPlayer videoUrl={videoUrl} />

      {/* Downloads */}
      <div className="bg-[#141210] border border-[#3d3428] rounded-xl p-6">
        <h2 className="text-lg font-semibold mb-4 text-[#f5f2ea]">Downloads</h2>
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
        <div className="bg-[#141210] border border-[#3d3428] rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-4 text-[#f5f2ea]">Cost Estimate</h2>
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

      {/* Post-Processing */}
      <PostProcessing
        videoUrl={videoUrl}
        audioUrl={audioUrl}
        musicUrl={musicUrl}
        hasAudio={result?.has_audio ?? false}
        hasMusic={result?.has_music ?? false}
      />

      {/* Avatar Overlay */}
      <AvatarOverlay jobId={jobId} videoUrl={videoUrl} />

      {/* New Video */}
      <button
        onClick={onNewVideo}
        className="w-full py-3 rounded-lg border border-[#3d3428] text-[#f5f2ea] hover:text-white hover:border-[#d4b44e] transition font-medium"
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
      className="px-4 py-2 rounded-lg bg-gradient-to-r from-[#f5da6a] to-[#c9a84c] text-[#0a0a0a] text-sm font-medium hover:opacity-90 transition"
    >
      {label}
    </a>
  );
}

function VideoPlayer({ videoUrl }: { videoUrl: string }) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const retriesRef = useRef(0);
  const maxRetries = 10;

  useEffect(() => {
    let cancelled = false;

    const fetchVideo = async () => {
      setLoading(true);
      setFailed(false);

      while (retriesRef.current < maxRetries && !cancelled) {
        try {
          const res = await fetch(videoUrl);
          if (res.ok) {
            const blob = await res.blob();
            if (!cancelled) {
              setBlobUrl(URL.createObjectURL(blob));
              setLoading(false);
            }
            return;
          }
        } catch {
          // ignore, will retry
        }
        retriesRef.current += 1;
        // Wait 3 seconds before retrying
        await new Promise((r) => setTimeout(r, 3000));
      }

      if (!cancelled) {
        setLoading(false);
        setFailed(true);
      }
    };

    fetchVideo();

    return () => {
      cancelled = true;
    };
  }, [videoUrl]);

  const handleRetry = () => {
    retriesRef.current = 0;
    setBlobUrl(null);
    setFailed(false);
    setLoading(true);

    const fetchVideo = async () => {
      while (retriesRef.current < maxRetries) {
        try {
          const res = await fetch(videoUrl);
          if (res.ok) {
            const blob = await res.blob();
            setBlobUrl(URL.createObjectURL(blob));
            setLoading(false);
            return;
          }
        } catch {
          // ignore
        }
        retriesRef.current += 1;
        await new Promise((r) => setTimeout(r, 3000));
      }
      setLoading(false);
      setFailed(true);
    };

    fetchVideo();
  };

  return (
    <div className="bg-[#141210] border border-[#3d3428] rounded-xl p-6">
      <h2 className="text-lg font-semibold mb-4 text-[#f5f2ea]">Your Video</h2>
      {loading && (
        <div className="w-full aspect-video rounded-lg bg-black flex flex-col items-center justify-center gap-2">
          <div className="w-6 h-6 border-2 border-[#d4b44e] border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-[#a09888]">Loading video...</p>
        </div>
      )}
      {!loading && blobUrl && (
        <video
          src={blobUrl}
          controls
          className="w-full rounded-lg bg-black"
          autoPlay
        />
      )}
      {!loading && failed && (
        <div className="w-full aspect-video rounded-lg bg-black flex flex-col items-center justify-center gap-3">
          <p className="text-sm text-[#a09888]">Video preview unavailable</p>
          <div className="flex gap-3">
            <button
              onClick={handleRetry}
              className="px-4 py-2 rounded-lg border border-[#3d3428] text-sm text-[#a09888] hover:text-[#f5f2ea] hover:border-[#d4b44e] transition"
            >
              Retry
            </button>
            <a
              href={videoUrl}
              download
              className="px-4 py-2 rounded-lg bg-gradient-to-r from-[#f5da6a] to-[#c9a84c] text-[#0a0a0a] text-sm font-medium hover:opacity-90 transition"
            >
              Download Video
            </a>
          </div>
        </div>
      )}
    </div>
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
      <p className="text-xs text-[#a09888]">{label}</p>
      <p
        className={`text-lg font-semibold ${
          highlight ? "text-[#d4b44e]" : "text-[#f5f2ea]"
        }`}
      >
        ${value.toFixed(2)}
      </p>
    </div>
  );
}
