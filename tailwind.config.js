/** @type {import('tailwindcss').Config} */
// Say It — design tokens. Brand palette is authoritative; a trimmed shadcn
// semantic layer (border/input/ring/background/foreground/primary/muted/
// popover/card/destructive) is kept for primitive components and mapped to the
// light brand palette in src/index.css. Brand hexes below MIRROR the CSS vars in
// src/index.css — keep the two in sync (index.css is the source of truth).
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // ---- Brand (Say It) ----
        canvas: { DEFAULT: "#FFFFFF", soft: "#FAFAFC" }, // frameless window fill
        ink: { DEFAULT: "#0B1640", secondary: "#52658F", tertiary: "#8792AD" }, // navy text ramp
        secondary: "#52658F",            // alias -> text/bg/border-secondary (muted blue-gray)
        accent: {                        // blue-violet primary
          DEFAULT: "#5A5BFF",
          soft: "#ECEBFF",               // tint: active-nav pill, glow, hover surface
          deep: "#4644E0",               // pressed/hover ink
        },
        teal: {                          // success: Ready dot + audio level meter
          DEFAULT: "#10B981",
          soft: "#D6F3E8",               // meter track / subtle fill
          deep: "#0E9E74",
        },
        blob: { purple: "#C8B8FF", pink: "#F2C8EE", cyan: "#C8EAF4" }, // background blobs
        glass: "rgba(255,255,255,0.72)", // bg-glass (alpha baked in)
        hairline: "rgba(100,120,200,0.16)", // border-hairline

        // ---- shadcn primitive layer (light-mapped in index.css) ----
        border: "var(--border)",
        input: "var(--input)",
        ring: "var(--ring)",
        background: "var(--background)",
        foreground: "var(--foreground)",
        primary: { DEFAULT: "var(--primary)", foreground: "var(--primary-foreground)" },
        muted: { DEFAULT: "var(--muted)", foreground: "var(--muted-foreground)" },
        popover: { DEFAULT: "var(--popover)", foreground: "var(--popover-foreground)" },
        card: { DEFAULT: "var(--card)", foreground: "var(--card-foreground)" },
        destructive: { DEFAULT: "var(--destructive)", foreground: "var(--destructive-foreground)" },
      },
      fontFamily: {
        ui: ["Inter", "system-ui", "-apple-system", "sans-serif"],
        display: ["Manrope", "Inter", "system-ui", "sans-serif"],
        hand: ["Caveat", "cursive"],
      },
      // Type scale — sizes/line-heights/weights live as CSS vars in index.css.
      // Usage: `text-title font-display text-ink`, `text-body`, `text-caption text-secondary`.
      fontSize: {
        display: ["var(--fs-display)", { lineHeight: "var(--lh-display)", fontWeight: "700", letterSpacing: "-0.02em" }],
        title: ["var(--fs-title)", { lineHeight: "var(--lh-title)", fontWeight: "600", letterSpacing: "-0.01em" }],
        body: ["var(--fs-body)", { lineHeight: "var(--lh-body)", fontWeight: "400" }],
        label: ["var(--fs-label)", { lineHeight: "var(--lh-label)", fontWeight: "500" }],
        caption: ["var(--fs-caption)", { lineHeight: "var(--lh-caption)", fontWeight: "400" }],
      },
      borderRadius: {
        // shadcn scale (relative to --radius=16px)
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
        // brand scale
        field: "12px",
        card: "16px",
        window: "20px",
        pill: "9999px",
      },
      boxShadow: {
        "soft-xs": "0 1px 2px rgba(70,80,160,0.08)",
        xs: "0 1px 2px rgba(70,80,160,0.08)", // alias so `shadow-xs` resolves (Tailwind v3 has none)
        "soft-sm": "0 4px 14px rgba(70,80,160,0.10)",
        soft: "0 8px 24px rgba(70,80,160,0.12)",
        "soft-lg": "0 16px 40px rgba(70,80,160,0.14)",
        glass: "0 8px 30px rgba(70,80,160,0.12), inset 0 1px 0 rgba(255,255,255,0.6)",
      },
      // Subtle drift for SoftBlobBackground blobs (gated by motion-safe: in the component).
      keyframes: {
        blobDrift: {
          "0%,100%": { transform: "translate(0,0) scale(1)" },
          "33%": { transform: "translate(3%,-4%) scale(1.05)" },
          "66%": { transform: "translate(-3%,3%) scale(0.97)" },
        },
      },
      animation: {
        "blob-drift": "blobDrift 18s ease-in-out infinite",
        "blob-drift-slow": "blobDrift 26s ease-in-out infinite",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
}
