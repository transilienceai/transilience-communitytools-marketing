"use client";

import { STYLES } from "@/lib/constants";
import { sampleVideoUrl } from "@/lib/api";
import type { VideoStyle } from "@/lib/types";
import { useRef, useState } from "react";

interface Props {
  value: VideoStyle;
  onChange: (style: VideoStyle) => void;
}

export default function StylePicker({ value, onChange }: Props) {
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
  onClick,
}: {
  id: string;
  name: string;
  description: string;
  icon: string;
  selected: boolean;
  onClick: () => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [showVideo, setShowVideo] = useState(false);

  return (
    <div
      onClick={onClick}
      className={`relative cursor-pointer rounded-xl p-5 border transition ${
        selected
          ? "border-[#d4b44e] bg-[#d4b44e]/5"
          : "border-[#3d3428] bg-[#1a1814] hover:border-[#3d3428]"
      }`}
    >
      <svg
        className="w-6 h-6 mb-3 text-[#d4b44e]"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
      >
        <path strokeLinecap="round" strokeLinejoin="round" d={icon} />
      </svg>
      <h3 className="font-semibold mb-1 text-[#f5f2ea]">{name}</h3>
      <p className="text-xs text-[#a09888]">{description}</p>

      <button
        onClick={(e) => {
          e.stopPropagation();
          setShowVideo(!showVideo);
        }}
        className="mt-3 text-xs text-[#d4b44e] hover:text-[#e8c54d] transition"
      >
        {showVideo ? "Hide Preview" : "Watch Sample"}
      </button>

      {showVideo && (
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
