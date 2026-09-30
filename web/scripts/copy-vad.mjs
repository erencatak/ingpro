// Copies the VAD worklet, Silero model and onnxruntime wasm into public/vad (served as static files)
import { cpSync, mkdirSync, readdirSync } from "node:fs";

const out = "public/vad";
mkdirSync(out, { recursive: true });
const vad = "node_modules/@ricky0123/vad-web/dist";
for (const f of ["vad.worklet.bundle.min.js", "silero_vad_v5.onnx"]) cpSync(`${vad}/${f}`, `${out}/${f}`);
const ort = "node_modules/onnxruntime-web/dist";
for (const f of readdirSync(ort)) if (/^ort-wasm-simd-threaded\.(wasm|mjs)$/.test(f)) cpSync(`${ort}/${f}`, `${out}/${f}`);
