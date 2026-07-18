import type { Config } from "tailwindcss";

/**
 * Design tokens theo mockup "Hệ thống thiết kế Âu Lạc Railway":
 * Navy #082B5C · Primary Blue #1261C9 · Light Blue #EAF3FF
 * Success #43B96B · Warning #E9A93A · Danger #E5484D
 * Heading #102A56 · Muted #667085
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        navy: "#082B5C",
        primary: {
          DEFAULT: "#1261C9",
          soft: "#EAF3FF",
          dark: "#0E4EA3",
        },
        ink: "#102A56",
        muted: "#667085",
        success: {
          DEFAULT: "#2F9E58",
          soft: "#E6F6EC",
        },
        warning: {
          DEFAULT: "#B87508",
          soft: "#FDF3E1",
        },
        danger: {
          DEFAULT: "#D93843",
          soft: "#FDEBEC",
        },
        surface: "#EEF4FC",
        line: "#E4E9F2",
      },
      fontSize: {
        base: ["15px", "1.6"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(16, 42, 86, 0.06), 0 1px 3px rgba(16, 42, 86, 0.08)",
      },
      borderRadius: {
        xl: "0.75rem",
        "2xl": "1rem",
      },
    },
  },
  plugins: [],
};
export default config;
