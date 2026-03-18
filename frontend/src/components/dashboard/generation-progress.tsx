"use client";

import { usePolling } from "@/hooks/use-polling";
import type { JobResult, JobStatus } from "@/lib/types";
import { useEffect, useRef, useState } from "react";

interface Props {
  jobId: string;
  fetcher: () => Promise<JobStatus>;
  onDone: (data: { result?: JobResult }) => void;
  onRetry?: () => void;
}

interface Step {
  label: string;
  status: "done" | "active" | "pending";
}

function parseSteps(logs: string): Step[] {
  const lines = logs.toLowerCase();
  const steps: { key: string; label: string; patterns: RegExp[] }[] = [
    {
      key: "scan",
      label: "Scanning uploaded files",
      patterns: [/scanning|loading.*files|found.*files|media files/],
    },
    {
      key: "extract",
      label: "Extracting content from files",
      patterns: [/extract|ocr|slides|pages|pptx|pdf/],
    },
    {
      key: "script",
      label: "Writing voiceover scripts",
      patterns: [/script|narrative|unified|generat.*script|claude|writing/],
    },
    {
      key: "animate",
      label: "Creating video animations",
      patterns: [/veo|animat|generat.*video|scene.*\d|motion/],
    },
    {
      key: "voice",
      label: "Generating voiceover audio",
      patterns: [/tts|voiceover|elevenlabs|voice|speech|audio.*generat/],
    },
    {
      key: "combine",
      label: "Combining video and audio",
      patterns: [/combin|merge|mux|attach.*audio/],
    },
    {
      key: "assemble",
      label: "Assembling final video",
      patterns: [/concatenat|assembl|final|stitch|joining/],
    },
    {
      key: "music",
      label: "Adding background music",
      patterns: [/music|background.*audio|mixing.*music/],
    },
    {
      key: "export",
      label: "Exporting video",
      patterns: [/export|saving|output|mp4|done|complete|finished/],
    },
  ];

  let lastMatched = -1;
  for (let i = 0; i < steps.length; i++) {
    for (const pat of steps[i].patterns) {
      if (pat.test(lines)) {
        lastMatched = i;
      }
    }
  }

  return steps.map((s, i) => ({
    label: s.label,
    status: i < lastMatched ? "done" : i === lastMatched ? "active" : "pending",
  }));
}

function progressPercent(steps: Step[]): number {
  const done = steps.filter((s) => s.status === "done").length;
  const active = steps.filter((s) => s.status === "active").length;
  const total = steps.length;
  if (total === 0) return 5;
  return Math.round(((done + active * 0.5) / total) * 100);
}

export default function GenerationProgress({ jobId, fetcher, onDone, onRetry }: Props) {
  const logRef = useRef<HTMLPreElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [showRawLogs, setShowRawLogs] = useState(false);

  const { data } = usePolling<JobStatus>(fetcher, 3000, {
    onDone: (d) => onDone({ result: d.result }),
    onError: (err) => setError(err),
  });

  const logs = data?.logs ?? "";
  const state = error ? "error" : data?.state ?? "pending";
  const steps = parseSteps(logs);
  const percent = state === "done" ? 100 : progressPercent(steps);

  // Auto-scroll logs
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [logs]);

  const activeStep = steps.find((s) => s.status === "active");

  return (
    <div className="bg-[#141210] border border-[#3d3428] rounded-xl p-6 space-y-5">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-[#f5f2ea]">Generating Video</h2>
        <span className={`text-xs px-2 py-1 rounded-full ${
          state === "error"
            ? "bg-red-500/10 text-red-400"
            : state === "done"
            ? "bg-emerald-500/10 text-emerald-400"
            : "bg-[#d4b44e]/10 text-[#d4b44e]"
        }`}>
          {state === "done" ? "complete" : state}
        </span>
      </div>

      {/* Progress bar */}
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <p className="text-sm text-[#f5f2ea]">
            {activeStep?.label ?? (state === "done" ? "Video ready!" : "Starting...")}
          </p>
          <span className="text-xs text-[#7a7060]">{percent}%</span>
        </div>
        <div className="h-2 rounded-full bg-[#161208] overflow-hidden">
          <div
            className="h-full rounded-full bg-gradient-to-r from-[#d4b44e] to-[#f0d060] transition-all duration-1000"
            style={{ width: `${percent}%` }}
          />
        </div>
      </div>

      {/* Steps */}
      <div className="space-y-1">
        {steps.map((step, i) => (
          <div key={i} className="flex items-center gap-2.5">
            {step.status === "done" ? (
              <svg className="w-4 h-4 text-emerald-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            ) : step.status === "active" ? (
              <div className="w-4 h-4 shrink-0 flex items-center justify-center">
                <div className="w-3 h-3 border-2 border-[#d4b44e] border-t-transparent rounded-full animate-spin" />
              </div>
            ) : (
              <div className="w-4 h-4 shrink-0 flex items-center justify-center">
                <div className="w-2 h-2 rounded-full bg-[#3d3428]" />
              </div>
            )}
            <span className={`text-sm ${
              step.status === "done"
                ? "text-[#a09888]"
                : step.status === "active"
                ? "text-[#f5f2ea]"
                : "text-[#5a5040]"
            }`}>
              {step.label}
            </span>
          </div>
        ))}
      </div>

      {/* Raw logs toggle */}
      <div>
        <button
          onClick={() => setShowRawLogs(!showRawLogs)}
          className="flex items-center gap-1.5 text-xs text-[#7a7060] hover:text-[#a09888] transition"
        >
          <svg
            className={`w-3 h-3 transition-transform ${showRawLogs ? "rotate-180" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
          {showRawLogs ? "Hide" : "Show"} technical logs
        </button>
        {showRawLogs && (
          <pre
            ref={logRef}
            className="mt-2 bg-[#0c0c0c] border border-[#3d3428] rounded-lg p-4 text-xs text-[#7a7060] font-mono max-h-48 overflow-y-auto whitespace-pre-wrap"
          >
            {logs || "Waiting for logs..."}
          </pre>
        )}
      </div>

      {error && (
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-sm text-red-400 bg-red-500/5 border border-red-500/20 rounded-lg px-3 py-2">
            <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
            Generation failed: {error}
          </div>
          {onRetry && (
            <button
              onClick={onRetry}
              className="px-4 py-2 rounded-lg border border-[#3d3428] text-sm text-[#a09888] hover:text-[#f5f2ea] hover:border-[#d4b44e] transition"
            >
              Try Again
            </button>
          )}
        </div>
      )}

      <p className="text-xs text-[#7a7060] text-center">
        Job ID: {jobId}
      </p>
    </div>
  );
}
