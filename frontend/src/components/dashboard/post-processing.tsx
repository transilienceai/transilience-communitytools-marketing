"use client";

import { useState } from "react";
import { postProcess } from "@/lib/api";

interface Props {
  videoUrl: string;
  audioUrl: string;
  musicUrl: string;
  hasAudio: boolean;
  hasMusic: boolean;
}

export default function PostProcessing({
  videoUrl,
  audioUrl,
  musicUrl,
  hasAudio,
  hasMusic,
}: Props) {
  const [speed, setSpeed] = useState(1.0);
  const [voiceVolume, setVoiceVolume] = useState(5.0);
  const [musicVolume, setMusicVolume] = useState(0.03);
  const [applying, setApplying] = useState(false);
  const [resultVideoUrl, setResultVideoUrl] = useState<string | null>(null);

  const handleApply = async () => {
    setApplying(true);
    try {
      const videoRes = await fetch(videoUrl);
      const videoBlob = await videoRes.blob();

      const form = new FormData();
      form.append("video", new File([videoBlob], "video.mp4", { type: "video/mp4" }));
      form.append("video_speed", String(speed));
      form.append("voice_volume", String(voiceVolume));
      form.append("music_volume", String(musicVolume));

      if (hasAudio) {
        const audioRes = await fetch(audioUrl);
        if (audioRes.ok) {
          const audioBlob = await audioRes.blob();
          form.append("voice_audio", new File([audioBlob], "voice.mp3", { type: "audio/mpeg" }));
        }
      }

      if (hasMusic) {
        const musicRes = await fetch(musicUrl);
        if (musicRes.ok) {
          const musicBlob = await musicRes.blob();
          form.append("music_audio", new File([musicBlob], "music.mp3", { type: "audio/mpeg" }));
        }
      }

      const result = await postProcess(form);
      if (result.video) {
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

  const isModified = speed !== 1.0 || voiceVolume !== 5.0 || musicVolume !== 0.03;

  return (
    <div className="bg-[#141210] border border-[#3d3428] rounded-xl p-6 space-y-4">
      <h2 className="text-lg font-semibold text-[#f5f2ea]">Post-Processing</h2>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Speed */}
        <div>
          <label className="text-xs text-[#a09888]">
            Speed: {speed.toFixed(1)}x
          </label>
          <input
            type="range"
            min={0.5}
            max={2.0}
            step={0.1}
            value={speed}
            onChange={(e) => setSpeed(Number(e.target.value))}
            className="w-full mt-2 accent-[#d4b44e]"
          />
          <div className="flex justify-between text-xs text-[#7a7060] mt-1">
            <span>0.5x</span>
            <span>1.0x</span>
            <span>2.0x</span>
          </div>
        </div>

        {/* Voice Volume */}
        <div>
          <label className="text-xs text-[#a09888]">
            Voice Volume: {voiceVolume.toFixed(1)}
          </label>
          <input
            type="range"
            min={0}
            max={10}
            step={0.5}
            value={voiceVolume}
            onChange={(e) => setVoiceVolume(Number(e.target.value))}
            className="w-full mt-2 accent-[#d4b44e]"
          />
          <div className="flex justify-between text-xs text-[#7a7060] mt-1">
            <span>Mute</span>
            <span>5.0</span>
            <span>10.0</span>
          </div>
        </div>

        {/* Music Volume */}
        <div>
          <label className="text-xs text-[#a09888]">
            Music Volume: {musicVolume.toFixed(2)}
          </label>
          <input
            type="range"
            min={0}
            max={0.2}
            step={0.01}
            value={musicVolume}
            onChange={(e) => setMusicVolume(Number(e.target.value))}
            className="w-full mt-2 accent-[#d4b44e]"
          />
          <div className="flex justify-between text-xs text-[#7a7060] mt-1">
            <span>Mute</span>
            <span>0.03</span>
            <span>0.20</span>
          </div>
        </div>
      </div>

      <button
        onClick={handleApply}
        disabled={applying || !isModified}
        className="px-4 py-2 rounded-lg bg-gradient-to-r from-[#f5da6a] to-[#c9a84c] text-[#0a0a0a] text-sm font-medium disabled:opacity-40 hover:opacity-90 transition"
      >
        {applying ? "Applying..." : "Apply Changes"}
      </button>

      {resultVideoUrl && (
        <div className="space-y-3">
          <p className="text-sm text-[#f5f2ea]">Post-Processed Video:</p>
          <video src={resultVideoUrl} controls className="w-full rounded-lg" />
          <a
            href={resultVideoUrl}
            download="video_processed.mp4"
            className="inline-block px-4 py-2 rounded-lg bg-gradient-to-r from-[#f5da6a] to-[#c9a84c] text-[#0a0a0a] text-sm font-medium hover:opacity-90 transition"
          >
            Download Processed Video
          </a>
        </div>
      )}
    </div>
  );
}
