import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "video-generator.transilienceapi.com",
      },
    ],
  },
};

export default nextConfig;
