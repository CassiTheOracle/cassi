import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  devIndicators: false,
  async rewrites() {
    return [
      // Agno-compatible routes: map root-level paths → /api/ handlers
      { source: '/health', destination: '/api/health' },
      { source: '/agents', destination: '/api/agents' },
      { source: '/agents/:path*', destination: '/api/agents/:path*' },
      { source: '/sessions', destination: '/api/sessions' },
      { source: '/sessions/:path*', destination: '/api/sessions/:path*' },
      { source: '/teams', destination: '/api/teams' },
      { source: '/teams/:path*', destination: '/api/teams/:path*' },
    ]
  },
}

export default nextConfig
