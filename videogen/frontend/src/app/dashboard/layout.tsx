import { UserButton } from "@clerk/nextjs";
import Link from "next/link";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-[#0f0f0f]">
      <nav className="flex items-center justify-between px-8 py-4 border-b border-[#222]">
        <Link
          href="/"
          className="text-xl font-bold bg-gradient-to-r from-orange-500 to-pink-500 bg-clip-text text-transparent"
        >
          VideoGen
        </Link>
        <UserButton />
      </nav>
      <div className="max-w-7xl mx-auto px-6 py-8">{children}</div>
    </div>
  );
}
