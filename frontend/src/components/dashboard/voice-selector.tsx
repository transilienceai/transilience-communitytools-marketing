"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { cloneVoice, fetchVoices } from "@/lib/api";
import type { Voice } from "@/lib/types";

// 120-second reading scripts — rotated randomly
const READING_SCRIPTS = [
  `The morning sun cast long golden shadows across the quiet village square. Maria stepped out of her bakery, wiping flour from her hands, and breathed in the cool autumn air. For twenty years she had opened this shop at exactly five thirty, long before anyone else stirred. The routine was her anchor.

Today felt different though. A letter had arrived the previous evening — thick cream paper, an unfamiliar seal. Inside, a single paragraph explained that a distant relative had left her a small vineyard in southern France. She read it three times, certain it was a mistake.

But it wasn't. By afternoon she was on the phone with a lawyer in Marseille who confirmed every detail. The vineyard produced a modest Grenache, nothing famous, but it had been in the family for generations. The catch: she had to visit within thirty days or forfeit the inheritance.

Maria looked around her bakery — the worn wooden counter, the brass bell above the door, the chalkboard menu she rewrote every morning. Could she really leave, even for a week? Her assistant Jules could manage the ovens, and her regulars would survive without her croissants for a few days. Probably.

She booked a flight that evening. As the confirmation email arrived, she felt something she hadn't felt in years — the thrill of the completely unknown. Tomorrow the baguettes would rise without her, and she would be thirty thousand feet above the Atlantic, heading toward a life she never expected.`,

  `There is a peculiar silence that exists only in libraries after midnight. Professor Chen knew it well. For eleven years he had worked in the archives of the Blackwood Institute, cataloguing manuscripts that most scholars had forgotten existed.

Tonight he was examining a leather-bound journal from eighteen forty-two. The author, a ship captain named Elias Drummond, had documented his voyages across the Indian Ocean with meticulous detail — wind speeds, star positions, crew morale, and cargo manifests. Standard fare for the era.

But on page one hundred and seventeen, the entries changed. Drummond described discovering an island that appeared on no chart. He spent three days exploring its interior, finding ruins of a civilization he could not identify. The stone carvings depicted astronomical events — eclipses, comets, planetary alignments — with startling accuracy.

Chen adjusted his reading lamp and leaned closer. Drummond had sketched several of the carvings. One showed a spiral pattern radiating from a central point, surrounded by smaller circles at precise intervals. It looked remarkably like a modern diagram of gravitational waves, a concept that wouldn't be theorized for another seventy years.

He photographed the pages carefully, then closed the journal. The rational part of his mind offered explanations: coincidence, projection, misinterpretation. But the scholar in him — the part that had devoted his life to finding truth in old paper — felt the unmistakable pulse of something genuinely extraordinary.`,

  `Rain hammered against the windows of the control room as Anika checked the satellite feed for the third time. The hurricane had shifted course overnight, defying every model they had run. Instead of curving northeast toward open water, it was heading straight for the coast.

She picked up the phone and called Director Okafor. His voice was calm, as always. He had been through nineteen hurricane seasons and never once raised his voice during a crisis. That steadiness was contagious — within minutes of his arrival, the entire team operated with renewed focus.

The data was clear: landfall in approximately fourteen hours. Wind speeds exceeding one hundred and forty miles per hour. Storm surge projections showed flooding up to twelve feet in low-lying areas. Three coastal counties needed immediate evacuation orders.

Anika drafted the advisory while her colleague Marcus coordinated with emergency services. The governor's office was already on standby. By six in the morning, highways would be converted to one-way evacuation routes, shelters would open across four counties, and the National Guard would deploy.

She paused to look at the radar image — that perfect spiral of white and green rotating with terrible beauty. Nature did not negotiate. It did not care about preparation or planning. All they could do was read the signals correctly, communicate clearly, and give people enough time to move. That was the job. Tonight, like every night that mattered, the job was everything.`,
];

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

  // Recorder
  const [recording, setRecording] = useState(false);
  const [recordedBlob, setRecordedBlob] = useState<Blob | null>(null);
  const [recordedUrl, setRecordedUrl] = useState<string | null>(null);
  const [recordingTime, setRecordingTime] = useState(0);
  const [scriptIndex, setScriptIndex] = useState(0);
  const [showScript, setShowScript] = useState(false);
  const [audioQualityOk, setAudioQualityOk] = useState<boolean | null>(null);
  const [audioError, setAudioError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval>>(undefined);
  const streamRef = useRef<MediaStream | null>(null);
  const audioFileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetchVoices()
      .then(setVoices)
      .catch(() => {})
      .finally(() => setLoading(false));
    setScriptIndex(Math.floor(Math.random() * READING_SCRIPTS.length));
  }, []);

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      mediaRecorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        setRecordedBlob(blob);
        setRecordedUrl(URL.createObjectURL(blob));
        setAudioQualityOk(null); // Ask user to confirm quality
        stream.getTracks().forEach((t) => t.stop());
      };

      mediaRecorder.start(100);
      setRecording(true);
      setRecordingTime(0);
      setRecordedBlob(null);
      setRecordedUrl(null);
      setAudioQualityOk(null);

      timerRef.current = setInterval(() => {
        setRecordingTime((t) => {
          if (t >= 120) {
            mediaRecorder.stop();
            setRecording(false);
            clearInterval(timerRef.current);
            return 120;
          }
          return t + 1;
        });
      }, 1000);
    } catch {
      alert("Microphone access denied. Please allow microphone access and try again.");
    }
  }, []);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && recording) {
      mediaRecorderRef.current.stop();
      setRecording(false);
      if (timerRef.current) clearInterval(timerRef.current);
    }
  }, [recording]);

  const discardRecording = () => {
    setRecordedBlob(null);
    if (recordedUrl) URL.revokeObjectURL(recordedUrl);
    setRecordedUrl(null);
    setAudioQualityOk(null);
    setRecordingTime(0);
    // Pick a new script
    setScriptIndex((i) => (i + 1) % READING_SCRIPTS.length);
  };

  const useRecording = () => {
    if (!recordedBlob) return;
    const file = new File([recordedBlob], `voice_recording.webm`, { type: "audio/webm" });
    setCloneFiles([file]);
    setAudioQualityOk(true);
  };

  const formatTime = (s: number) =>
    `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

  const cloned = voices.filter((v) => v.category === "cloned");
  const premade = voices.filter((v) => v.category === "premade");

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
      setRecordedBlob(null);
      setRecordedUrl(null);
      setAudioQualityOk(null);
    } catch (err) {
      alert(String(err));
    } finally {
      setCloning(false);
    }
  };

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 items-end">
        <div>
          <label className="block text-xs text-[#a09888] mb-1">Select Voice <span className="text-[#d4b44e]">*</span></label>
          <select
            value={value}
            onChange={(e) => onChange(e.target.value)}
            disabled={loading}
            className="w-full bg-[#1a1814] border border-[#3d3428] rounded-lg px-3 py-2 text-sm text-[#f5f2ea] focus:outline-none focus:border-[#d4b44e]"
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
        </div>
        <div>
          <button
            onClick={() => setShowClone(!showClone)}
            className="px-4 py-2 rounded-lg border border-[#3d3428] text-sm text-[#a09888] hover:text-[#f5f2ea] hover:border-[#d4b44e] transition"
          >
            {showClone ? "Cancel" : "+ Clone Voice"}
          </button>
        </div>
      </div>

      {showClone && (
        <div className="bg-[#1a1814] border border-[#3d3428] rounded-lg p-5 space-y-5">
          {/* Clone config row */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 items-end">
            <div>
              <label className="block text-xs text-[#a09888] mb-1">Voice Name <span className="text-[#d4b44e]">*</span></label>
              <input
                placeholder="e.g. My Voice"
                value={cloneName}
                onChange={(e) => setCloneName(e.target.value)}
                className="w-full bg-[#0c0c0c] border border-[#3d3428] rounded-lg px-3 py-2 text-sm text-[#f5f2ea] focus:outline-none focus:border-[#d4b44e]"
              />
            </div>
            <div>
              <label className="block text-xs text-[#a09888] mb-1">Accent</label>
              <input
                placeholder="e.g. British"
                value={cloneAccent}
                onChange={(e) => setCloneAccent(e.target.value)}
                className="w-full bg-[#0c0c0c] border border-[#3d3428] rounded-lg px-3 py-2 text-sm text-[#f5f2ea] focus:outline-none focus:border-[#d4b44e]"
              />
            </div>
            <div>
              <label className="block text-xs text-[#a09888] mb-1">Gender</label>
              <select
                value={cloneGender}
                onChange={(e) => setCloneGender(e.target.value)}
                className="w-full bg-[#0c0c0c] border border-[#3d3428] rounded-lg px-3 py-2 text-sm text-[#f5f2ea] focus:outline-none focus:border-[#d4b44e]"
              >
                <option value="">Select</option>
                <option value="male">Male</option>
                <option value="female">Female</option>
              </select>
            </div>
          </div>

          {/* Recording Section */}
          <div className="bg-[#141210] border border-[#3d3428] rounded-lg p-4 space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-medium text-[#f5f2ea]">Record Your Voice</h4>
              <button
                onClick={() => setShowScript(!showScript)}
                className="text-xs text-[#d4b44e] hover:text-[#e8c54d] transition"
              >
                {showScript ? "Hide Script" : "Show Reading Script"}
              </button>
            </div>

            {/* Instructions */}
            <div className="flex items-start gap-2 text-xs text-[#7a7060] bg-[#0c0c0c] rounded-lg p-3">
              <svg className="w-4 h-4 text-[#d4b44e] shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <div>
                <p>Record at least <strong className="text-[#f5f2ea]">2 minutes</strong> of clear speech for best results.</p>
                <p className="mt-1">Speak naturally in a quiet environment. Avoid background noise, echo, or whispering.</p>
              </div>
            </div>

            {/* Reading Script */}
            {showScript && (
              <div className="bg-[#0c0c0c] border border-[#3d3428] rounded-lg p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <p className="text-xs text-[#7a7060] font-medium uppercase tracking-wider">Reading Script</p>
                  <button
                    onClick={() => setScriptIndex((i) => (i + 1) % READING_SCRIPTS.length)}
                    className="text-xs text-[#d4b44e] hover:text-[#e8c54d] transition flex items-center gap-1"
                  >
                    <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                    New Script
                  </button>
                </div>
                <p className="text-sm text-[#f5f2ea] leading-relaxed whitespace-pre-line">
                  {READING_SCRIPTS[scriptIndex]}
                </p>
              </div>
            )}

            {/* Recorder Controls */}
            <div className="flex items-center gap-3">
              {!recording && !recordedBlob && (
                <button
                  onClick={startRecording}
                  className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm font-medium hover:bg-red-500/20 transition"
                >
                  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
                    <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
                  </svg>
                  Start Recording
                </button>
              )}

              {recording && (
                <>
                  <button
                    onClick={stopRecording}
                    className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-red-500 text-white text-sm font-medium hover:bg-red-600 transition"
                  >
                    <span className="w-3 h-3 rounded-sm bg-white animate-pulse" />
                    Stop Recording
                  </button>
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                    <span className="text-sm font-mono text-[#f5f2ea]">{formatTime(recordingTime)}</span>
                    <span className="text-xs text-[#7a7060]">/ 2:00</span>
                  </div>
                  {/* Progress bar */}
                  <div className="flex-1 h-1.5 rounded-full bg-[#161208] overflow-hidden">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-red-500 to-[#d4b44e] transition-all duration-1000"
                      style={{ width: `${Math.min((recordingTime / 120) * 100, 100)}%` }}
                    />
                  </div>
                </>
              )}
            </div>

            {/* Playback & Quality Check */}
            {recordedUrl && !recording && (
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <audio src={recordedUrl} controls className="flex-1 h-10" />
                  <span className="text-xs text-[#7a7060] font-mono">{formatTime(recordingTime)}</span>
                </div>

                {recordingTime < 30 && (
                  <div className="flex items-center gap-2 text-xs text-yellow-400 bg-yellow-500/5 border border-yellow-500/20 rounded-lg px-3 py-2">
                    <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
                    </svg>
                    Recording is short ({formatTime(recordingTime)}). For best voice clone quality, record at least 2 minutes.
                  </div>
                )}

                {audioQualityOk === null && (
                  <div className="bg-[#0c0c0c] border border-[#3d3428] rounded-lg p-3">
                    <p className="text-sm text-[#f5f2ea] mb-3">Does the recording sound clear?</p>
                    <div className="flex gap-2">
                      <button
                        onClick={useRecording}
                        className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-sm font-medium hover:bg-emerald-500/20 transition"
                      >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                        </svg>
                        Yes, use this
                      </button>
                      <button
                        onClick={discardRecording}
                        className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm font-medium hover:bg-red-500/20 transition"
                      >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                        </svg>
                        Record again
                      </button>
                    </div>
                  </div>
                )}

                {audioQualityOk === true && (
                  <div className="flex items-center gap-2 text-xs text-emerald-400">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    Recording ready for cloning
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Or upload file */}
          <div className="flex items-center gap-3">
            <div className="flex-1 h-px bg-[#2a2418]" />
            <span className="text-xs text-[#7a7060]">or upload audio file <span className="text-[#d4b44e]">*</span></span>
            <div className="flex-1 h-px bg-[#2a2418]" />
          </div>

          <div>
            <button
              onClick={() => audioFileRef.current?.click()}
              className="flex items-center gap-2 px-4 py-2.5 rounded-lg border border-dashed border-[#3d3428] text-sm text-[#a09888] hover:border-[#d4b44e] hover:text-[#f5f2ea] transition"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
              </svg>
              {cloneFiles.length > 0
                ? cloneFiles.map((f) => f.name).join(", ")
                : "Upload audio file"}
            </button>
            <input
              ref={audioFileRef}
              type="file"
              accept="audio/*"
              multiple
              onChange={(e) => {
                if (e.target.files) {
                  const files = Array.from(e.target.files);
                  setAudioError(null);
                  // Validate each file's duration
                  const checks = files.map(
                    (file) =>
                      new Promise<number>((resolve) => {
                        const url = URL.createObjectURL(file);
                        const audio = new Audio(url);
                        audio.addEventListener("loadedmetadata", () => {
                          const dur = audio.duration;
                          URL.revokeObjectURL(url);
                          resolve(dur);
                        });
                        audio.addEventListener("error", () => {
                          URL.revokeObjectURL(url);
                          resolve(0);
                        });
                      })
                  );
                  Promise.all(checks).then((durations) => {
                    const totalDuration = durations.reduce((a, b) => a + b, 0);
                    if (totalDuration < 120) {
                      setAudioError(
                        `Audio must be at least 120 seconds. Current: ${Math.round(totalDuration)}s`
                      );
                      setCloneFiles([]);
                      setAudioQualityOk(null);
                    } else {
                      setCloneFiles(files);
                      setAudioQualityOk(true);
                      setAudioError(null);
                    }
                  });
                }
              }}
              className="hidden"
            />
            {audioError && (
              <p className="text-xs text-red-400 mt-1.5">{audioError}</p>
            )}
            <p className="text-xs text-[#7a7060] mt-1.5">
              Min 120 seconds, clean audio with no background noise
            </p>
          </div>

          <button
            onClick={handleClone}
            disabled={cloning || !cloneName || cloneFiles.length === 0}
            className="w-full py-2.5 rounded-lg bg-gradient-to-r from-[#f5da6a] to-[#c9a84c] text-[#0a0a0a] text-sm font-medium disabled:opacity-40 hover:opacity-90 transition"
          >
            {cloning ? "Cloning..." : "Clone Voice"}
          </button>
        </div>
      )}
    </div>
  );
}
