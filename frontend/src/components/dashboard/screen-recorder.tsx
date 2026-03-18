"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  saveRecording,
  getRecordings,
  deleteRecording,
  type CachedRecording,
} from "@/lib/recording-cache";

interface Props {
  onRecorded: (files: File[]) => void;
  onRecordingChange?: (isRecording: boolean) => void;
}

type RecordingState = "idle" | "recording" | "paused" | "preview";

export default function ScreenRecorder({ onRecorded, onRecordingChange }: Props) {
  const [state, setState] = useState<RecordingState>("idle");
  const [duration, setDuration] = useState(0);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [micPreviewUrl, setMicPreviewUrl] = useState<string | null>(null);
  const [recordedFile, setRecordedFile] = useState<File | null>(null);
  const [micFile, setMicFile] = useState<File | null>(null);
  const [includeAudio, setIncludeAudio] = useState(true);
  const [includeMic, setIncludeMic] = useState(false);
  const [rerecordingMic, setRerecordingMic] = useState(false);
  const [cached, setCached] = useState<CachedRecording[]>([]);
  const [showCached, setShowCached] = useState(false);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const micRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const micChunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const micStreamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const previewVideoRef = useRef<HTMLVideoElement>(null);

  // Re-record mic refs
  const rerecordMicStreamRef = useRef<MediaStream | null>(null);
  const rerecordMicRecorderRef = useRef<MediaRecorder | null>(null);
  const rerecordMicChunksRef = useRef<Blob[]>([]);

  const loadCached = useCallback(async () => {
    try {
      const recs = await getRecordings();
      setCached(recs);
    } catch {
      // IndexedDB not available
    }
  }, []);

  useEffect(() => {
    loadCached();
    return () => {
      stopAllStreams();
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      if (micPreviewUrl) URL.revokeObjectURL(micPreviewUrl);
      if (timerRef.current) clearInterval(timerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const stopAllStreams = () => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    micStreamRef.current?.getTracks().forEach((t) => t.stop());
    rerecordMicStreamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    micStreamRef.current = null;
    rerecordMicStreamRef.current = null;
  };

  const startTimer = () => {
    setDuration(0);
    timerRef.current = setInterval(() => setDuration((d) => d + 1), 1000);
  };

  const stopTimer = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  };

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60).toString().padStart(2, "0");
    const s = (secs % 60).toString().padStart(2, "0");
    return `${m}:${s}`;
  };

  const formatDate = (ts: number) => {
    const d = new Date(ts);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    return d.toLocaleDateString();
  };

  const handleStart = useCallback(async () => {
    try {
      const displayStream = await navigator.mediaDevices.getDisplayMedia({
        video: { frameRate: 30 },
        audio: includeAudio,
      });

      // Main recording: screen video + system audio only
      const tracks: MediaStreamTrack[] = [...displayStream.getVideoTracks()];
      const systemAudioTracks = displayStream.getAudioTracks();
      if (systemAudioTracks.length > 0) {
        tracks.push(...systemAudioTracks);
      }

      const combinedStream = new MediaStream(tracks);
      streamRef.current = displayStream;

      displayStream.getVideoTracks()[0].addEventListener("ended", () => {
        handleStop();
      });

      // Main recorder — screen + system audio
      chunksRef.current = [];
      const recorder = new MediaRecorder(combinedStream, {
        mimeType: MediaRecorder.isTypeSupported("video/webm;codecs=vp9,opus")
          ? "video/webm;codecs=vp9,opus"
          : "video/webm",
      });

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      const timestamp = new Date().toISOString().slice(0, 19).replace(/[T:]/g, "-");

      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: "video/webm" });
        const url = URL.createObjectURL(blob);
        if (previewUrl) URL.revokeObjectURL(previewUrl);
        setPreviewUrl(url);

        const file = new File([blob], `screen-recording-${timestamp}.webm`, { type: "video/webm" });
        setRecordedFile(file);
        setState("preview");
        onRecordingChange?.(false);
        stopTimer();
        stopAllStreams();
      };

      mediaRecorderRef.current = recorder;

      // Separate mic recorder (if enabled)
      if (includeMic) {
        try {
          const micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
          micStreamRef.current = micStream;

          micChunksRef.current = [];
          const micRecorder = new MediaRecorder(micStream, {
            mimeType: MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
              ? "audio/webm;codecs=opus"
              : "audio/webm",
          });

          micRecorder.ondataavailable = (e) => {
            if (e.data.size > 0) micChunksRef.current.push(e.data);
          };

          micRecorder.onstop = () => {
            const micBlob = new Blob(micChunksRef.current, { type: "audio/webm" });
            const micUrl = URL.createObjectURL(micBlob);
            if (micPreviewUrl) URL.revokeObjectURL(micPreviewUrl);
            setMicPreviewUrl(micUrl);

            const mf = new File([micBlob], `mic-recording-${timestamp}.webm`, { type: "audio/webm" });
            setMicFile(mf);
          };

          micRecorderRef.current = micRecorder;
          micRecorder.start(1000);
        } catch {
          // Mic denied — continue without
        }
      }

      recorder.start(1000);
      setState("recording");
      onRecordingChange?.(true);
      startTimer();
    } catch (err) {
      console.error("Screen recording failed:", err);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [includeAudio, includeMic]);

  const handleStop = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }
    if (micRecorderRef.current && micRecorderRef.current.state !== "inactive") {
      micRecorderRef.current.stop();
    }
  }, []);

  const handlePause = () => {
    if (mediaRecorderRef.current?.state === "recording") {
      mediaRecorderRef.current.pause();
      micRecorderRef.current?.pause();
      setState("paused");
      stopTimer();
    }
  };

  const handleResume = () => {
    if (mediaRecorderRef.current?.state === "paused") {
      mediaRecorderRef.current.resume();
      micRecorderRef.current?.resume();
      setState("recording");
      timerRef.current = setInterval(() => setDuration((d) => d + 1), 1000);
    }
  };

  const handleUse = async () => {
    if (recordedFile) {
      await saveRecording(recordedFile, duration);
      loadCached();
      const files: File[] = [recordedFile];
      if (micFile) files.push(micFile);
      onRecorded(files);
      handleDiscard();
    }
  };

  const handleDiscard = () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    if (micPreviewUrl) URL.revokeObjectURL(micPreviewUrl);
    setPreviewUrl(null);
    setMicPreviewUrl(null);
    setRecordedFile(null);
    setMicFile(null);
    setDuration(0);
    setState("idle");
    setRerecordingMic(false);
  };

  const handleRemoveMic = () => {
    if (micPreviewUrl) URL.revokeObjectURL(micPreviewUrl);
    setMicPreviewUrl(null);
    setMicFile(null);
  };

  const handleStartRerecordMic = async () => {
    try {
      const micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      rerecordMicStreamRef.current = micStream;

      rerecordMicChunksRef.current = [];
      const micRecorder = new MediaRecorder(micStream, {
        mimeType: MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
          ? "audio/webm;codecs=opus"
          : "audio/webm",
      });

      micRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) rerecordMicChunksRef.current.push(e.data);
      };

      micRecorder.onstop = () => {
        const micBlob = new Blob(rerecordMicChunksRef.current, { type: "audio/webm" });
        const micUrl = URL.createObjectURL(micBlob);
        if (micPreviewUrl) URL.revokeObjectURL(micPreviewUrl);
        setMicPreviewUrl(micUrl);

        const timestamp = new Date().toISOString().slice(0, 19).replace(/[T:]/g, "-");
        const mf = new File([micBlob], `mic-recording-${timestamp}.webm`, { type: "audio/webm" });
        setMicFile(mf);
        setRerecordingMic(false);
        rerecordMicStreamRef.current?.getTracks().forEach((t) => t.stop());
        rerecordMicStreamRef.current = null;
      };

      rerecordMicRecorderRef.current = micRecorder;
      micRecorder.start(1000);
      setRerecordingMic(true);

      // Play the screen recording while re-recording mic so user can narrate along
      if (previewVideoRef.current) {
        previewVideoRef.current.currentTime = 0;
        previewVideoRef.current.play();
      }
    } catch {
      // Mic denied
    }
  };

  const handleStopRerecordMic = () => {
    if (rerecordMicRecorderRef.current && rerecordMicRecorderRef.current.state !== "inactive") {
      rerecordMicRecorderRef.current.stop();
    }
    if (previewVideoRef.current) {
      previewVideoRef.current.pause();
    }
  };

  const handleUseCached = (rec: CachedRecording) => {
    const file = new File([rec.blob], rec.name, { type: rec.blob.type });
    onRecorded([file]);
  };

  const handleDeleteCached = async (id: string) => {
    await deleteRecording(id);
    loadCached();
  };

  return (
    <div className="border border-[#3d3428] rounded-xl p-4 space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-[#d4b44e]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
          </svg>
          <span className="text-sm font-medium text-[#f5f2ea]">Screen Recorder</span>
          {cached.length > 0 && state === "idle" && (
            <button
              onClick={() => setShowCached(!showCached)}
              className="text-xs text-[#7a7060] hover:text-[#d4b44e] transition ml-2"
            >
              {showCached ? "Hide" : "Show"} previous ({cached.length})
            </button>
          )}
        </div>

        {state === "recording" && (
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
            <span className="text-sm font-mono text-red-400">{formatTime(duration)}</span>
          </div>
        )}
        {state === "paused" && (
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-yellow-500" />
            <span className="text-sm font-mono text-yellow-400">{formatTime(duration)} (paused)</span>
          </div>
        )}
      </div>

      {/* Audio options (only before recording) */}
      {state === "idle" && (
        <div className="flex flex-wrap gap-4">
          <label className="flex items-center gap-2 text-xs text-[#a09888]">
            <input
              type="checkbox"
              checked={includeAudio}
              onChange={(e) => setIncludeAudio(e.target.checked)}
              className="accent-[#d4b44e]"
            />
            System audio
          </label>
          <label className="flex items-center gap-2 text-xs text-[#a09888]">
            <input
              type="checkbox"
              checked={includeMic}
              onChange={(e) => setIncludeMic(e.target.checked)}
              className="accent-[#d4b44e]"
            />
            Microphone
          </label>
        </div>
      )}

      {/* Controls */}
      <div className="flex flex-wrap gap-2">
        {state === "idle" && (
          <button
            onClick={handleStart}
            className="px-4 py-2 rounded-lg bg-gradient-to-r from-[#f5da6a] to-[#c9a84c] text-[#0a0a0a] text-sm font-medium hover:opacity-90 transition"
          >
            Start Recording
          </button>
        )}

        {state === "recording" && (
          <>
            <button
              onClick={handlePause}
              className="px-4 py-2 rounded-lg border border-[#d4b44e]/40 text-sm text-[#d4b44e] hover:bg-[#d4b44e]/10 transition"
            >
              Pause
            </button>
            <button
              onClick={handleStop}
              className="px-4 py-2 rounded-lg bg-red-500/80 text-white text-sm font-medium hover:bg-red-500 transition"
            >
              Stop
            </button>
          </>
        )}

        {state === "paused" && (
          <>
            <button
              onClick={handleResume}
              className="px-4 py-2 rounded-lg border border-[#d4b44e]/40 text-sm text-[#d4b44e] hover:bg-[#d4b44e]/10 transition"
            >
              Resume
            </button>
            <button
              onClick={handleStop}
              className="px-4 py-2 rounded-lg bg-red-500/80 text-white text-sm font-medium hover:bg-red-500 transition"
            >
              Stop
            </button>
          </>
        )}

        {state === "preview" && !rerecordingMic && (
          <>
            <button
              onClick={handleUse}
              className="px-4 py-2 rounded-lg bg-gradient-to-r from-[#f5da6a] to-[#c9a84c] text-[#0a0a0a] text-sm font-medium hover:opacity-90 transition"
            >
              Use Recording
            </button>
            {previewUrl && recordedFile && (
              <a
                href={previewUrl}
                download={recordedFile.name}
                className="px-4 py-2 rounded-lg border border-[#3d3428] text-sm text-[#a09888] hover:border-[#d4b44e] hover:text-[#f5f2ea] transition"
              >
                Download
              </a>
            )}
            <button
              onClick={handleDiscard}
              className="px-4 py-2 rounded-lg border border-[#3d3428] text-sm text-[#a09888] hover:border-red-400 hover:text-red-400 transition"
            >
              Discard
            </button>
          </>
        )}
      </div>

      {/* Preview */}
      {state === "preview" && previewUrl && (
        <div className="rounded-lg overflow-hidden border border-[#3d3428] bg-black">
          <video
            ref={previewVideoRef}
            src={previewUrl}
            controls
            className="w-full max-h-64 object-contain"
          />
        </div>
      )}

      {/* Mic audio track (separate) */}
      {state === "preview" && (
        <div className="border border-[#3d3428] rounded-lg p-3 space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <svg className="w-3.5 h-3.5 text-[#a09888]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
              </svg>
              <span className="text-xs font-medium text-[#f5f2ea]">
                Voiceover Track
              </span>
              {micFile && (
                <span className="text-[10px] text-[#7a7060]">
                  ({(micFile.size / 1024).toFixed(0)} KB)
                </span>
              )}
            </div>
            <div className="flex items-center gap-1.5">
              {!rerecordingMic && (
                <>
                  <button
                    onClick={handleStartRerecordMic}
                    className="text-xs px-2 py-1 rounded border border-[#3d3428] text-[#a09888] hover:border-[#d4b44e] hover:text-[#d4b44e] transition"
                  >
                    {micFile ? "Re-record" : "Record"}
                  </button>
                  {micFile && (
                    <button
                      onClick={handleRemoveMic}
                      className="text-xs px-2 py-1 rounded border border-[#3d3428] text-[#a09888] hover:border-red-400 hover:text-red-400 transition"
                    >
                      Remove
                    </button>
                  )}
                </>
              )}
              {rerecordingMic && (
                <button
                  onClick={handleStopRerecordMic}
                  className="text-xs px-2 py-1 rounded bg-red-500/80 text-white font-medium hover:bg-red-500 transition flex items-center gap-1.5"
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
                  Stop Recording
                </button>
              )}
            </div>
          </div>

          {micPreviewUrl && !rerecordingMic && (
            <audio src={micPreviewUrl} controls className="w-full h-8" />
          )}

          {!micFile && !rerecordingMic && (
            <p className="text-[10px] text-[#7a7060]">
              No voiceover — click Record to narrate over the video. System audio is preserved separately.
            </p>
          )}

          {rerecordingMic && (
            <p className="text-[10px] text-[#d4b44e] animate-pulse">
              Recording voiceover — video is playing for reference...
            </p>
          )}
        </div>
      )}

      {/* Previous Recordings */}
      {showCached && cached.length > 0 && state === "idle" && (
        <div className="space-y-2 border-t border-[#3d3428] pt-3">
          <p className="text-xs text-[#7a7060] font-medium">Previous Recordings</p>
          {cached.map((rec) => (
            <CachedRecordingItem
              key={rec.id}
              rec={rec}
              formatTime={formatTime}
              formatDate={formatDate}
              onUse={handleUseCached}
              onDelete={handleDeleteCached}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function CachedRecordingItem({
  rec,
  formatTime,
  formatDate,
  onUse,
  onDelete,
}: {
  rec: CachedRecording;
  formatTime: (s: number) => string;
  formatDate: (ts: number) => string;
  onUse: (rec: CachedRecording) => void;
  onDelete: (id: string) => void;
}) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  const togglePreview = () => {
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
      setPreviewUrl(null);
    } else {
      setPreviewUrl(URL.createObjectURL(rec.blob));
    }
  };

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const downloadUrl = URL.createObjectURL(rec.blob);

  return (
    <div className="bg-[#1a1814] border border-[#3d3428] rounded-lg p-3 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-xs text-[#f5f2ea] truncate max-w-[200px]">{rec.name}</span>
          <span className="text-xs text-[#7a7060]">{formatTime(rec.duration)}</span>
          <span className="text-xs text-[#7a7060]">{formatDate(rec.timestamp)}</span>
          <span className="text-xs text-[#7a7060]">{(rec.blob.size / 1024 / 1024).toFixed(1)} MB</span>
        </div>
        <div className="flex items-center gap-1.5">
          <button
            onClick={togglePreview}
            className="text-xs px-2 py-1 rounded border border-[#3d3428] text-[#a09888] hover:border-[#d4b44e] hover:text-[#d4b44e] transition"
          >
            {previewUrl ? "Hide" : "Preview"}
          </button>
          <button
            onClick={() => onUse(rec)}
            className="text-xs px-2 py-1 rounded bg-gradient-to-r from-[#f5da6a] to-[#c9a84c] text-[#0a0a0a] font-medium hover:opacity-90 transition"
          >
            Use
          </button>
          <a
            href={downloadUrl}
            download={rec.name}
            className="text-xs px-2 py-1 rounded border border-[#3d3428] text-[#a09888] hover:border-[#d4b44e] hover:text-[#f5f2ea] transition"
          >
            Download
          </a>
          <button
            onClick={() => onDelete(rec.id)}
            className="text-[#7a7060] hover:text-red-400 transition"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {previewUrl && (
        <div className="rounded overflow-hidden border border-[#3d3428] bg-black">
          <video src={previewUrl} controls className="w-full max-h-48 object-contain" />
        </div>
      )}
    </div>
  );
}
