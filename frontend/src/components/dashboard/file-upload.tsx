"use client";

import { useCallback, useRef, useState } from "react";
import { ALL_ACCEPTED } from "@/lib/constants";

interface Props {
  files: File[];
  onChange: (files: File[]) => void;
}

export default function FileUpload({ files, onChange }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

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
            ? "border-orange-500 bg-orange-500/5"
            : "border-[#333] hover:border-[#555]"
        }`}
      >
        <p className="text-gray-400 text-sm">
          Drop files here or click to browse
        </p>
        <p className="text-gray-500 text-xs mt-1">
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

      {files.length > 0 && (
        <div className="mt-3 space-y-1">
          {files.map((f, i) => (
            <div
              key={`${f.name}-${i}`}
              className="flex items-center justify-between text-sm text-gray-300 bg-[#1a1a1a] rounded px-3 py-1.5"
            >
              <span className="truncate">{f.name}</span>
              <button
                onClick={() => removeFile(i)}
                className="text-gray-500 hover:text-red-400 ml-2"
              >
                x
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
