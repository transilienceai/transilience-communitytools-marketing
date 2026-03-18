import { auth } from "@clerk/nextjs/server";
import Link from "next/link";

const steps = [
  {
    num: "1",
    title: "Upload Your Assets",
    desc: "Drop your screenshots, pitch deck, product demo, or any mix — we handle everything",
    icon: "M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12",
  },
  {
    num: "2",
    title: "AI Writes Your Script",
    desc: "Gemini Vision analyzes every slide and writes a compelling marketing narrative with hooks and CTAs",
    icon: "M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z",
  },
  {
    num: "3",
    title: "Cinematic Production",
    desc: "Veo 3.1 animates every scene, ElevenLabs adds professional voiceover, AI generates background music",
    icon: "M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15.536a5 5 0 010-7.072m-2.828 9.9a9 9 0 010-12.728",
  },
  {
    num: "4",
    title: "Ship It",
    desc: "Download your launch-ready MP4 — post to LinkedIn, embed on your site, send to investors",
    icon: "M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4",
  },
];

const features = [
  {
    title: "Pitch Deck to Video",
    desc: "Upload your PPTX or PDF pitch deck and get a narrated, animated video — perfect for investor outreach and Product Hunt launches.",
    icon: "M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10",
  },
  {
    title: "Your Voice, Your Brand",
    desc: "Clone your founder's voice from a 2-minute recording. Every video sounds like you — not a stock narrator.",
    icon: "M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z",
  },
  {
    title: "AI Background Music",
    desc: "Describe the vibe — \"upbeat SaaS demo\", \"inspiring launch\" — and get a custom soundtrack that fits perfectly.",
    icon: "M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3",
  },
  {
    title: "Storyline That Sells",
    desc: "Tell the AI your narrative — it writes a cohesive script across all scenes with a hook, pain points, solution, and CTA.",
    icon: "M4 6h16M4 10h16M4 14h16M4 18h16",
  },
  {
    title: "Website to Video",
    desc: "Paste your landing page URL — AI crawls it, captures screenshots, and produces a marketing video from your live product.",
    icon: "M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9",
  },
  {
    title: "100x Cheaper",
    desc: "Full production for ~$0.30 per video. Replace $3K-5K agency quotes with AI that delivers in minutes, not weeks.",
    icon: "M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
  },
];

const logos = [
  { name: "Gemini", label: "Google Gemini Vision" },
  { name: "Veo", label: "Veo 3.1 Animation" },
  { name: "Imagen", label: "Imagen 4.0" },
  { name: "ElevenLabs", label: "ElevenLabs TTS" },
];

export default async function LandingPage() {
  const { userId } = await auth();
  const isSignedIn = !!userId;

  return (
    <main className="min-h-screen bg-[#0c0c0c] overflow-hidden text-[#f5f2ea]">
      {/* Ambient glow */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute top-[-30%] left-1/2 -translate-x-1/2 w-[900px] h-[700px] bg-[#d4b44e]/[0.03] rounded-full blur-[150px]" />
        <div className="absolute bottom-[-15%] right-[-5%] w-[600px] h-[600px] bg-[#c9a84c]/[0.03] rounded-full blur-[130px]" />
        <div className="absolute top-[40%] left-[-10%] w-[400px] h-[400px] bg-[#d4b44e]/[0.015] rounded-full blur-[100px]" />
      </div>

      {/* Subtle grid pattern */}
      <div
        className="fixed inset-0 pointer-events-none opacity-[0.03]"
        style={{
          backgroundImage: "linear-gradient(rgba(212,180,78,0.4) 1px, transparent 1px), linear-gradient(90deg, rgba(212,180,78,0.4) 1px, transparent 1px)",
          backgroundSize: "60px 60px",
        }}
      />

      <div className="relative z-10">
        {/* Nav */}
        <nav className="flex items-center justify-between px-8 py-6 max-w-7xl mx-auto">
          <div className="flex items-center gap-3">
            <img src="/logo.png" alt="Transilience" className="h-8 w-auto" />
            <span className="text-lg font-semibold text-[#f5f2ea]">Transilience</span>
            <span className="text-[#333]">|</span>
            <span className="text-lg font-bold bg-gradient-to-r from-[#f5da6a] to-[#d4b44e] bg-clip-text text-transparent">
              VideoGen
            </span>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/docs"
              className="px-5 py-2.5 text-sm text-[#a09888] hover:text-[#f5f2ea] transition"
            >
              API Docs
            </Link>
            {isSignedIn ? (
              <Link
                href="/dashboard"
                className="px-5 py-2.5 text-sm rounded-full bg-gradient-to-r from-[#f5da6a] to-[#c9a84c] text-[#0a0a0a] font-semibold hover:shadow-lg hover:shadow-[#d4b44e]/20 transition-all"
              >
                Open Dashboard
              </Link>
            ) : (
              <>
                <Link
                  href="/sign-in"
                  className="px-5 py-2.5 text-sm text-[#a09888] hover:text-[#f5f2ea] transition"
                >
                  Sign In
                </Link>
                <Link
                  href="/sign-up"
                  className="px-5 py-2.5 text-sm rounded-full bg-gradient-to-r from-[#f5da6a] to-[#c9a84c] text-[#0a0a0a] font-semibold hover:shadow-lg hover:shadow-[#d4b44e]/20 transition-all"
                >
                  Get Started Free
                </Link>
              </>
            )}
          </div>
        </nav>

        {/* Hero */}
        <section className="text-center pt-24 pb-8 px-6">
          <div className="inline-flex items-center gap-2 px-5 py-2 rounded-full border border-[#3d3428] bg-[#1a1814] text-xs text-[#d4b44e] mb-10 tracking-wide uppercase">
            <span className="w-1.5 h-1.5 rounded-full bg-[#d4b44e] animate-pulse" />
            Trusted by early-stage startups to launch faster
          </div>

          <h1 className="text-5xl md:text-7xl font-bold mb-8 leading-[1.08] tracking-tight max-w-5xl mx-auto font-[family-name:var(--font-playfair)]">
            Turn any content into{" "}
            <span className="bg-gradient-to-r from-[#f5da6a] via-[#d4b44e] to-[#c9a84c] bg-clip-text text-transparent">
              professional marketing videos
            </span>
          </h1>

          <p className="text-lg md:text-xl text-[#a09888] max-w-2xl mx-auto mb-14 leading-relaxed">
            Stop spending $5K on video agencies. Upload your screenshots, pitch deck, or demo
            — AI writes the script, creates cinematic animations, adds voiceover and music.
            Launch-ready videos in minutes, not weeks.
          </p>

          <div className="flex items-center justify-center gap-4 mb-8">
            <Link
              href={isSignedIn ? "/dashboard" : "/sign-up"}
              className="group px-9 py-4 rounded-full bg-gradient-to-r from-[#f5da6a] to-[#c9a84c] text-[#0a0a0a] text-lg font-bold hover:shadow-2xl hover:shadow-[#d4b44e]/30 transition-all hover:-translate-y-0.5"
            >
              {isSignedIn ? "Go to Dashboard" : "Start Creating"}
            </Link>
            <a
              href="#demo"
              className="px-9 py-4 rounded-full border border-[#3d3428] text-[#d4b44e] text-lg font-medium hover:border-[#d4b44e]/40 hover:bg-[#d4b44e]/5 transition"
            >
              Watch Demo
            </a>
          </div>

          <p className="text-xs text-[#7a7060] tracking-wide">
            No credit card required &middot; ~$0.30 per video &middot; Ready in minutes
          </p>
        </section>

        {/* Video Demo */}
        <section id="demo" className="max-w-4xl mx-auto px-6 py-16">
          <div className="relative group">
            <div className="absolute -inset-1 bg-gradient-to-r from-[#d4b44e]/15 via-[#f0d060]/10 to-[#c9a84c]/15 rounded-2xl blur-xl opacity-50 group-hover:opacity-80 transition duration-700" />
            <div className="relative rounded-2xl overflow-hidden border border-[#3d3428] bg-black shadow-2xl shadow-[#d4b44e]/5">
              <video
                src={`${process.env.NEXT_PUBLIC_API_BASE_URL}/sample/marketing`}
                controls
                muted
                autoPlay
                loop
                playsInline
                className="w-full"
              />
            </div>
          </div>
          <p className="text-center text-sm text-[#7a7060] mt-5 tracking-wide">
            This startup marketing video was generated from screenshots in under 10 minutes
          </p>
        </section>

        {/* Divider */}
        <div className="max-w-xs mx-auto h-px bg-gradient-to-r from-transparent via-[#2a2418] to-transparent" />

        {/* Tech Stack */}
        <section className="max-w-4xl mx-auto px-6 py-20">
          <p className="text-center text-[10px] text-[#7a7060] uppercase tracking-[0.25em] mb-10">
            Built on world-class AI infrastructure
          </p>
          <div className="flex items-center justify-center gap-16 flex-wrap">
            {logos.map((l) => (
              <div key={l.name} className="flex flex-col items-center gap-3">
                <div className="w-14 h-14 rounded-xl bg-[#1a1814] border border-[#3d3428] flex items-center justify-center">
                  <span className="text-sm font-bold bg-gradient-to-b from-[#f5da6a] to-[#c9a84c] bg-clip-text text-transparent">
                    {l.name.slice(0, 2).toUpperCase()}
                  </span>
                </div>
                <span className="text-[11px] text-[#7a7060] tracking-wide">{l.label}</span>
              </div>
            ))}
          </div>
        </section>

        {/* Divider */}
        <div className="max-w-xs mx-auto h-px bg-gradient-to-r from-transparent via-[#2a2418] to-transparent" />

        {/* How It Works */}
        <section className="max-w-6xl mx-auto px-6 py-24">
          <div className="text-center mb-20">
            <p className="text-[10px] text-[#d4b44e] uppercase tracking-[0.3em] font-medium mb-4">
              Simple Workflow
            </p>
            <h2 className="text-4xl md:text-5xl font-bold tracking-tight font-[family-name:var(--font-playfair)]">From screenshots to launch video</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
            {steps.map((s, i) => (
              <div key={s.num} className="relative group">
                {i < steps.length - 1 && (
                  <div className="hidden md:block absolute top-12 left-[60%] w-[80%] h-px bg-gradient-to-r from-[#2a2418] to-transparent" />
                )}
                <div className="bg-[#141210] border border-[#3d3428] rounded-2xl p-8 hover:border-[#3d3428] hover:bg-[#1a1814] transition-all duration-500 group-hover:-translate-y-1">
                  <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-[#d4b44e]/8 to-[#c9a84c]/8 border border-[#d4b44e]/15 flex items-center justify-center mb-6">
                    <svg className="w-5 h-5 text-[#d4b44e]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d={s.icon} />
                    </svg>
                  </div>
                  <div className="text-[10px] text-[#d4b44e]/40 font-mono tracking-widest mb-3">STEP 0{s.num}</div>
                  <h3 className="font-semibold text-lg mb-3 text-[#f5f2ea]">{s.title}</h3>
                  <p className="text-sm text-[#a09888] leading-relaxed">{s.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Divider */}
        <div className="max-w-xs mx-auto h-px bg-gradient-to-r from-transparent via-[#2a2418] to-transparent" />

        {/* Features */}
        <section className="max-w-6xl mx-auto px-6 py-24">
          <div className="text-center mb-20">
            <p className="text-[10px] text-[#d4b44e] uppercase tracking-[0.3em] font-medium mb-4">
              Capabilities
            </p>
            <h2 className="text-4xl md:text-5xl font-bold tracking-tight font-[family-name:var(--font-playfair)]">Built for startups that move fast</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {features.map((f) => (
              <div
                key={f.title}
                className="group bg-[#141210] border border-[#3d3428] rounded-2xl p-8 hover:border-[#d4b44e]/20 transition-all duration-500 hover:-translate-y-1"
              >
                <div className="w-11 h-11 rounded-lg bg-gradient-to-br from-[#d4b44e]/8 to-[#c9a84c]/8 border border-[#d4b44e]/15 flex items-center justify-center mb-5 group-hover:border-[#d4b44e]/30 group-hover:shadow-lg group-hover:shadow-[#d4b44e]/5 transition-all duration-500">
                  <svg className="w-5 h-5 text-[#d4b44e]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d={f.icon} />
                  </svg>
                </div>
                <h3 className="font-semibold text-lg mb-3 text-[#f5f2ea]">{f.title}</h3>
                <p className="text-sm text-[#a09888] leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* CTA */}
        <section className="max-w-4xl mx-auto px-6 py-28 text-center">
          <div className="relative">
            <div className="absolute -inset-4 bg-gradient-to-r from-[#d4b44e]/5 via-[#f0d060]/3 to-[#c9a84c]/5 rounded-[2rem] blur-3xl" />
            <div className="relative bg-[#141210] border border-[#3d3428] rounded-[2rem] p-20">
              {/* Decorative corner accents */}
              <div className="absolute top-6 left-6 w-8 h-8 border-t border-l border-[#d4b44e]/20 rounded-tl-lg" />
              <div className="absolute top-6 right-6 w-8 h-8 border-t border-r border-[#d4b44e]/20 rounded-tr-lg" />
              <div className="absolute bottom-6 left-6 w-8 h-8 border-b border-l border-[#d4b44e]/20 rounded-bl-lg" />
              <div className="absolute bottom-6 right-6 w-8 h-8 border-b border-r border-[#d4b44e]/20 rounded-br-lg" />

              <h2 className="text-4xl md:text-5xl font-bold mb-5 tracking-tight font-[family-name:var(--font-playfair)]">
                Ship your launch video{" "}
                <span className="bg-gradient-to-r from-[#f5da6a] to-[#d4b44e] bg-clip-text text-transparent">today</span>
              </h2>
              <p className="text-lg text-[#a09888] mb-12 max-w-xl mx-auto leading-relaxed">
                Your startup deserves marketing videos that look like a $5K production.
                Get them for under a dollar, in minutes.
              </p>
              <Link
                href={isSignedIn ? "/dashboard" : "/sign-up"}
                className="inline-block px-12 py-4 rounded-full bg-gradient-to-r from-[#f5da6a] to-[#c9a84c] text-[#0a0a0a] text-lg font-bold hover:shadow-2xl hover:shadow-[#d4b44e]/30 transition-all hover:-translate-y-0.5"
              >
                {isSignedIn ? "Open Dashboard" : "Get Started Free"}
              </Link>
            </div>
          </div>
        </section>

        {/* Footer */}
        <footer className="border-t border-[#2a2418] py-14">
          <div className="max-w-7xl mx-auto px-8 flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <img src="/logo.png" alt="Transilience" className="h-5 w-auto opacity-60" />
              <span className="text-sm font-semibold text-[#7a7060]">Transilience</span>
              <span className="text-[#2a2418]">|</span>
              <span className="text-sm font-semibold text-[#5a5040]">VideoGen</span>
            </div>
            <p className="text-[11px] text-[#5a5040] tracking-wide">
              Powered by Google Gemini, Veo 3.1, Imagen 4.0 & ElevenLabs
            </p>
          </div>
        </footer>
      </div>
    </main>
  );
}
