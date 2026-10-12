import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Required for the production Docker image (standalone output copies only what's needed)
  output: "standalone",
  skipTrailingSlashRedirect: true,
  async rewrites() {
    // In Docker container: INTERNAL_API_URL is set to http://backend:8001
    // In local development outside Docker: defaults to http://localhost:8001
    const internalApiUrl = process.env.INTERNAL_API_URL || "http://localhost:8001";
    return [
      {
        source: "/api/:path*",
        destination: `${internalApiUrl}/api/:path*`,
      },
      {
        source: "/health",
        destination: `${internalApiUrl}/health`,
      },
    ];
  },
};

export default nextConfig;
