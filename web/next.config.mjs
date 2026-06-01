/** @type {import('next').NextConfig} */
const API = process.env.BOT_API_URL || "http://localhost:8000";

const nextConfig = {
  // Proxy data calls to the Python FastAPI backend (avoids CORS in the browser
  // and lets the app use relative URLs in dev + prod).
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API}/api/:path*` }];
  },
};

export default nextConfig;
