"use client";

import { useEffect, useState } from "react";
import { cloneVoice, fetchVoices } from "@/lib/api";
import type { Voice } from "@/lib/types";

interface Props {
  value: string;
  onChange: (voice: string) => void;
}

export default function VoiceSelector({ value, onChange }: Props) {
  const [voices, setVoices] = useState<Voice[]>([]);
  const [loading, setLoading] = useState(true);
  const [showClone, setShowClone] = useState(false);
  const [cloning, setCloning] = useState(false);

  // Clone form
  const [cloneName, setCloneName] = useState("");
  const [cloneFiles, setCloneFiles] = useState<File[]>([]);
  const [cloneAccent, setCloneAccent] = useState("");
  const [cloneGender, setCloneGender] = useState("");

  useEffect(() => {
    fetchVoices()
      .then(setVoices)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleClone = async () => {
    if (!cloneName || cloneFiles.length === 0) return;
    setCloning(true);
    try {
      const form = new FormData();
      form.append("name", cloneName);
      cloneFiles.forEach((f) => form.append("audio_files", f));
      if (cloneAccent) form.append("accent", cloneAccent);
      if (cloneGender) form.append("gender", cloneGender);

      const result = await cloneVoice(form);
      setVoices((prev) => [
        { name: result.name, category: "cloned", voice_id: result.voice_id },
        ...prev,
      ]);
      onChange(result.name);
      setShowClone(false);
      setCloneName("");
      setCloneFiles([]);
    } catch (err) {
      alert(String(err));
    } finally {
      setCloning(false);
    }
  };

  const cloned = voices.filter((v) => v.category === "cloned");
  const premade = voices.filter((v) => v.category === "premade");

  return (
    <div className="space-y-3">
      <div className="flex gap-3 items-center">
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={loading}
          className="flex-1 bg-[#1a1a1a] border border-[#333] rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-orange-500"
        >
          {loading && <option>Loading voices...</option>}
          {cloned.length > 0 && (
            <optgroup label="Cloned Voices">
              {cloned.map((v) => (
                <option key={`${v.name}-${v.voice_id ?? v.category}`} value={v.name}>
                  {v.name}
                </option>
              ))}
            </optgroup>
          )}
          {premade.length > 0 && (
            <optgroup label="Premade Voices">
              {premade.map((v) => (
                <option key={`${v.name}-${v.voice_id ?? v.category}`} value={v.name}>
                  {v.name}
                </option>
              ))}
            </optgroup>
          )}
        </select>
        <button
          onClick={() => setShowClone(!showClone)}
          className="text-xs px-3 py-2 rounded-lg border border-[#333] text-gray-400 hover:text-white hover:border-orange-500 transition"
        >
          {showClone ? "Cancel" : "+ Clone Voice"}
        </button>
      </div>

      {showClone && (
        <div className="bg-[#1a1a1a] border border-[#333] rounded-lg p-4 space-y-3">
          <input
            placeholder="Voice name"
            value={cloneName}
            onChange={(e) => setCloneName(e.target.value)}
            className="w-full bg-[#0f0f0f] border border-[#333] rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-orange-500"
          />
          <input
            type="file"
            accept="audio/*"
            multiple
            onChange={(e) => {
              if (e.target.files) setCloneFiles(Array.from(e.target.files));
            }}
            className="text-sm text-gray-400"
          />
          <div className="flex gap-2">
            <input
              placeholder="Accent (optional)"
              value={cloneAccent}
              onChange={(e) => setCloneAccent(e.target.value)}
              className="flex-1 bg-[#0f0f0f] border border-[#333] rounded px-3 py-1.5 text-sm text-gray-200 focus:outline-none"
            />
            <select
              value={cloneGender}
              onChange={(e) => setCloneGender(e.target.value)}
              className="bg-[#0f0f0f] border border-[#333] rounded px-3 py-1.5 text-sm text-gray-200 focus:outline-none"
            >
              <option value="">Gender</option>
              <option value="male">Male</option>
              <option value="female">Female</option>
            </select>
          </div>
          <button
            onClick={handleClone}
            disabled={cloning || !cloneName || cloneFiles.length === 0}
            className="w-full py-2 rounded-lg bg-gradient-to-r from-orange-500 to-pink-500 text-white text-sm font-medium disabled:opacity-40 hover:opacity-90 transition"
          >
            {cloning ? "Cloning..." : "Clone Voice"}
          </button>
        </div>
      )}
    </div>
  );
}
