const { PHASE_DEVELOPMENT_SERVER } = require('next/constants');

module.exports = (phase) => {
  const isDevServer = phase === PHASE_DEVELOPMENT_SERVER;
  const backendOrigin = process.env.BACKEND_ORIGIN || 'http://127.0.0.1:8000';

  /** @type {import('next').NextConfig} */
  const nextConfig = {
    reactStrictMode: true,
    trailingSlash: true,
    experimental: {
      optimizePackageImports: ['@heroui/react', 'lucide-react'],
    },
    images: {
      unoptimized: true,
    },
  };

  if (isDevServer) {
    return {
      ...nextConfig,
      async rewrites() {
        return [
          {
            source: '/api/:path*',
            destination: `${backendOrigin}/api/:path*`,
          },
          {
            source: '/health',
            destination: `${backendOrigin}/health`,
          },
          {
            source: '/version',
            destination: `${backendOrigin}/version`,
          },
        ];
      },
    };
  }

  return {
    ...nextConfig,
    output: 'export',
  };
};
