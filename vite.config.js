import { defineConfig } from 'vite';
import { resolve } from 'path';
import { readdirSync, statSync } from 'fs';

// Auto-discover all JS and CSS files in static/
function getEntries(dir, ext) {
  const entries = {};
  try {
    const files = readdirSync(dir);
    for (const file of files) {
      const full = resolve(dir, file);
      if (statSync(full).isFile() && file.endsWith(ext) && !file.endsWith('.min.js')) {
        entries[file.replace(ext, '')] = full;
      }
    }
  } catch (e) { /* dir may not exist */ }
  return entries;
}

const jsEntries = getEntries('static/js', '.js');
const cssEntries = getEntries('static/css', '.css');

export default defineConfig({
  build: {
    outDir: 'staticfiles/dist',
    emptyOutDir: true,
    manifest: true,
    rollupOptions: {
      input: {
        ...jsEntries,
        ...cssEntries,
      },
    },
    cssMinify: true,
    minify: 'terser',
    sourcemap: false,
  },
  resolve: {
    alias: {
      '@': resolve(__dirname, 'static'),
    },
  },
});
