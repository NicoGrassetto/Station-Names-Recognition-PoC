# Custom Speech training data (English + French)

Custom Speech is **per-locale**, so we train one custom model + endpoint per
language. This project supports two:

- `data/en-US/` — English speakers
- `data/fr-FR/` — French speakers

## Layout

```
data/
  en-US/
    language.txt          # required, UTF-8 BOM
    pronunciation.txt     # optional
    audio/                # optional
      clip001.wav
      clip001.txt
  fr-FR/
    language.txt
    pronunciation.txt
    audio/
```

Folder names must match the BCP-47 locale exactly — they're passed straight to
the Custom Speech REST API.

## Files per locale

### `language.txt` — required
UTF-8 with BOM, one utterance per line. Carrier sentences in the target language
plus the bare station names. **Include both the local-language form AND the
form a speaker of this language is likely to use** (English speakers often say
"Brussels-South"; French speakers say "Bruxelles-Midi" — both are valid).

### `pronunciation.txt` — optional but recommended
Tab-delimited `<displayForm>\t<spokenForm>`, UTF-8 with BOM. Spell phonetically
**in the target language** for words the base model gets wrong.

### `audio/` — optional, biggest accuracy win
WAV / 16 kHz / mono / 16-bit PCM. For each `clipNNN.wav`, a sibling
`clipNNN.txt` with the verbatim transcript. Aim for ≥ 30 minutes per locale.

## Running the trainer

```bash
pip install -r requirements.txt

# Both locales
python scripts/train_custom_speech.py

# Subset
python scripts/train_custom_speech.py fr-FR
```

The script writes `config/custom_speech_endpoints.json`:
```json
{
  "en-US": { "endpoint_id": "abc...", "model": "..." },
  "fr-FR": { "endpoint_id": "def...", "model": "..." }
}
```

## Picking the right model at runtime

Detect / let the user pick the language, then load the matching endpoint:

```python
import json
from azure.cognitiveservices.speech import SpeechConfig

endpoints = json.load(open("config/custom_speech_endpoints.json"))

def make_speech_config(locale: str, token: str, region: str) -> SpeechConfig:
    cfg = SpeechConfig(auth_token=f"aad#resourceId#{token}", region=region)
    cfg.speech_recognition_language = locale
    cfg.endpoint_id = endpoints[locale]["endpoint_id"]
    return cfg
```

Custom endpoints can't be combined with `AutoDetectSourceLanguageConfig`. Either
let the user pick the language in the UI, or do a quick base-model auto-detect
pass first and then switch to the matching custom endpoint.
