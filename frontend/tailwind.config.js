/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Instrument Sans"', 'system-ui', 'sans-serif'],
        serif: ['"Instrument Serif"', 'Georgia', 'serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      colors: {
        /* Ink ramp — 0 brightest, 9 faintest */
        ink: {
          0: 'var(--ink-0)',
          1: 'var(--ink-1)',
          2: 'var(--ink-2)',
          3: 'var(--ink-3)',
          4: 'var(--ink-4)',
          5: 'var(--ink-5)',
          6: 'var(--ink-6)',
          7: 'var(--ink-7)',
          8: 'var(--ink-8)',
          9: 'var(--ink-9)',
        },

        /* Signals — one accent, one caution, one negative */
        acid: {
          DEFAULT: 'var(--acid)',
          ink: 'var(--acid-ink)',
          soft: 'var(--acid-soft)',
          wash: 'var(--acid-wash)',
        },
        caution: {
          DEFAULT: 'var(--caution)',
          solid: 'var(--caution-solid)',
        },
        alert: 'var(--alert)',

        /* Semantic tokens */
        background: 'var(--background)',
        foreground: 'var(--foreground)',
        card: 'var(--card)',
        primary: 'var(--primary)',
        'primary-foreground': 'var(--primary-foreground)',
        secondary: 'var(--secondary)',
        'secondary-foreground': 'var(--secondary-foreground)',
        muted: 'var(--muted)',
        'muted-foreground': 'var(--muted-foreground)',
        border: 'var(--border)',
        input: 'var(--input)',
        popover: 'var(--popover)',
        'popover-foreground': 'var(--popover-foreground)',
        accent: 'var(--accent)',
        'accent-foreground': 'var(--accent-foreground)',
        destructive: 'var(--destructive)',
        'destructive-foreground': 'var(--destructive-foreground)',
        ring: 'var(--ring)',
        'chart-1': 'var(--chart-1)',
        'chart-2': 'var(--chart-2)',
        'chart-3': 'var(--chart-3)',
        'chart-4': 'var(--chart-4)',
      },
      borderColor: {
        hair: 'var(--hair)',
        'hair-soft': 'var(--hair-soft)',
        'hair-row': 'var(--hair-row)',
        'hair-rule': 'var(--hair-rule)',
        'hair-control': 'var(--hair-control)',
      },
      backgroundColor: {
        hair: 'var(--hair)',
        track: 'var(--track)',
      },
      spacing: {
        nav: 'var(--nav-h)',
        gutter: 'var(--gutter)',
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
      letterSpacing: {
        eyebrow: '0.14em',
        'eyebrow-wide': '0.16em',
        tightest: '-0.025em',
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
