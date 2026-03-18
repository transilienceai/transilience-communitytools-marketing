"use client";

import { useCallback, useState, type ReactNode } from "react";
import {
  createFromStoryboard,
  createVideo,
  downloadUrl,
  getJobStatus,
} from "@/lib/api";
import type { CreateVideoParams, JobResult, VideoStyle } from "@/lib/types";
import FileUpload from "@/components/dashboard/file-upload";
import StylePicker from "@/components/dashboard/style-picker";
import VideoConfig from "@/components/dashboard/video-config";
import VoiceSelector from "@/components/dashboard/voice-selector";
import GenerationProgress from "@/components/dashboard/generation-progress";
import ResultsPanel from "@/components/dashboard/results-panel";
import StoryboardPanel from "@/components/dashboard/storyboard-panel";
import BookendGenerator from "@/components/dashboard/bookend-generator";
import RecentVideos from "@/components/dashboard/recent-videos";

type AppState = "config" | "generating" | "results";

export default function DashboardPage() {
  const [appState, setAppState] = useState<AppState>("config");
  const [jobId, setJobId] = useState<string | null>(null);
  const [result, setResult] = useState<JobResult | null>(null);

  // Config state
  const [files, setFiles] = useState<File[]>([]);
  const [voice, setVoice] = useState("Smritika");
  const [style, setStyle] = useState<VideoStyle>("marketing");
  const [product, setProduct] = useState("");
  const [tone, setTone] = useState("professional and engaging");
  const [resolution, setResolution] = useState("1080p");
  const [scriptDuration, setScriptDuration] = useState(60);
  const [storyline, setStoryline] = useState("");
  const [generateMusic, setGenerateMusic] = useState(false);
  const [musicPrompt, setMusicPrompt] = useState("");
  const [generateIntro, setGenerateIntro] = useState(false);
  const [generateOutro, setGenerateOutro] = useState(false);
  const [maxWorkers, setMaxWorkers] = useState(5);

  // Bookend state
  const [bookendJobId, setBookendJobId] = useState("");
  const [introOption, setIntroOption] = useState(0);
  const [outroOption, setOutroOption] = useState(0);
  const [introVeoPrompt, setIntroVeoPrompt] = useState("");
  const [outroVeoPrompt, setOutroVeoPrompt] = useState("");

  // Storyboard state
  const [storyboardJobId, setStoryboardJobId] = useState<string | null>(null);
  const [useStoryboard, setUseStoryboard] = useState(false);

  // Recording state
  const [isRecording, setIsRecording] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);

  // Per-file voiceover settings
  const [noVoiceoverFiles, setNoVoiceoverFiles] = useState<Set<string>>(new Set());

  const buildParams = useCallback(
    (): Omit<CreateVideoParams, "files"> => ({
      voice,
      style,
      product,
      tone,
      resolution,
      scriptDuration,
      storyline,
      generateMusic,
      musicPrompt,
      generateIntro,
      generateOutro,
      bookendJobId,
      introOption,
      outroOption,
      introVeoPrompt,
      outroVeoPrompt,
      maxWorkers,
      noVoiceoverFiles: Array.from(noVoiceoverFiles),
    }),
    [
      voice, style, product, tone, resolution, scriptDuration, storyline,
      generateMusic, musicPrompt, generateIntro, generateOutro,
      bookendJobId, introOption, outroOption, introVeoPrompt, outroVeoPrompt,
      maxWorkers, noVoiceoverFiles,
    ]
  );

  const handleGenerate = async () => {
    setGenerating(true);
    setGenerateError(null);
    try {
      let id: string;
      if (useStoryboard && storyboardJobId) {
        id = await createFromStoryboard(storyboardJobId, buildParams());
      } else {
        if (files.length === 0) return;
        id = await createVideo({ ...buildParams(), files });
      }
      setJobId(id);
      setAppState("generating");
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setGenerateError(msg);
    } finally {
      setGenerating(false);
    }
  };

  const handleDone = (status: { result?: JobResult }) => {
    setResult(status.result ?? null);
    setAppState("results");
  };

  const handleNewVideo = () => {
    setAppState("config");
    setJobId(null);
    setResult(null);
    setFiles([]);
    setStoryboardJobId(null);
    setUseStoryboard(false);
    setBookendJobId("");
  };

  const handleLoadJob = (loadedJobId: string, hasAudio: boolean, hasMusic: boolean) => {
    setJobId(loadedJobId);
    setResult({ has_video: true, has_audio: hasAudio, has_music: hasMusic });
    setAppState("results");
  };

  const canGenerate =
    (files.length > 0 || (useStoryboard && storyboardJobId)) &&
    appState === "config" &&
    !isRecording;

  return (
    <div className="space-y-8">
      {appState === "config" && (
        <>
          {/* Voice */}
          <Section title="Voice">
            <VoiceSelector value={voice} onChange={setVoice} />
          </Section>

          {/* Style */}
          <Section title="Style">
            <StylePicker value={style} onChange={setStyle} />
          </Section>

          {/* Content Source */}
          <Section title="Content">
            <div className="space-y-4">
              <FileUpload
                files={files}
                onChange={setFiles}
                onRecordingChange={setIsRecording}
                noVoiceoverFiles={noVoiceoverFiles}
                onNoVoiceoverChange={setNoVoiceoverFiles}
              />

              {style === "marketing" && (
                <StoryboardPanel
                  product={product}
                  storyline={storyline}
                  tone={tone}
                  style={style}
                  hasFiles={files.length > 0}
                  files={files}
                  onStoryboardReady={(id) => {
                    setStoryboardJobId(id);
                    setUseStoryboard(true);
                  }}
                />
              )}

              {storyboardJobId && (
                <label className="flex items-center gap-2 text-sm text-[#a09888]">
                  <input
                    type="checkbox"
                    checked={useStoryboard}
                    onChange={(e) => setUseStoryboard(e.target.checked)}
                    className="accent-[#d4b44e]"
                  />
                  Use storyboard images instead of uploaded files
                </label>
              )}
            </div>
          </Section>

          {/* Video Config */}
          <CollapsibleSection title="Advanced Custom Configurations">
            <VideoConfig
              product={product}
              onProductChange={setProduct}
              tone={tone}
              onToneChange={setTone}
              resolution={resolution}
              onResolutionChange={setResolution}
              scriptDuration={scriptDuration}
              onScriptDurationChange={setScriptDuration}
              storyline={storyline}
              onStorylineChange={setStoryline}
              generateMusic={generateMusic}
              onGenerateMusicChange={setGenerateMusic}
              musicPrompt={musicPrompt}
              onMusicPromptChange={setMusicPrompt}
              generateIntro={generateIntro}
              onGenerateIntroChange={setGenerateIntro}
              generateOutro={generateOutro}
              onGenerateOutroChange={setGenerateOutro}
              maxWorkers={maxWorkers}
              onMaxWorkersChange={setMaxWorkers}
              files={files}
              style={style}
            />
          </CollapsibleSection>

          {/* Bookends */}
          {(generateIntro || generateOutro) && (
            <Section title="Bookend Frames">
              <BookendGenerator
                product={product}
                storyline={storyline}
                tone={tone}
                style={style}
                generateIntro={generateIntro}
                generateOutro={generateOutro}
                files={files}
                onBookendReady={(id, intro, outro, introPrompt, outroPrompt) => {
                  setBookendJobId(id);
                  setIntroOption(intro);
                  setOutroOption(outro);
                  setIntroVeoPrompt(introPrompt);
                  setOutroVeoPrompt(outroPrompt);
                }}
              />
            </Section>
          )}

          {/* Generate Button */}
          <button
            onClick={handleGenerate}
            disabled={!canGenerate || generating}
            className="w-full py-3 rounded-lg bg-gradient-to-r from-[#f5da6a] to-[#c9a84c] text-[#0a0a0a] font-semibold text-lg disabled:opacity-40 hover:opacity-90 transition"
          >
            {generating
              ? "Starting..."
              : isRecording
              ? "Stop recording first..."
              : files.length === 0 && !(useStoryboard && storyboardJobId)
              ? "Upload files to generate"
              : "Generate Video"}
          </button>
          {generateError && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 text-sm text-red-400">
              <p className="font-medium">Generation failed</p>
              <p className="text-xs mt-1 text-red-400/80">{generateError}</p>
            </div>
          )}

          {/* Recent Videos */}
          <RecentVideos onLoadJob={handleLoadJob} />
        </>
      )}

      {appState === "generating" && jobId && (
        <GenerationProgress
          jobId={jobId}
          fetcher={() => getJobStatus(jobId)}
          onDone={handleDone}
          onRetry={() => {
            setAppState("config");
            setJobId(null);
          }}
        />
      )}

      {appState === "results" && jobId && (
        <ResultsPanel
          jobId={jobId}
          result={result}
          videoUrl={downloadUrl(jobId, "video")}
          audioUrl={downloadUrl(jobId, "audio")}
          musicUrl={downloadUrl(jobId, "music")}
          onNewVideo={handleNewVideo}
        />
      )}
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-[#141210] border border-[#3d3428] rounded-xl p-6">
      <h2 className="text-lg font-semibold mb-4 text-[#f5f2ea]">{title}</h2>
      {children}
    </div>
  );
}

function CollapsibleSection({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="bg-[#141210] border border-[#3d3428] rounded-xl p-6">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center justify-between w-full text-left"
      >
        <h2 className="text-lg font-semibold text-[#f5f2ea]">{title}</h2>
        <svg
          className={`w-5 h-5 text-[#a09888] transition-transform ${open ? "rotate-180" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {open && <div className="mt-4">{children}</div>}
    </div>
  );
}
