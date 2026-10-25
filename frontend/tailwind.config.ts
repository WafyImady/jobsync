import type { Config } from 'tailwindcss'

const config: Config = {
  darkMode: 'class',
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        "surface": "#031427",
        "on-surface": "#d3e4fe",
        "surface-variant": "#26364a",
        "on-surface-variant": "#c2c6d6",
        "surface-container-lowest": "#000f21",
        "surface-container-low": "#0b1c30",
        "surface-container": "#102034",
        "surface-container-high": "#1b2b3f",
        "primary": "#adc6ff",
        "on-primary": "#002e6a",
        "secondary": "#4edea3",
        "tertiary": "#ffb95f",
        "outline": "#8c909f",
        "outline-variant": "#424754"
      }
    }
  },
  plugins: [],
}
export default config