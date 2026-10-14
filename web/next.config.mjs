/** @type {import('next').NextConfig} */
export default {
  reactStrictMode: true,
  output: 'standalone',
  eslint: { ignoreDuringBuilds: true },   // lint is run separately (npm run lint)
};
