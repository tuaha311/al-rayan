/** @type {import('tailwindcss').Config} */
export default {
  // Only scan the React island sources so we emit exactly the classes they use
  // (including responsive md: variants the frozen Next.js CSS is missing).
  content: ["./src/**/*.{ts,tsx}"],
  // shadcn components use dark: variants gated on a .dark ancestor class.
  darkMode: ["class"],
  // Preflight is disabled so this stylesheet only adds utilities and does not
  // reset/override the rest of the Django page (which uses the frozen bundle).
  corePlugins: { preflight: false },
  theme: {
    extend: {
      // shadcn design tokens, mapped to the CSS variables in src/tailwind.css.
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
      },
    },
  },
  plugins: [],
};
