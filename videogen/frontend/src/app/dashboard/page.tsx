"use client";

import { useCallback, useState } from "react";
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

  // Bookend state
  const [bookendJobId, setBookendJobId] = useState("");
  const [introOption, setIntroOption] = useState(0);
  const [outroOption, setOutroOption] = useState(0);
  const [introVeoPrompt, setIntroVeoPrompt] = useState("");
  const [outroVeoPrompt, setOutroVeoPrompt] = useState("");

  // Storyboard state
  const [storyboardJobId, setStoryboardJobId] = useState<string | null>(null);
  const [useStoryboard, setUseStoryboard] = useState(false);

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
    }),
    [
      voice, style, product, tone, resolution, scriptDuration, storyline,
      generateMusic, musicPrompt, generateIntro, generateOutro,
      bookendJobId, introOption, outroOption, introVeoPrompt, outroVeoPrompt,
    ]
  );

  const handleGenerate = async () => {
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
      alert(String(err));
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

  const canGenerate =
    (files.length > 0 || (useStoryboard && storyboardJobId)) &&
    appState === "config";

  return (
    <div className="space-y-8">
      {appState === "config" && (
        <>
          {/* Voice */}
          <Section title="Voice">
            <VoiceSelector value={voice} onChange={setVoice} />
          </Section>

          {/* Content Source */}
          <Section title="Content">
            <div className="space-y-4">
              <FileUpload files={files} onChange={setFiles} />

              {style === "marketing" && (
                <StoryboardPanel
                  product={product}
                  storyline={storyline}
                  tone={tone}
                  style={style}
                  onStoryboardReady={(id) => {
                    setStoryboardJobId(id);
                    setUseStoryboard(true);
                  }}
                />
              )}

              {storyboardJobId && (
                <label className="flex items-center gap-2 text-sm text-gray-400">
                  <input
                    type="checkbox"
                    checked={useStoryboard}
                    onChange={(e) => setUseStoryboard(e.target.checked)}
                    className="accent-orange-500"
                  />
                  Use storyboard images instead of uploaded files
                </label>
              )}
            </div>
          </Section>

          {/* Style */}
          <Section title="Style">
            <StylePicker value={style} onChange={setStyle} />
          </Section>

          {/* Video Config */}
          <Section title="Configuration">
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
            />
          </Section>

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
            disabled={!canGenerate}
            className="w-full py-3 rounded-lg bg-gradient-to-r from-orange-500 to-pink-500 text-white font-semibold text-lg disabled:opacity-40 hover:opacity-90 transition"
          >
            Generate Video
          </button>
        </>
      )}

      {appState === "generating" && jobId && (
        <GenerationProgress
          jobId={jobId}
          fetcher={() => getJobStatus(jobId)}
          onDone={handleDone}
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
    <div className="bg-[#161616] border border-[#222] rounded-xl p-6">
      <h2 className="text-lg font-semibold mb-4">{title}</h2>
      {children}
    </div>
  );
}
