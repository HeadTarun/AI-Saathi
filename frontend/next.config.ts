import type { NextConfig } from "next";
import { dirname } from "path";
import { fileURLToPath } from "url";

const appRoot = dirname(fileURLToPath(import.meta.url));
const workspaceRoot = dirname(appRoot);
const backendUrl = (
  process.env.BACKEND_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8080"
).replace(/\/$/, "");

const nextConfig: NextConfig = {
  turbopack: {
    root: workspaceRoot,
  },
  async rewrites() {
    return [
      {
        source: "/study/:path*",
        destination: `${backendUrl}/study/:path*`,
      },
      {
        source: "/health",
        destination: `${backendUrl}/health`,
      },
    ];
  },
};

export default nextConfig;
