#!/usr/bin/env bash
# One-time setup: Python deps (uv, Python 3.12), web deps, and model download/warm-up.
set -euo pipefail
cd "$(dirname "$0")/.."
command -v uv >/dev/null || { echo "uv gerekli: https://docs.astral.sh/uv/"; exit 1; }
command -v claude >/dev/null || { echo "Claude Code CLI gerekli ve giriş yapılmış olmalı (claude login)"; exit 1; }
(cd server && uv sync)
(cd web && npm install)
[ -f .env ] || cp .env.example .env
mkdir -p content/vocab
[ -f content/vocab/warriner_vad.csv ] || {
  echo "Kelime beyni için duygu verisi indiriliyor (Warriner et al. 2013, CC BY-NC-ND, ~1 MB)…"
  curl -sL "https://raw.githubusercontent.com/JULIELab/XANEW/master/Ratings_Warriner_et_al.csv" -o content/vocab/warriner_vad.csv
}
echo "Modeller indiriliyor (ilk sefer birkaç dakika sürer, ~2 GB)…"
(cd server && uv run python -c "
import pathlib
from ingpro.config import settings
from ingpro.voice.engines import WhisperSTT, ChatterboxTTS, ensure_voice_ref
WhisperSTT(settings.stt_model).warm_up()
ref = ensure_voice_ref(settings.voice_ref, settings.tts_voice)
ChatterboxTTS(settings.chatterbox_model, ref)
print('hazır')")
