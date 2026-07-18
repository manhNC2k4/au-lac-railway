/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  async rewrites() {
    const apiServer = process.env.API_SERVER_URL ?? "http://127.0.0.1:8000";
    return [{ source: "/api/v1/:path*", destination: `${apiServer}/api/v1/:path*` }];
  },
};

export default nextConfig;
