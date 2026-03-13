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
  onStoryboardReady: (jobId: string) => void;
}

export default function StoryboardPanel({
  product,
  storyline,
  tone,
  style,
  onStoryboardReady,
}: Props) {
  const [url, setUrl] = useState("");
  const [scenes, setScenes] = useState(6);
  const [jobId, setJobId] = useState<string | null>(null);
  const [images, setImages] = useState<string[]>([]);
  const [generating, setGenerating] = useState(false);

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
      onError: () => setGenerating(false),
    }
  );

  const handleGenerate = async () => {
    if (!url) return;
    setGenerating(true);
    try {
      const form = new FormData();
      form.append("url", url);
      form.append("storyline", storyline);
      form.append("product", product);
      form.append("scenes", String(scenes));
      form.append("tone", tone);
      form.append("style", style);
      const id = await createStoryboard(form);
      setJobId(id);
    } catch (err) {
      alert(String(err));
      setGenerating(false);
    }
  };

  return (
    <div className="border border-[#333] rounded-lg p-4 space-y-3">
      <p className="text-xs text-gray-400 font-medium">
        Or generate from a website URL
      </p>
      <div className="flex gap-2">
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://example.com"
          className="input-field flex-1"
        />
        <input
          type="number"
          value={scenes}
          onChange={(e) => setScenes(Number(e.target.value))}
          min={3}
          max={15}
          className="input-field w-20"
          title="Number of scenes"
        />
        <button
          onClick={handleGenerate}
          disabled={!url || generating}
          className="px-4 py-2 rounded-lg bg-gradient-to-r from-orange-500 to-pink-500 text-white text-sm font-medium disabled:opacity-40 hover:opacity-90 transition whitespace-nowrap"
        >
          {generating ? "Generating..." : "Storyboard"}
        </button>
      </div>

      {isPolling && data && (
        <p className="text-xs text-gray-500">
          {data.state === "running" ? "Crawling & generating..." : data.state}
        </p>
      )}

      {images.length > 0 && jobId && (
        <div className="grid grid-cols-3 md:grid-cols-6 gap-2 mt-2">
          {images.map((filename) => (
            <img
              key={filename}
              src={storyboardImageUrl(jobId, filename)}
              alt={filename}
              className="rounded border border-[#333] w-full aspect-video object-cover"
            />
          ))}
        </div>
      )}
    </div>
  );
}
