"use client";

import { useCallback, useRef, useState } from "react";
import { ALL_ACCEPTED } from "@/lib/constants";
import ScreenRecorder from "./screen-recorder";
import MediaEditor from "./media-editor";

interface Props {
  files: File[];
  onChange: (files: File[]) => void;
  onRecordingChange?: (isRecording: boolean) => void;
  noVoiceoverFiles?: Set<string>;
  onNoVoiceoverChange?: (s: Set<string>) => void;
}

export default function FileUpload({ files, onChange, onRecordingChange, noVoiceoverFiles = new Set(), onNoVoiceoverChange }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);

  const toggleNoVoiceover = (fileName: string) => {
    if (!onNoVoiceoverChange) return;
    const next = new Set(noVoiceoverFiles);
    if (next.has(fileName)) next.delete(fileName);
    else next.add(fileName);
    onNoVoiceoverChange(next);
  };

  const addFiles = useCallback(
    (newFiles: FileList | File[]) => {
      const arr = Array.from(newFiles);
      onChange([...files, ...arr]);
    },
    [files, onChange]
  );

  const removeFile = (index: number) => {
    onChange(files.filter((_, i) => i !== index));
  };

  const canEdit = (f: File) =>
    f.type.startsWith("video/") || f.type.startsWith("image/");

  const handleEditorSave = (editedFiles: File[]) => {
    if (editingIndex === null) return;
    // Replace the edited file with the result(s)
    const updated = [...files];
    updated.splice(editingIndex, 1, ...editedFiles);
    onChange(updated);
    setEditingIndex(null);
  };

  return (
    <div>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
        }}
        onClick={() => inputRef.current?.click()}
        className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition ${
          dragging
            ? "border-[#d4b44e] bg-[#d4b44e]/5"
            : "border-[#3d3428] hover:border-[#d4b44e]/40"
        }`}
      >
        <p className="text-[#a09888] text-sm">
          Drop files here or click to browse
        </p>
        <p className="text-[#7a7060] text-xs mt-1">
          Images, Videos, PPT, PDF
        </p>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ALL_ACCEPTED}
          className="hidden"
          onChange={(e) => {
            if (e.target.files?.length) addFiles(e.target.files);
            e.target.value = "";
          }}
        />
      </div>

      {/* Screen Recorder */}
      <div className="mt-3">
        <ScreenRecorder
          onRecorded={(newFiles) => onChange([...files, ...newFiles])}
          onRecordingChange={onRecordingChange}
        />
      </div>

      {files.length > 0 && (
        <div className="mt-3 space-y-1">
          {files.map((f, i) => {
            const isVideo = f.type.startsWith("video/");
            const isMicTrack = f.name.startsWith("mic-recording-");
            const noVO = noVoiceoverFiles.has(f.name);
            return (
              <div
                key={`${f.name}-${i}`}
                className="bg-[#1a1814] rounded px-3 py-1.5 space-y-1"
              >
                <div className="flex items-center justify-between text-sm text-[#f5f2ea]">
                  <span className="truncate flex-1">{f.name}</span>
                  <div className="flex items-center gap-1 ml-2">
                    {canEdit(f) && (
                      <button
                        onClick={() => setEditingIndex(i)}
                        className="text-[#7a7060] hover:text-[#d4b44e] transition"
                        title="Edit (trim, split, crop)"
                      >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                        </svg>
                      </button>
                    )}
                    <button
                      onClick={() => removeFile(i)}
                      className="text-[#7a7060] hover:text-red-400"
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                </div>
                {/* No Voiceover toggle for video files */}
                {isVideo && !isMicTrack && (
                  <label className="flex items-center gap-2 text-[10px] text-[#7a7060] cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={noVO}
                      onChange={() => toggleNoVoiceover(f.name)}
                      className="accent-[#d4b44e] w-3 h-3"
                    />
                    <span className={noVO ? "text-[#d4b44e]" : ""}>
                      Keep original audio (no AI voiceover)
                    </span>
                  </label>
                )}
                {isMicTrack && (
                  <span className="text-[10px] text-[#7a7060]">Voiceover track — will replace mic audio only</span>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Media Editor Modal */}
      {editingIndex !== null && files[editingIndex] && (
        <MediaEditor
          file={files[editingIndex]}
          onSave={handleEditorSave}
          onCancel={() => setEditingIndex(null)}
        />
      )}
    </div>
  );
}
