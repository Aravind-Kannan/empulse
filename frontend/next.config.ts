import type { NextConfig } from "next";
import path from "node:path";
import { fileURLToPath } from "node:url";

const configDir = path.dirname(fileURLToPath(import.meta.url));

const nextConfig: NextConfig = {
  transpilePackages: ["recharts"],
  // Prevent Next from picking ~/package-lock.json as the workspace root.
  outputFileTracingRoot: configDir,
};

export default nextConfig;
