import { auth } from "@clerk/nextjs/server";
import Link from "next/link";

const steps = [
  { num: "1", title: "Upload", desc: "Drop images, videos, PDFs, or PowerPoints" },
  { num: "2", title: "AI Analysis", desc: "Gemini Vision understands your content" },
  { num: "3", title: "Animate & Voice", desc: "Veo 3.1 animation + ElevenLabs voiceover" },
  { num: "4", title: "Download", desc: "Professional MP4 with music, ready to share" },
];

const features = [
  { title: "Any Input Type", desc: "Images, videos, PPT, PDF — mix them all in one folder" },
  { title: "Voice Cloning", desc: "Clone any voice from a short audio sample" },
  { title: "AI Music", desc: "Generate background music that matches your tone" },
  { title: "Storyline-Driven", desc: "Cohesive narrative with hooks, flow, and CTAs" },
  { title: "Branded Frames", desc: "AI-generated intro and outro with Veo animation" },
  { title: "Cost-Effective", desc: "~$0.25-0.65 per video, or $0.03 with free options" },
];

export default async function LandingPage() {
  const { userId } = await auth();
  const isSignedIn = !!userId;

  return (
    <main className="min-h-screen bg-[#0f0f0f]">
      {/* Nav */}
      <nav className="flex items-center justify-between px-8 py-5 max-w-7xl mx-auto">
        <span className="text-xl font-bold bg-gradient-to-r from-orange-500 to-pink-500 bg-clip-text text-transparent">
          VideoGen
        </span>
        <div className="flex gap-4">
          {isSignedIn ? (
            <Link
              href="/dashboard"
              className="px-4 py-2 text-sm rounded-lg bg-gradient-to-r from-orange-500 to-pink-500 text-white font-medium hover:opacity-90 transition"
            >
              Dashboard
            </Link>
          ) : (
            <>
              <Link
                href="/sign-in"
                className="px-4 py-2 text-sm text-gray-300 hover:text-white transition"
              >
                Sign In
              </Link>
              <Link
                href="/sign-up"
                className="px-4 py-2 text-sm rounded-lg bg-gradient-to-r from-orange-500 to-pink-500 text-white font-medium hover:opacity-90 transition"
              >
                Get Started
              </Link>
            </>
          )}
        </div>
      </nav>

      {/* Hero */}
      <section className="text-center py-24 px-6">
        <h1 className="text-5xl md:text-6xl font-bold mb-6 leading-tight">
          Turn any content into{" "}
          <span className="bg-gradient-to-r from-orange-500 to-pink-500 bg-clip-text text-transparent">
            professional marketing videos
          </span>
        </h1>
        <p className="text-lg text-gray-400 max-w-2xl mx-auto mb-10">
          Upload images, slides, or videos. AI generates cohesive scripts,
          cinematic animations, voiceover, and music — in minutes.
        </p>
        <Link
          href={isSignedIn ? "/dashboard" : "/sign-up"}
          className="inline-block px-8 py-3 rounded-lg bg-gradient-to-r from-orange-500 to-pink-500 text-white text-lg font-semibold hover:opacity-90 transition"
        >
          {isSignedIn ? "Go to Dashboard" : "Experience It"}
        </Link>
      </section>

      {/* How It Works */}
      <section className="max-w-5xl mx-auto px-6 py-16">
        <h2 className="text-3xl font-bold text-center mb-12">How It Works</h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          {steps.map((s) => (
            <div
              key={s.num}
              className="bg-[#161616] border border-[#222] rounded-xl p-6 text-center"
            >
              <div className="w-10 h-10 rounded-full bg-gradient-to-r from-orange-500 to-pink-500 flex items-center justify-center text-white font-bold mx-auto mb-4">
                {s.num}
              </div>
              <h3 className="font-semibold text-lg mb-2">{s.title}</h3>
              <p className="text-sm text-gray-400">{s.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section className="max-w-5xl mx-auto px-6 py-16">
        <h2 className="text-3xl font-bold text-center mb-12">Features</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {features.map((f) => (
            <div
              key={f.title}
              className="bg-[#161616] border border-[#222] rounded-xl p-6 hover:border-[#333] transition"
            >
              <h3 className="font-semibold text-lg mb-2">{f.title}</h3>
              <p className="text-sm text-gray-400">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="text-center text-sm text-gray-500 py-12 border-t border-[#222]">
        Built with Gemini Vision, Veo 3.1, Imagen 4.0 & ElevenLabs
      </footer>
    </main>
  );
}
