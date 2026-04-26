#!/usr/bin/env bash
# Convert raw recordings (.m4a, .wav, .mp3) into the WAV format Custom Speech requires.
#
# Usage:
#   scripts/prep_audio.sh en-US
#   scripts/prep_audio.sh fr-FR
#   scripts/prep_audio.sh                # processes every locale folder under raw/
#
# Reads from:  raw/<locale>/*.{m4a,wav,mp3}
# Writes to:   data/<locale>/audio/*.wav   (16 kHz, mono, 16-bit PCM)
#
# Filenames are preserved (clip001.m4a -> clip001.wav).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RAW="$ROOT/raw"

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg not found. Install with: brew install ffmpeg" >&2
  exit 1
fi

if [ ! -d "$RAW" ]; then
  echo "No raw/ folder at $RAW. Drop your iPhone recordings into raw/<locale>/ first." >&2
  exit 1
fi

if [ "$#" -gt 0 ]; then
  LOCALES=("$@")
else
  LOCALES=()
  for d in "$RAW"/*/; do
    [ -d "$d" ] || continue
    LOCALES+=("$(basename "$d")")
  done
  if [ "${#LOCALES[@]}" -eq 0 ]; then
    echo "No locale subfolders under raw/. Expected raw/en-US/, raw/fr-FR/, etc." >&2
    exit 1
  fi
fi

for locale in "${LOCALES[@]}"; do
  src="$RAW/$locale"
  dst="$ROOT/data/$locale/audio"
  if [ ! -d "$src" ]; then
    echo "[$locale] no folder $src — skipping" >&2
    continue
  fi
  mkdir -p "$dst"
  count=0
  shopt -s nullglob nocaseglob
  for f in "$src"/*.m4a "$src"/*.wav "$src"/*.mp3 "$src"/*.aac "$src"/*.mp4; do
    base="$(basename "${f%.*}")"
    out="$dst/${base}.wav"
    ffmpeg -y -loglevel error -i "$f" \
      -ac 1 -ar 16000 -sample_fmt s16 -c:a pcm_s16le "$out"
    count=$((count + 1))
  done
  shopt -u nullglob nocaseglob
  echo "[$locale] converted $count clips -> $dst"
done
