export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "https://video-generator.transilienceapi.com";

export const STYLES = [
  {
    id: "marketing" as const,
    name: "Marketing",
    description: "Bold, persuasive videos that convert viewers into customers",
    icon: "M13 10V3L4 14h7v7l9-11h-7z",
  },
  {
    id: "feature-explainer" as const,
    name: "Feature Explainer",
    description: "Clear, structured walkthroughs of product features",
    icon: "M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z",
  },
  {
    id: "tutorial-explainer" as const,
    name: "Tutorial",
    description: "Step-by-step educational content that teaches effectively",
    icon: "M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253",
  },
] as const;

export const RESOLUTIONS = ["720p", "1080p", "4k"] as const;

export const ACCEPTED_FILE_TYPES = {
  images: [".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"],
  videos: [".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"],
  documents: [".pdf", ".doc", ".docx", ".pptx", ".ppt"],
};

export const ALL_ACCEPTED = [
  ...ACCEPTED_FILE_TYPES.images,
  ...ACCEPTED_FILE_TYPES.videos,
  ...ACCEPTED_FILE_TYPES.documents,
].join(",");
