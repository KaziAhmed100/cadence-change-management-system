/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  // The frontend talks to the FastAPI backend. The URL differs between
  // local dev (docker-compose) and prod (Railway), so we read it from env.
  env: {
    NEXT_PUBLIC_API_BASE_URL: process.env.NEXT_PUBLIC_API_BASE_URL,
  },

  // Keep image optimization permissive for now; we'll tighten allowed
  // remote patterns when we actually start loading external images.
  images: {
    remotePatterns: [],
  },
};

module.exports = nextConfig;
