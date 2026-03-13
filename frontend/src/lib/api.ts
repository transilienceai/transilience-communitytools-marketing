import { API_BASE } from "./constants";
import type {
  BookendResult,
  CreateVideoParams,
  JobStatus,
  Voice,
} from "./types";

// --- Voices ---

export async function fetchVoices(): Promise<Voice[]> {
  const res = await fetch(`${API_BASE}/voices`);
  const data = await res.json();
  return data.voices ?? [];
}

export async function cloneVoice(form: FormData): Promise<{ name: string; voice_id: string }> {
  const res = await fetch(`${API_BASE}/voice-clone`, { method: "POST", body: form });
  if (!res.ok) throw new Error((await res.json()).error ?? "Clone failed");
  return res.json();
}

// --- Video Creation ---

export async function createVideo(params: CreateVideoParams): Promise<string> {
  const form = new FormData();
  params.files.forEach((f) => form.append("files", f));
  form.append("voice", params.voice);
  form.append("style", params.style);
  form.append("product", params.product);
  form.append("tone", params.tone);
  form.append("resolution", params.resolution);
  form.append("script_duration", String(params.scriptDuration));
  form.append("storyline", params.storyline);
  form.append("generate_music", String(params.generateMusic));
  form.append("music_prompt", params.musicPrompt);
  form.append("generate_intro", String(params.generateIntro));
  form.append("generate_outro", String(params.generateOutro));
  if (params.bookendJobId) form.append("bookend_job_id", params.bookendJobId);
  if (params.introOption) form.append("intro_option", String(params.introOption));
  if (params.outroOption) form.append("outro_option", String(params.outroOption));
  if (params.introVeoPrompt) form.append("intro_veo_prompt", params.introVeoPrompt);
  if (params.outroVeoPrompt) form.append("outro_veo_prompt", params.outroVeoPrompt);

  const res = await fetch(`${API_BASE}/create`, { method: "POST", body: form });
  if (!res.ok) throw new Error((await res.json()).error ?? "Create failed");
  const data = await res.json();
  return data.job_id;
}

export async function createFromStoryboard(
  storyboardJobId: string,
  params: Omit<CreateVideoParams, "files">
): Promise<string> {
  const form = new FormData();
  form.append("storyboard_job_id", storyboardJobId);
  form.append("voice", params.voice);
  form.append("style", params.style);
  form.append("product", params.product);
  form.append("tone", params.tone);
  form.append("resolution", params.resolution);
  form.append("script_duration", String(params.scriptDuration));
  form.append("storyline", params.storyline);
  form.append("generate_music", String(params.generateMusic));
  form.append("music_prompt", params.musicPrompt);
  form.append("generate_intro", String(params.generateIntro));
  form.append("generate_outro", String(params.generateOutro));
  if (params.bookendJobId) form.append("bookend_job_id", params.bookendJobId);
  if (params.introOption) form.append("intro_option", String(params.introOption));
  if (params.outroOption) form.append("outro_option", String(params.outroOption));
  if (params.introVeoPrompt) form.append("intro_veo_prompt", params.introVeoPrompt);
  if (params.outroVeoPrompt) form.append("outro_veo_prompt", params.outroVeoPrompt);

  const res = await fetch(`${API_BASE}/create-from-storyboard`, { method: "POST", body: form });
  if (!res.ok) throw new Error((await res.json()).error ?? "Create failed");
  const data = await res.json();
  return data.job_id;
}

// --- Job Status ---

export async function getJobStatus(jobId: string): Promise<JobStatus> {
  const res = await fetch(`${API_BASE}/status/${jobId}`);
  return res.json();
}

export function downloadUrl(jobId: string, fileType: "video" | "audio" | "music"): string {
  return `${API_BASE}/download/${jobId}/${fileType}`;
}

// --- Storyboard ---

export async function createStoryboard(form: FormData): Promise<string> {
  const res = await fetch(`${API_BASE}/storyboard`, { method: "POST", body: form });
  if (!res.ok) throw new Error((await res.json()).error ?? "Storyboard failed");
  const data = await res.json();
  return data.job_id;
}

export async function getStoryboardStatus(jobId: string): Promise<JobStatus> {
  const res = await fetch(`${API_BASE}/storyboard-status/${jobId}`);
  return res.json();
}

export function storyboardImageUrl(jobId: string, filename: string): string {
  return `${API_BASE}/storyboard-image/${jobId}/${filename}`;
}

// --- Bookends ---

export async function createBookends(form: FormData): Promise<string> {
  const res = await fetch(`${API_BASE}/bookends`, { method: "POST", body: form });
  if (!res.ok) throw new Error((await res.json()).error ?? "Bookend failed");
  const data = await res.json();
  return data.job_id;
}

export async function getBookendStatus(jobId: string): Promise<{ state: string; error: string; result?: BookendResult }> {
  const res = await fetch(`${API_BASE}/bookend-status/${jobId}`);
  return res.json();
}

export function bookendImageUrl(jobId: string, filename: string): string {
  return `${API_BASE}/bookend-image/${jobId}/${filename}`;
}

// --- Post-processing ---

export async function postProcess(form: FormData): Promise<{ video?: string }> {
  const res = await fetch(`${API_BASE}/post`, { method: "POST", body: form });
  if (!res.ok) throw new Error((await res.json()).error ?? "Post-processing failed");
  return res.json();
}

export async function applyAvatar(form: FormData): Promise<{ video?: string }> {
  const res = await fetch(`${API_BASE}/avatar`, { method: "POST", body: form });
  if (!res.ok) throw new Error((await res.json()).error ?? "Avatar overlay failed");
  return res.json();
}

// --- Samples ---

export function sampleVideoUrl(style: string): string {
  return `${API_BASE}/sample/${style}`;
}

export async function checkSampleExists(style: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/sample/${style}`, { method: "HEAD" });
    return res.ok;
  } catch {
    return false;
  }
}
