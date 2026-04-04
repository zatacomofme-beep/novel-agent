import { defineConfig } from "vitest/config";


export default defineConfig({
  test: {
    include: [],
    exclude: ["tests/e2e/**", "node_modules/**", ".next/**"],
    passWithNoTests: true,
  },
});
