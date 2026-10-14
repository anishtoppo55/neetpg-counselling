import type { Config } from 'tailwindcss';

/** Theme taken from the reference dashboard: light slate page, white cards, indigo primary, soft shadows. */
export default {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        page: '#eef1f6',
        ink: { DEFAULT: '#0f172a', soft: '#475569', faint: '#94a3b8' },
        brand: {
          50: '#eef2ff', 100: '#e0e7ff', 200: '#c7d2fe', 300: '#a5b4fc', 400: '#818cf8',
          500: '#6366f1', 600: '#4f46e5', 700: '#4338ca', 900: '#312e81',
        },
        status: {
          safe: '#16a34a', good: '#65a30d', borderline: '#f59e0b',
          later: '#7c3aed', reach: '#0ea5e9', unlikely: '#94a3b8',
        },
      },
      borderRadius: { card: '18px', pill: '999px' },
      boxShadow: {
        card: '0 1px 2px rgba(15,23,42,.04), 0 8px 24px -16px rgba(15,23,42,.18)',
        pop: '0 12px 32px -12px rgba(15,23,42,.28)',
      },
      fontFamily: { sans: ['var(--font-sans)', 'system-ui', 'sans-serif'] },
    },
  },
  plugins: [],
} satisfies Config;
