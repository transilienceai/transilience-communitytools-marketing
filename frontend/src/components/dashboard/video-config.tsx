"use client";

import { RESOLUTIONS } from "@/lib/constants";
import { useRef } from "react";

interface Props {
  product: string;
  onProductChange: (v: string) => void;
  tone: string;
  onToneChange: (v: string) => void;
  resolution: string;
  onResolutionChange: (v: string) => void;
  scriptDuration: number;
  onScriptDurationChange: (v: number) => void;
  storyline: string;
  onStorylineChange: (v: string) => void;
  generateMusic: boolean;
  onGenerateMusicChange: (v: boolean) => void;
  musicPrompt: string;
  onMusicPromptChange: (v: string) => void;
  generateIntro: boolean;
  onGenerateIntroChange: (v: boolean) => void;
  generateOutro: boolean;
  onGenerateOutroChange: (v: boolean) => void;
}

export default function VideoConfig(props: Props) {
  const storyFileRef = useRef<HTMLInputElement>(null);

  const handleStorylineFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      props.onStorylineChange(ev.target?.result as string);
    };
    reader.readAsText(file);
  };

  const sceneCount = Math.ceil(props.scriptDuration / 5);

  return (
    <div className="space-y-4">
      {/* Row 1: Product + Tone */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Field label="Product Name">
          <input
            value={props.product}
            onChange={(e) => props.onProductChange(e.target.value)}
            placeholder="My SaaS App"
            className="input-field"
          />
        </Field>
        <Field label="Tone">
          <input
            value={props.tone}
            onChange={(e) => props.onToneChange(e.target.value)}
            placeholder="professional and engaging"
            className="input-field"
          />
        </Field>
      </div>

      {/* Row 2: Resolution + Script Duration */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Field label="Resolution">
          <select
            value={props.resolution}
            onChange={(e) => props.onResolutionChange(e.target.value)}
            className="input-field"
          >
            {RESOLUTIONS.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </Field>
        <Field label={`Script Duration — ${sceneCount} scenes ~ ${sceneCount * 5}s video`}>
          <input
            type="number"
            value={props.scriptDuration}
            onChange={(e) => props.onScriptDurationChange(Number(e.target.value))}
            min={10}
            max={300}
            className="input-field"
          />
        </Field>
      </div>

      {/* Storyline */}
      <Field label="Storyline">
        <div className="flex gap-2">
          <textarea
            value={props.storyline}
            onChange={(e) => props.onStorylineChange(e.target.value)}
            placeholder="A small team discovers AI automation and scales to 10x productivity..."
            rows={3}
            className="input-field flex-1 resize-none"
          />
          <button
            onClick={() => storyFileRef.current?.click()}
            className="self-start px-2 py-2 rounded border border-[#333] text-gray-400 hover:text-white hover:border-orange-500 text-xs transition"
            title="Upload .txt/.md storyline file"
          >
            +
          </button>
          <input
            ref={storyFileRef}
            type="file"
            accept=".txt,.md"
            className="hidden"
            onChange={handleStorylineFile}
          />
        </div>
      </Field>

      {/* Toggles */}
      <div className="flex flex-wrap gap-6">
        <Toggle
          label="Generate Music"
          checked={props.generateMusic}
          onChange={props.onGenerateMusicChange}
        />
        <Toggle
          label="Intro Frame"
          checked={props.generateIntro}
          onChange={props.onGenerateIntroChange}
        />
        <Toggle
          label="Outro Frame"
          checked={props.generateOutro}
          onChange={props.onGenerateOutroChange}
        />
      </div>

      {/* Music prompt */}
      {props.generateMusic && (
        <Field label="Music Prompt">
          <input
            value={props.musicPrompt}
            onChange={(e) => props.onMusicPromptChange(e.target.value)}
            placeholder="upbeat corporate (auto-derived from tone if empty)"
            className="input-field"
          />
        </Field>
      )}
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-xs text-gray-400 mb-1">{label}</label>
      {children}
    </div>
  );
}

function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
      <div
        onClick={() => onChange(!checked)}
        className={`w-9 h-5 rounded-full transition relative ${
          checked ? "bg-orange-500" : "bg-[#333]"
        }`}
      >
        <div
          className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
            checked ? "translate-x-4" : "translate-x-0.5"
          }`}
        />
      </div>
      {label}
    </label>
  );
}
