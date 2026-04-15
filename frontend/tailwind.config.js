/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        surface:          'var(--surface)',
        surfaceLow:       'var(--surface-low)',
        surfaceContainer: 'var(--surface-container)',
        surfaceHigh:      'var(--surface-high)',
        surfaceHighest:   'var(--surface-highest)',
        onSurface:        'var(--on-surface)',
        onSurfaceMuted:   'var(--on-surface-muted)',
        onSurfaceSubtle:  'var(--on-surface-subtle)',
        primary:          'var(--primary)',
        primaryDim:       'var(--primary-dim)',
        primaryGlow:      'var(--primary-glow)',
        onPrimary:        'var(--on-primary)',
        danger:           'var(--danger)',
        warning:          'var(--warning)',
        border:           'var(--border)',
        borderAccent:     'var(--border-accent)',
      },
      fontFamily: {
        sans:    ['Inter', 'system-ui', 'sans-serif'],
        display: ['Space Grotesk', 'system-ui', 'sans-serif'],
      },
      gridTemplateColumns: {
        workspace: 'minmax(0,1fr) 340px',
        sidebar:   '360px minmax(0,1fr)',
        profile:   'minmax(0,1fr) 280px',
      },
    },
  },
  plugins: [],
}
