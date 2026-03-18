import { UserButton } from "@clerk/nextjs";
import Link from "next/link";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-[#0c0c0c]">
      <nav className="flex items-center justify-between px-8 py-4 border-b border-[#3d3428]">
        <Link href="/" className="flex items-center gap-3">
          <img src="/logo.png" alt="Transilience" className="h-7 w-auto" />
          <span className="text-lg font-semibold text-[#f5f2ea]">Transilience</span>
          <span className="text-[#333]">|</span>
          <span className="text-lg font-bold bg-gradient-to-r from-[#f5da6a] to-[#d4b44e] bg-clip-text text-transparent">
            VideoGen
          </span>
        </Link>
        <UserButton />
      </nav>
      <div className="max-w-7xl mx-auto px-6 py-8">{children}</div>
    </div>
  );
}
