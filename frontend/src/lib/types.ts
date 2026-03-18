export interface Voice {
  name: string;
  category: "cloned" | "premade";
  voice_id?: string;
}

export interface JobStatus {
  state: "pending" | "running" | "done" | "error";
  logs: string;
  error: string;
  result?: JobResult;
}

export interface JobResult {
  has_video?: boolean;
  has_audio?: boolean;
  has_music?: boolean;
  cost?: CostEstimate;
}

export interface CostEstimate {
  num_scenes: number;
  gemini_vision: number;
  veo_animation: number;
  tts: number;
  music: number;
  total: number;
}

export interface BookendOption {
  option_number: number;
  title_text: string;
  subtitle_text: string;
  image_filename: string;
  veo_motion_prompt?: string;
}

export interface BookendResult {
  intro_options?: BookendOption[];
  outro_options?: BookendOption[];
}

export interface StoryboardScene {
  scene_number: number;
  title: string;
  voiceover_script: string;
}

export interface StoryboardResult {
  scenes?: StoryboardScene[];
  images?: string[];
  sequence_files?: string[];
}

export type VideoStyle = "marketing" | "feature-explainer" | "tutorial-explainer";

export interface CreateVideoParams {
  files: File[];
  voice: string;
  style: VideoStyle;
  product: string;
  tone: string;
  resolution: string;
  scriptDuration: number;
  storyline: string;
  generateMusic: boolean;
  musicPrompt: string;
  generateIntro: boolean;
  generateOutro: boolean;
  bookendJobId: string;
  introOption: number;
  outroOption: number;
  introVeoPrompt: string;
  outroVeoPrompt: string;
  maxWorkers: number;
  noVoiceoverFiles?: string[];
}
