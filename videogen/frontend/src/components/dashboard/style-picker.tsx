"use client";

import { STYLES } from "@/lib/constants";
import { sampleVideoUrl } from "@/lib/api";
import type { VideoStyle } from "@/lib/types";
import { useEffect, useRef, useState } from "react";

interface Props {
  value: VideoStyle;
  onChange: (style: VideoStyle) => void;
}

export default function StylePicker({ value, onChange }: Props) {
  const [sampleAvail, setSampleAvail] = useState<Record<string, boolean>>({});

  useEffect(() => {
    STYLES.forEach(({ id }) => {
      fetch(sampleVideoUrl(id), { method: "HEAD" })
        .then((r) => setSampleAvail((prev) => ({ ...prev, [id]: r.ok })))
        .catch(() => {});
    });
  }, []);

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {STYLES.map((s) => (
        <StyleCard
          key={s.id}
          id={s.id}
          name={s.name}
          description={s.description}
          icon={s.icon}
          selected={value === s.id}
          hasSample={!!sampleAvail[s.id]}
          onClick={() => onChange(s.id)}
        />
      ))}
    </div>
  );
}

function StyleCard({
  id,
  name,
  description,
  icon,
  selected,
  hasSample,
  onClick,
}: {
  id: string;
  name: string;
  description: string;
  icon: string;
  selected: boolean;
  hasSample: boolean;
  onClick: () => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [showVideo, setShowVideo] = useState(false);

  return (
    <div
      onClick={onClick}
      className={`relative cursor-pointer rounded-xl p-5 border transition ${
        selected
          ? "border-orange-500 bg-orange-500/5"
          : "border-[#333] bg-[#1a1a1a] hover:border-[#555]"
      }`}
    >
      <svg
        className="w-6 h-6 mb-3 text-orange-400"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
      >
        <path strokeLinecap="round" strokeLinejoin="round" d={icon} />
      </svg>
      <h3 className="font-semibold mb-1">{name}</h3>
      <p className="text-xs text-gray-400">{description}</p>

      {hasSample && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            setShowVideo(!showVideo);
          }}
          className="mt-3 text-xs text-orange-400 hover:text-orange-300 transition"
        >
          {showVideo ? "Hide Preview" : "Watch Sample"}
        </button>
      )}

      {showVideo && hasSample && (
        <video
          ref={videoRef}
          src={sampleVideoUrl(id)}
          controls
          className="mt-2 w-full rounded-lg"
          autoPlay
          muted
        />
      )}
    </div>
  );
}
