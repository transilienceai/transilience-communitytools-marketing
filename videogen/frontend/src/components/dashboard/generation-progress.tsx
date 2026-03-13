"use client";

import { usePolling } from "@/hooks/use-polling";
import type { JobResult, JobStatus } from "@/lib/types";
import { useEffect, useRef } from "react";

interface Props {
  jobId: string;
  fetcher: () => Promise<JobStatus>;
  onDone: (data: { result?: JobResult }) => void;
}

export default function GenerationProgress({ jobId, fetcher, onDone }: Props) {
  const logRef = useRef<HTMLPreElement>(null);

  const { data } = usePolling<JobStatus>(fetcher, 3000, {
    onDone: (d) => onDone({ result: d.result }),
    onError: (err) => alert(`Generation failed: ${err}`),
  });

  const logs = data?.logs ?? "";
  const state = data?.state ?? "pending";

  // Auto-scroll logs
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [logs]);

  const lastLine = logs.trim().split("\n").pop() ?? "Starting...";

  return (
    <div className="bg-[#161616] border border-[#222] rounded-xl p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Generating Video</h2>
        <span className="text-xs px-2 py-1 rounded-full bg-orange-500/10 text-orange-400">
          {state}
        </span>
      </div>

      {/* Progress bar */}
      <div className="h-1.5 rounded-full bg-[#222] overflow-hidden">
        <div
          className="h-full rounded-full bg-gradient-to-r from-orange-500 to-pink-500 transition-all duration-1000"
          style={{
            width:
              state === "done"
                ? "100%"
                : state === "running"
                ? "60%"
                : "10%",
            animation: state === "running" ? "pulse 2s infinite" : "none",
          }}
        />
      </div>

      <p className="text-sm text-gray-400 truncate">{lastLine}</p>

      {/* Logs */}
      <pre
        ref={logRef}
        className="bg-[#0f0f0f] border border-[#222] rounded-lg p-4 text-xs text-gray-400 font-mono max-h-64 overflow-y-auto whitespace-pre-wrap"
      >
        {logs || "Waiting for logs..."}
      </pre>

      <p className="text-xs text-gray-500 text-center">
        Job ID: {jobId}
      </p>
    </div>
  );
}
