// Compiles the React island(s) into a single static bundle Django can serve.
// Output lands in ../static/js/ so {% static 'js/hero.bundle.js' %} resolves.
import * as esbuild from "esbuild";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const isWatch = process.argv.includes("--watch");

/** @type {import('esbuild').BuildOptions} */
const options = {
  entryPoints: {
    "hero.bundle": "src/main.tsx",
  },
  bundle: true,
  format: "esm",
  target: ["es2020"],
  outdir: "../static/js",
  // shadcn-style "@/..." imports resolve to frontend/src.
  alias: { "@": path.resolve(__dirname, "src") },
  jsx: "automatic",
  minify: !isWatch,
  sourcemap: isWatch,
  legalComments: "none",
  define: {
    "process.env.NODE_ENV": isWatch ? '"development"' : '"production"',
  },
  logLevel: "info",
};

if (isWatch) {
  const ctx = await esbuild.context(options);
  await ctx.watch();
  console.log("watching for changes…");
} else {
  await esbuild.build(options);
  console.log("built static/js/hero.bundle.js");
}
