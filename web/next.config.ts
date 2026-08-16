import type { NextConfig } from "next";

const BRIDGE = process.env.BRIDGE_BASE_URL ?? "http://127.0.0.1:8787";

const nextConfig: NextConfig = {
  // The browser talks to the bridge on same origin (/api/*); we proxy to the
  // real FastAPI bridge so no CORS / port leakage in the client bundle.
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${BRIDGE}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
