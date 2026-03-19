import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#101417",
        paper: "#f5efe3",
        copper: "#8b4a2b",
        moss: "#566246",
      },
    },
  },
  plugins: [],
};

export default config;
