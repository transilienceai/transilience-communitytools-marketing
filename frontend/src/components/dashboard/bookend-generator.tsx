"use client";

import { useCallback, useState } from "react";
import {
  bookendImageUrl,
  createBookends,
  getBookendStatus,
} from "@/lib/api";
import { usePolling } from "@/hooks/use-polling";
import type { BookendOption } from "@/lib/types";

interface Props {
  product: string;
  storyline: string;
  tone: string;
  style: string;
  generateIntro: boolean;
  generateOutro: boolean;
  onBookendReady: (
    jobId: string,
    introOption: number,
    outroOption: number,
    introVeoPrompt: string,
    outroVeoPrompt: string
  ) => void;
}

export default function BookendGenerator({
  product,
  storyline,
  tone,
  style,
  generateIntro,
  generateOutro,
  onBookendReady,
}: Props) {
  const [jobId, setJobId] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [introPrompt, setIntroPrompt] = useState("");
  const [outroPrompt, setOutroPrompt] = useState("");
  const [introRef, setIntroRef] = useState<File | null>(null);
  const [outroRef, setOutroRef] = useState<File | null>(null);

  const [introOptions, setIntroOptions] = useState<BookendOption[]>([]);
  const [outroOptions, setOutroOptions] = useState<BookendOption[]>([]);
  const [selectedIntro, setSelectedIntro] = useState(0);
  const [selectedOutro, setSelectedOutro] = useState(0);

  const fetcher = useCallback(
    () => (jobId ? getBookendStatus(jobId) : Promise.reject()),
    [jobId]
  );

  usePolling(jobId ? fetcher : null, 3000, {
    onDone: (d) => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const result = (d as any).result;
      if (result?.intro_options) setIntroOptions(result.intro_options);
      if (result?.outro_options) setOutroOptions(result.outro_options);
      setGenerating(false);
    },
    onError: () => setGenerating(false),
  });

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const form = new FormData();
      form.append("product", product);
      form.append("storyline", storyline);
      form.append("tone", tone);
      form.append("style", style);
      form.append("generate_intro", String(generateIntro));
      form.append("generate_outro", String(generateOutro));
      if (introPrompt) form.append("intro_prompt", introPrompt);
      if (outroPrompt) form.append("outro_prompt", outroPrompt);
      if (introRef) form.append("intro_ref", introRef);
      if (outroRef) form.append("outro_ref", outroRef);

      const id = await createBookends(form);
      setJobId(id);
    } catch (err) {
      alert(String(err));
      setGenerating(false);
    }
  };

  const handleConfirm = () => {
    if (!jobId) return;
    const introVeo = introOptions[selectedIntro]?.veo_motion_prompt ?? "";
    const outroVeo = outroOptions[selectedOutro]?.veo_motion_prompt ?? "";
    onBookendReady(jobId, selectedIntro, selectedOutro, introVeo, outroVeo);
  };

  const hasResults = introOptions.length > 0 || outroOptions.length > 0;

  return (
    <div className="space-y-4">
      {/* Prompts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {generateIntro && (
          <div className="space-y-2">
            <label className="text-xs text-gray-400">Intro Prompt (optional)</label>
            <input
              value={introPrompt}
              onChange={(e) => setIntroPrompt(e.target.value)}
              placeholder="Clean gradient with logo..."
              className="input-field"
            />
            <input
              type="file"
              accept="image/*"
              onChange={(e) => setIntroRef(e.target.files?.[0] ?? null)}
              className="text-xs text-gray-500"
            />
          </div>
        )}
        {generateOutro && (
          <div className="space-y-2">
            <label className="text-xs text-gray-400">Outro Prompt (optional)</label>
            <input
              value={outroPrompt}
              onChange={(e) => setOutroPrompt(e.target.value)}
              placeholder="CTA with warm tones..."
              className="input-field"
            />
            <input
              type="file"
              accept="image/*"
              onChange={(e) => setOutroRef(e.target.files?.[0] ?? null)}
              className="text-xs text-gray-500"
            />
          </div>
        )}
      </div>

      <button
        onClick={handleGenerate}
        disabled={generating}
        className="px-4 py-2 rounded-lg bg-gradient-to-r from-orange-500 to-pink-500 text-white text-sm font-medium disabled:opacity-40 hover:opacity-90 transition"
      >
        {generating ? "Generating Frames..." : "Generate Frame Options"}
      </button>

      {/* Intro Gallery */}
      {introOptions.length > 0 && jobId && (
        <OptionGallery
          title="Intro Options"
          options={introOptions}
          jobId={jobId}
          selected={selectedIntro}
          onSelect={setSelectedIntro}
        />
      )}

      {/* Outro Gallery */}
      {outroOptions.length > 0 && jobId && (
        <OptionGallery
          title="Outro Options"
          options={outroOptions}
          jobId={jobId}
          selected={selectedOutro}
          onSelect={setSelectedOutro}
        />
      )}

      {hasResults && (
        <button
          onClick={handleConfirm}
          className="px-4 py-2 rounded-lg border border-orange-500 text-orange-400 text-sm font-medium hover:bg-orange-500/10 transition"
        >
          Confirm Selection
        </button>
      )}
    </div>
  );
}

function OptionGallery({
  title,
  options,
  jobId,
  selected,
  onSelect,
}: {
  title: string;
  options: BookendOption[];
  jobId: string;
  selected: number;
  onSelect: (i: number) => void;
}) {
  return (
    <div>
      <p className="text-sm text-gray-300 mb-2">{title}</p>
      <div className="grid grid-cols-3 gap-3">
        {options.map((opt, i) => (
          <div
            key={i}
            onClick={() => onSelect(i)}
            className={`cursor-pointer rounded-lg border overflow-hidden transition ${
              selected === i
                ? "border-orange-500 ring-1 ring-orange-500"
                : "border-[#333] hover:border-[#555]"
            }`}
          >
            <img
              src={bookendImageUrl(jobId, opt.image_filename)}
              alt={opt.title_text}
              className="w-full aspect-video object-cover"
            />
            <div className="p-2">
              <p className="text-xs font-medium truncate">{opt.title_text}</p>
              <p className="text-xs text-gray-500 truncate">
                {opt.subtitle_text}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
