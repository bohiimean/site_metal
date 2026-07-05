/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './templates/**/*.html',
    './apps/**/*.py',
    './static/**/*.js',
  ],
  // Тема переключается через CSS-переменные — dark: нужен только для редких edge-cases
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['Manrope', 'sans-serif'],
      },
      colors: {
        // Семантические цвета — всегда ссылаются на CSS-переменные.
        // Переключение светлой/тёмной темы происходит в CSS, не здесь.
        surface:     'var(--color-surface)',
        'surface-alt': 'var(--color-surface-alt)',
        'surface-card': 'var(--color-surface-card)',
        primary:     'var(--color-text-primary)',
        muted:       'var(--color-text-muted)',
        accent:      'var(--color-accent)',
        'accent-fg': 'var(--color-accent-fg)',
        border:      'var(--color-border)',
        'border-strong': 'var(--color-border-strong)',
        'footer-bg': 'var(--color-footer-bg)',
        'footer-text': 'var(--color-footer-text)',
        // Hero всегда тёмный в обеих темах
        'hero-bg':   'var(--color-hero-bg)',
        'hero-text': 'var(--color-hero-text)',
      },
      borderRadius: {
        DEFAULT: '3px',
        sm:  '2px',
        md:  '4px',
        full: '9999px',
      },
      letterSpacing: {
        widest: '.12em',
        wider:  '.06em',
        wide:   '.04em',
      },
    },
  },
  plugins: [],
}
