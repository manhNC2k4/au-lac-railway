/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  // Standalone deployment does not bundle `sharp`; serve the original high-resolution
  // brand/hero assets so image requests cannot terminate the frontend process.
  images: { unoptimized: true },
  async rewrites() {
    const apiServer = process.env.API_SERVER_URL ?? "http://127.0.0.1:8000";
    return [{ source: "/api/v1/:path*", destination: `${apiServer}/api/v1/:path*` }];
  },
};

export default nextConfig;
