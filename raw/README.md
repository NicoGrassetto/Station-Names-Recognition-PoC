# Raw recordings — drop iPhone files here

Place your unconverted recordings (`.m4a`, `.wav`, `.mp3`) into a subfolder
named after the locale they belong to:

```
raw/
  en-US/
    clip001.m4a
    clip002.m4a
    ...
  fr-FR/
    clip001.m4a
    ...
```

Then run:

```bash
chmod +x scripts/prep_audio.sh   # one time
scripts/prep_audio.sh            # converts every locale found here
# or scripts/prep_audio.sh fr-FR # just one
```

The script converts each file to **16 kHz mono 16-bit PCM WAV** and writes the
result to `data/<locale>/audio/`, keeping the same filename. After that, write
each `clipNNN.txt` transcript next to its `.wav` and run the trainer.

> This folder is in `.gitignore` — raw audio doesn't get committed.
