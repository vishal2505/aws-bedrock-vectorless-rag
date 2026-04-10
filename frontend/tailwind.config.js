/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      colors: {
        surface: {
          DEFAULT: 'rgba(255,255,255,0.03)',
          hover:   'rgba(255,255,255,0.06)',
          active:  'rgba(255,255,255,0.08)',
        },
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-mesh':
          'radial-gradient(at 40% 20%, hsla(260,60%,50%,0.15) 0px, transparent 50%), ' +
          'radial-gradient(at 80% 0%, hsla(220,70%,50%,0.12) 0px, transparent 50%), ' +
          'radial-gradient(at 0% 50%, hsla(280,60%,50%,0.1) 0px, transparent 50%), ' +
          'radial-gradient(at 80% 50%, hsla(200,70%,50%,0.1) 0px, transparent 50%), ' +
          'radial-gradient(at 0% 100%, hsla(240,70%,50%,0.12) 0px, transparent 50%)',
      },
      animation: {
        'shimmer':       'shimmer 2s linear infinite',
        'glow-pulse':    'glow-pulse 3s ease-in-out infinite',
        'float':         'float 6s ease-in-out infinite',
        'float-delayed': 'float 6s ease-in-out 2s infinite',
        'float-slow':    'float 8s ease-in-out 1s infinite',
        'spin-slow':     'spin 4s linear infinite',
        'fade-up':       'fade-up 0.4s ease forwards',
        'slide-in-right':'slide-in-right 0.35s ease forwards',
      },
      keyframes: {
        shimmer: {
          '0%':   { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        'glow-pulse': {
          '0%, 100%': { opacity: '0.6' },
          '50%':      { opacity: '1' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%':      { transform: 'translateY(-20px)' },
        },
        'fade-up': {
          from: { opacity: '0', transform: 'translateY(12px)' },
          to:   { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-in-right': {
          from: { opacity: '0', transform: 'translateX(24px)' },
          to:   { opacity: '1', transform: 'translateX(0)' },
        },
      },
      boxShadow: {
        'glow-sm': '0 0 15px rgba(99,102,241,0.2)',
        'glow':    '0 0 30px rgba(99,102,241,0.25)',
        'glow-lg': '0 0 60px rgba(99,102,241,0.3)',
        'glow-violet': '0 0 40px rgba(139,92,246,0.3)',
        'inner-light': 'inset 0 1px 0 rgba(255,255,255,0.1)',
      },
    },
  },
  plugins: [],
}
