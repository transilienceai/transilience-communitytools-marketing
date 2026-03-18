"use client";

import { useEffect, useRef, useState } from "react";
import { downloadUrl, fetchRecentJobs, type RecentJob } from "@/lib/api";
import PostProcessing from "./post-processing";

interface Props {
  onLoadJob: (jobId: string, hasAudio: boolean, hasMusic: boolean) => void;
}

export default function RecentVideos({ onLoadJob }: Props) {
  const [jobs, setJobs] = useState<RecentJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<RecentJob | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchRecentJobs()
      .then(setJobs)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Load preview when a job is selected
  useEffect(() => {
    if (!selected) {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      setPreviewUrl(null);
      return;
    }
    setPreviewLoading(true);
    let cancelled = false;
    fetch(downloadUrl(selected.job_id, "video"))
      .then((res) => {
        if (!res.ok) throw new Error("Failed");
        return res.blob();
      })
      .then((blob) => {
        if (!cancelled) {
          if (previewUrl) URL.revokeObjectURL(previewUrl);
          setPreviewUrl(URL.createObjectURL(blob));
        }
      })
      .catch(() => {
        if (!cancelled) setPreviewUrl(null);
      })
      .finally(() => {
        if (!cancelled) setPreviewLoading(false);
      });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected]);

  if (loading || jobs.length === 0) return null;

  const formatDate = (ts: number) => {
    const d = new Date(ts * 1000);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    if (diffDays < 7) return `${diffDays}d ago`;
    return d.toLocaleDateString();
  };

  const handleSelect = (job: RecentJob) => {
    setSelected(job);
    setOpen(false);
  };

  return (
    <div className="bg-[#141210] border border-[#3d3428] rounded-xl p-6">
      <h2 className="text-lg font-semibold mb-4 text-[#f5f2ea]">Recent Videos</h2>

      {/* Dropdown */}
      <div className="relative" ref={dropdownRef}>
        <button
          onClick={() => setOpen(!open)}
          className="w-full flex items-center justify-between px-4 py-2.5 rounded-lg border border-[#3d3428] bg-[#1a1814] text-sm text-[#a09888] hover:border-[#d4b44e]/40 transition"
        >
          <span className={selected ? "text-[#f5f2ea]" : ""}>
            {selected
              ? `${selected.job_id.slice(0, 8)}... — ${formatDate(selected.created_at)}`
              : "Select a recent video"}
          </span>
          <svg
            className={`w-4 h-4 text-[#7a7060] transition-transform ${open ? "rotate-180" : ""}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {open && (
          <div className="absolute z-20 mt-1 w-full rounded-lg border border-[#3d3428] bg-[#1a1814] shadow-xl max-h-60 overflow-y-auto">
            {jobs.map((job) => (
              <button
                key={job.job_id}
                onClick={() => handleSelect(job)}
                className={`w-full flex items-center justify-between px-4 py-3 text-left hover:bg-[#d4b44e]/10 transition border-b border-[#3d3428]/50 last:border-b-0 ${
                  selected?.job_id === job.job_id ? "bg-[#d4b44e]/5" : ""
                }`}
              >
                <div>
                  <span className="text-xs font-mono text-[#f5f2ea]">{job.job_id.slice(0, 12)}...</span>
                  <div className="flex gap-2 mt-1">
                    {job.has_audio && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#3d3428] text-[#a09888]">Audio</span>
                    )}
                    {job.has_music && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#3d3428] text-[#a09888]">Music</span>
                    )}
                  </div>
                </div>
                <span className="text-xs text-[#7a7060]">{formatDate(job.created_at)}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Preview & Actions */}
      {selected && (
        <div className="mt-4 space-y-4">
          {/* Video Preview */}
          <div className="rounded-lg overflow-hidden border border-[#3d3428] bg-black aspect-video">
            {previewLoading ? (
              <div className="flex items-center justify-center h-full text-sm text-[#7a7060]">
                <svg className="animate-spin w-5 h-5 mr-2" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Loading preview...
              </div>
            ) : previewUrl ? (
              <video
                src={previewUrl}
                controls
                className="w-full h-full object-contain"
              />
            ) : (
              <div className="flex items-center justify-center h-full text-sm text-[#7a7060]">
                Preview unavailable
              </div>
            )}
          </div>

          {/* Action Buttons */}
          <div className="flex flex-wrap gap-2">
            <a
              href={downloadUrl(selected.job_id, "video")}
              download
              className="px-4 py-2 rounded-lg bg-gradient-to-r from-[#f5da6a] to-[#c9a84c] text-[#0a0a0a] text-sm font-medium hover:opacity-90 transition"
            >
              Download Video
            </a>
            {selected.has_audio && (
              <a
                href={downloadUrl(selected.job_id, "audio")}
                download
                className="px-4 py-2 rounded-lg border border-[#3d3428] text-sm text-[#a09888] hover:border-[#d4b44e] hover:text-[#f5f2ea] transition"
              >
                Download Audio
              </a>
            )}
            {selected.has_music && (
              <a
                href={downloadUrl(selected.job_id, "music")}
                download
                className="px-4 py-2 rounded-lg border border-[#3d3428] text-sm text-[#a09888] hover:border-[#d4b44e] hover:text-[#f5f2ea] transition"
              >
                Download Music
              </a>
            )}
            <button
              onClick={() => onLoadJob(selected.job_id, selected.has_audio, selected.has_music)}
              className="px-4 py-2 rounded-lg border border-[#d4b44e]/40 text-sm text-[#d4b44e] hover:bg-[#d4b44e]/10 transition"
            >
              Open in Results
            </button>
          </div>

          {/* Post-Processing */}
          <PostProcessing
            videoUrl={downloadUrl(selected.job_id, "video")}
            audioUrl={downloadUrl(selected.job_id, "audio")}
            musicUrl={downloadUrl(selected.job_id, "music")}
            hasAudio={selected.has_audio}
            hasMusic={selected.has_music}
          />
        </div>
      )}
    </div>
  );
}
