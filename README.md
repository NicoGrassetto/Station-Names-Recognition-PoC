# Station Names Recognition PoC

<p align="center">
  <img src="assets/nmbs-sncb.png" alt="NMBS/SNCB" width="360" />
</p>

A proof-of-concept voice booking assistant for **NMBS/SNCB** (Belgian Railways) train tickets. The user converses naturally with a [GPT Realtime](https://learn.microsoft.com/azure/ai-services/openai/realtime-audio-quickstart) agent that walks them through a booking flow (language → product tier → destination → details → confirmation → receipt). For the destination step — where Belgian station names are notoriously hard to recognise across French, Flemish and English accents — audio is also routed to a **custom-trained [Azure AI Speech](https://learn.microsoft.com/azure/ai-services/speech-service/) endpoint** whose transcription is injected back into the Realtime session as ground truth.

> **Warning — Not production-ready.** No authentication, no TLS, permissive CORS, mock payment/SMS tools. Localhost / demo use only.

<p align="center">
  <a href="#current-set-up">Current set-up</a> |
  <a href="#how-it-works">How it works</a> |
  <a href="#project-structure">Project Structure</a> |
  <a href="#quick-start">Quick Start</a> |
  <a href="#customization">Customization</a>
</p>

## Current set-up

<p align="center">
  <video src="assets/current-setup-demo.mp4" controls width="480"></video>
</p>

> If the video does not render in your Markdown viewer, watch it directly: [assets/current-setup-demo.mp4](assets/current-setup-demo.mp4).

## How it works

The app is driven by a small **state machine** in [package/](package/) (`LanguageSelectionState` → `ProductSelectionState` → `DestinationSelectionState` → `DetailsSelectionState` → `ConfirmationSelectionState` → `EndState`). Each state maps to a dedicated `.prompty` file in [prompts/](prompts/), and each transition is triggered by a tool call from the Realtime model.

```
LanguageSelection ──▶ ProductSelection ──▶ DestinationSelection ──▶ DetailsSelection ──▶ ConfirmationSelection ──▶ End
   (fr/nl/en)          (tier)               (Azure Speech)            (date, return)        (mock SMS)              (mock receipt)
```

Key behaviours:

- **Per-session state** — [src/booking.py](src/booking.py) holds a `BookingContext` per WebSocket. Every state change pushes a fresh prompt to the Realtime session via `session.update`.
- **Azure Speech routing** — In `DestinationSelectionState`, audio is forked: it still feeds Realtime VAD for turn detection, but auto-response is suppressed. On `speech_stopped`, the buffered PCM16 is sent to a custom Azure Speech endpoint (locale-specific: `fr-FR`, `en-US`, with Flemish currently falling back to `fr-FR`), and the resulting station name is injected as a `[Azure Speech transcription]: <station>` user message before manually triggering `response.create`.
- **Mock fulfilment** — The confirmation and end states use `@function_tool`s in [src/booking.py](src/booking.py) to simulate sending an SMS confirmation and emailing a receipt.
- **Custom Speech training** — [scripts/train_custom_speech.py](scripts/train_custom_speech.py) trains/deploys language and (optionally) acoustic models from data in [data/](data/); manifests for active endpoints live in [config/custom_speech_endpoints.json](config/custom_speech_endpoints.json).

## Project Structure

```
├── assets/                         # Static images and demo video
├── config/
│   ├── custom_speech_endpoints.json  # Custom Azure Speech endpoint manifest
│   ├── session_defaults.yaml       # Shared Realtime session baseline
│   └── modes/                      # Mode presets (booking, voice_assistant, …)
├── data/                           # Training data for custom Speech (per locale)
│   ├── en-US/{language.txt, pronunciation.txt, audio/}
│   └── fr-FR/{language.txt, pronunciation.txt, audio/}
├── frontend/                       # Vite + React UI
├── hooks/                          # azd post-provision hooks
├── infra/                          # Bicep IaC (Azure OpenAI + Speech + RBAC)
├── package/                        # State machine: State + 6 subclasses
├── prompts/                        # One .prompty per state (booking flow)
├── raw/                            # Raw audio captures (per locale)
├── scripts/
│   ├── prep_audio.sh               # Convert raw audio for Speech training
│   ├── train_custom_speech.py      # Train + deploy custom Speech models
│   └── test_custom_speech.py       # Smoke-test a custom endpoint
├── src/
│   ├── agent.py                    # RealtimeAgent factory (booking + legacy)
│   ├── booking.py                  # BookingContext, Speech bridge, tools
│   └── main.py                     # FastAPI WebSocket server
├── tools/                          # Generic @function_tools (weather, time, …)
├── azure.yaml                      # azd project config
├── requirements.txt
└── README.md
```

## Quick Start

```bash
azd auth login
azd up                  # provisions Azure OpenAI + Speech, writes .env via post-provision
pip install -r requirements.txt

# Backend
python3 -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

# Frontend (in another terminal)
cd frontend && npm install && npm run dev
```

Open the URL printed by Vite (typically `http://localhost:5173`), grant mic access, and start talking.

## Manual Setup

### 1. Deploy infrastructure

```bash
azd auth login
azd up
```

You will be prompted for an environment name, subscription and region (`Sweden Central` or `East US 2` recommended). After provisioning, a `.env` is written with:

```
AZURE_OPENAI_ENDPOINT="https://<your-resource>.openai.azure.com/"
AZURE_OPENAI_DEPLOYMENT="gpt-realtime-1-5"
AZURE_SPEECH_REGION="<region>"
AZURE_SPEECH_RESOURCE_ID="/subscriptions/.../Microsoft.CognitiveServices/accounts/<speech-account>"
```

Authentication uses `DefaultAzureCredential` for both Azure OpenAI and Azure Speech — no API keys.

Optional environment variables:

| Variable | Default | Description |
|---|---|---|
| `ALLOWED_ORIGINS` | `http://localhost:5173,http://localhost:8000` | Comma-separated CORS origins |
| `MAX_SESSIONS` | `10` | Max concurrent WebSocket sessions |

### 2. (Optional) Train custom Speech endpoints

The destination step is gated by custom Speech endpoints listed in [config/custom_speech_endpoints.json](config/custom_speech_endpoints.json). To retrain from your own audio:

```bash
# 1. Drop raw audio in raw/<locale>/, then normalise
./scripts/prep_audio.sh

# 2. Train (and deploy) language + acoustic models
python3 scripts/train_custom_speech.py            # all locales
python3 scripts/train_custom_speech.py --skip-acoustic fr-FR  # language model only

# 3. Smoke-test a clip
python3 scripts/test_custom_speech.py fr-FR /path/to/clip.wav
```

Update `config/custom_speech_endpoints.json` with the new endpoint IDs when training finishes.

### 3. Run

```bash
python3 -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
cd frontend && npm run dev
```

### 4. Tear down

```bash
azd down
```

## Customization

### Booking prompts

One `.prompty` per state in [prompts/](prompts/):

| Prompt | Used by | Purpose |
|---|---|---|
| `language_selection.prompty` | `LanguageSelectionState` | Greet the user, pick fr/nl/en |
| `product_selection.prompty` | `ProductSelectionState` | Standard / first / weekend / youth |
| `destination_selection.prompty` | `DestinationSelectionState` | Trust `[Azure Speech transcription]: …` |
| `details_selection.prompty` | `DetailsSelectionState` | Date, one-way / return |
| `confirmation_selection.prompty` | `ConfirmationSelectionState` | Confirm + trigger mock SMS |
| `end.prompty` | `EndState` | Offer receipt by email/SMS |

To tweak tone or instructions, edit the `system:` block of the relevant file. Keep the destination prompt's instruction to **trust** the Azure Speech transcription — that's what makes station names work.

### State machine

The flow is hard-coded in [package/state.py](package/state.py). To insert a new step (e.g. seat selection), subclass `State`, point `prompt_name` at a new prompty, return the next state from `confirm()`, then wire a tool in [src/booking.py](src/booking.py) that mutates the context and calls `ctx.state.confirm()`.

### Function tools

Booking tools (`set_language`, `set_tier`, `set_destination`, `lookup_trains`, `set_details`, `send_purchase_confirmation_to_phone`, `send_receipt`, `cancel_step`) are built in `make_booking_tools(ctx)` in [src/booking.py](src/booking.py). Each gates on the current state and triggers a transition. Generic, state-agnostic tools live in [tools/](tools/) and are exported via `ALL_TOOLS`.

### Session settings

Baseline Realtime session settings are in [config/session_defaults.yaml](config/session_defaults.yaml); per-mode overrides in [config/modes/](config/modes/) (e.g. `booking.yaml` disables Whisper input transcription since Azure Speech handles destination words).

> **Note:** The Realtime API enforces a **30-minute maximum session duration**. Plan for renewal if you need longer interactions.

## Security Considerations

This PoC is intended for **local development and demos** only. Before any wider deployment:

- **Add authentication** — The WebSocket and HTTP endpoints have no auth. Add API keys or Microsoft Entra ID.
- **Enable HTTPS** — Run behind a TLS-terminating reverse proxy. Audio over plain WebSocket is unencrypted.
- **Restrict CORS** — Set `ALLOWED_ORIGINS` to your specific frontend domain(s).
- **Replace mock fulfilment** — `send_purchase_confirmation_to_phone` and `send_receipt` are stubs. Wire them to a real payment/messaging provider with proper validation.
- **Lock down infrastructure** — The Bicep templates deploy Azure OpenAI and Speech with `publicNetworkAccess: Enabled`. Use Private Endpoints in production.
- **Rate limiting** — `MAX_SESSIONS` is a concurrency cap, not real rate limiting.
