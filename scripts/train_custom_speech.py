"""
Custom Speech end-to-end trainer (multi-locale).

Trains one Custom Speech model + endpoint per locale found under ./data/.
Authentication is fully passwordless via DefaultAzureCredential, leveraging
the role assignments created in the Bicep template:
  - You              -> Storage Blob Data Contributor (upload data)
  - Speech identity  -> Storage Blob Data Reader     (ingest data, BYOS)
  - You              -> Cognitive Services Speech Contributor (manage Custom Speech)

Required env (auto-loaded from .env, written by `azd env get-values > .env`):
    AZURE_SPEECH_REGION
    AZURE_STORAGE_ACCOUNT
    AZURE_STORAGE_CONTAINER

Expected ./data layout (one subfolder per locale; folder name = BCP-47 locale):
    data/
      en-US/
        language.txt                 # required, UTF-8 BOM
        pronunciation.txt            # optional
        audio/                       # optional
          clip001.wav
          clip001.txt
      fr-FR/
        language.txt
        ...
      nl-BE/
        language.txt
        ...

Run:
    pip install -r requirements.txt
    python scripts/train_custom_speech.py                 # all locales found
    python scripts/train_custom_speech.py fr-FR nl-BE     # subset
"""

from __future__ import annotations

import io
import json
import os
import sys
import time
import zipfile
from pathlib import Path

import httpx
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
PROJECT_PREFIX = os.getenv("CUSTOM_SPEECH_PROJECT", "station-names")
POLL_INTERVAL_S = 15
POLL_TIMEOUT_S = 60 * 60  # 1h


def env(name: str) -> str:
    val = os.getenv(name)
    if not val:
        sys.exit(f"Missing required env var: {name}. Run `azd env get-values > .env`.")
    return val


def log(msg: str) -> None:
    print(f"[trainer] {msg}", flush=True)


# ---------- Storage upload ----------

def upload_locale_data(cc, locale: str, locale_dir: Path, run_id: str, account_url: str, container: str) -> dict[str, str]:
    """Uploads training artifacts for one locale and returns their HTTPS URLs."""
    prefix = f"runs/{run_id}/{locale}"
    urls: dict[str, str] = {}

    lang_file = locale_dir / "language.txt"
    if not lang_file.exists():
        sys.exit(f"[{locale}] Missing required file: {lang_file}")
    blob_path = f"{prefix}/language.txt"
    log(f"[{locale}] Uploading language.txt -> {blob_path}")
    cc.upload_blob(name=blob_path, data=lang_file.read_bytes(), overwrite=True)
    urls["language"] = f"{account_url}/{container}/{blob_path}"

    pron_file = locale_dir / "pronunciation.txt"
    if pron_file.exists():
        blob_path = f"{prefix}/pronunciation.txt"
        log(f"[{locale}] Uploading pronunciation.txt -> {blob_path}")
        cc.upload_blob(name=blob_path, data=pron_file.read_bytes(), overwrite=True)
        urls["pronunciation"] = f"{account_url}/{container}/{blob_path}"

    audio_dir = locale_dir / "audio"
    if audio_dir.exists() and any(audio_dir.glob("*.wav")):
        log(f"[{locale}] Packaging acoustic dataset (audio + transcripts)...")
        buf = io.BytesIO()
        transcript_lines: list[str] = []
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for wav in sorted(audio_dir.glob("*.wav")):
                txt = wav.with_suffix(".txt")
                if not txt.exists():
                    log(f"[{locale}]   WARN: skipping {wav.name} (no matching transcript)")
                    continue
                zf.write(wav, arcname=wav.name)
                transcript_lines.append(f"{wav.name}\t{txt.read_text(encoding='utf-8').strip()}")
            zf.writestr("transcripts.txt", "\ufeff" + "\n".join(transcript_lines) + "\n")
        buf.seek(0)
        blob_path = f"{prefix}/acoustic.zip"
        log(f"[{locale}] Uploading acoustic.zip ({len(transcript_lines)} clips) -> {blob_path}")
        cc.upload_blob(name=blob_path, data=buf.getvalue(), overwrite=True)
        urls["acoustic"] = f"{account_url}/{container}/{blob_path}"

    return urls


# ---------- Speech REST helpers ----------

class SpeechClient:
    def __init__(self, region: str, credential: DefaultAzureCredential, custom_endpoint: str | None = None) -> None:
        # AAD token auth requires the custom subdomain endpoint, not the regional one.
        if custom_endpoint:
            host = custom_endpoint.rstrip("/")
            self.base = f"{host}/speechtotext/v3.2"
        else:
            self.base = f"https://{region}.api.cognitive.microsoft.com/speechtotext/v3.2"
        self.credential = credential
        self._client = httpx.Client(timeout=60)

    def _headers(self) -> dict[str, str]:
        token = self.credential.get_token("https://cognitiveservices.azure.com/.default").token
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def post(self, path: str, body: dict) -> dict:
        r = self._client.post(f"{self.base}{path}", headers=self._headers(), json=body)
        if r.status_code >= 300:
            sys.exit(f"POST {path} failed [{r.status_code}]: {r.text}")
        return r.json()

    def get(self, url: str) -> dict:
        r = self._client.get(url, headers=self._headers())
        if r.status_code >= 300:
            sys.exit(f"GET {url} failed [{r.status_code}]: {r.text}")
        return r.json()

    def list(self, path: str) -> list[dict]:
        return self.get(f"{self.base}{path}").get("values", [])

    def wait(self, self_url: str, label: str) -> dict:
        deadline = time.time() + POLL_TIMEOUT_S
        while time.time() < deadline:
            obj = self.get(self_url)
            status = obj.get("status")
            log(f"  {label} status: {status}")
            if status == "Succeeded":
                return obj
            if status == "Failed":
                sys.exit(f"{label} failed: {obj.get('properties', {}).get('error')}")
            time.sleep(POLL_INTERVAL_S)
        sys.exit(f"{label} timed out after {POLL_TIMEOUT_S}s")


# ---------- Workflow ----------

def get_or_create_project(sc: SpeechClient, project_name: str, locale: str) -> str:
    for p in sc.list("/projects"):
        if p.get("displayName") == project_name and p.get("locale") == locale:
            log(f"[{locale}] Reusing project: {p['self']}")
            return p["self"]
    log(f"[{locale}] Creating project: {project_name}")
    p = sc.post("/projects", {
        "displayName": project_name,
        "locale": locale,
        "description": f"Station name recognition ({locale})",
    })
    return p["self"]


def pick_base_model(sc: SpeechClient, locale: str, required_kinds: set[str]) -> str:
    """Picks the newest base model that supports all required adaptation kinds
    AND is not past its adaptation deprecation date."""
    models: list[dict] = []
    next_url = f"{sc.base}/models/base?filter=locale eq '{locale}'&top=100"
    while next_url:
        r = sc.get(next_url)
        models.extend(r.get("values", []))
        next_url = r.get("@nextLink")
    if not models:
        sys.exit(f"[{locale}] No base models found")

    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def supported_kinds(m: dict) -> set[str]:
        feats = (m.get("properties") or {}).get("features") or {}
        return set(feats.get("supportsAdaptationsWith") or [])

    def adaptation_alive(m: dict) -> bool:
        dep = (m.get("properties") or {}).get("deprecationDates") or {}
        adapt_until = dep.get("adaptationDateTime")
        return (not adapt_until) or (adapt_until > now_iso)

    candidates = [
        m for m in models
        if required_kinds.issubset(supported_kinds(m)) and adaptation_alive(m)
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda m: m.get("createdDateTime", ""), reverse=True)
    chosen = candidates[0]
    log(f"[{locale}] Base model: {chosen['displayName']} (supports {sorted(supported_kinds(chosen))})")
    return chosen["self"]


def create_dataset(sc: SpeechClient, project_self: str, kind: str, content_url: str, name: str, locale: str) -> str:
    log(f"[{locale}] Creating {kind} dataset: {name}")
    ds = sc.post("/datasets", {
        "kind": kind,
        "displayName": name,
        "locale": locale,
        "contentUrl": content_url,
        "project": {"self": project_self},
    })
    sc.wait(ds["self"], f"[{locale}] dataset[{kind}]")
    return ds["self"]


def train_model(sc: SpeechClient, project_self: str, base_self: str, dataset_selfs: list[str], locale: str, project_name: str) -> str:
    name = f"custom-{project_name}-{locale}-{time.strftime('%Y%m%d-%H%M%S')}"
    log(f"[{locale}] Training custom model: {name}")
    m = sc.post("/models", {
        "displayName": name,
        "locale": locale,
        "baseModel": {"self": base_self},
        "datasets": [{"self": s} for s in dataset_selfs],
        "project": {"self": project_self},
    })
    sc.wait(m["self"], f"[{locale}] model")
    return m["self"]


def deploy_endpoint(sc: SpeechClient, project_self: str, model_self: str, locale: str, project_name: str) -> dict:
    name = f"endpoint-{project_name}-{locale}-{time.strftime('%Y%m%d-%H%M%S')}"
    log(f"[{locale}] Deploying endpoint: {name}")
    e = sc.post("/endpoints", {
        "displayName": name,
        "locale": locale,
        "model": {"self": model_self},
        "project": {"self": project_self},
        "properties": {"contentLoggingEnabled": False},
    })
    return sc.wait(e["self"], f"[{locale}] endpoint")


def discover_locales(requested: list[str]) -> list[Path]:
    candidates = sorted(p for p in DATA_DIR.iterdir() if p.is_dir() and (p / "language.txt").exists())
    if not candidates:
        sys.exit(f"No locale subfolders with language.txt found under {DATA_DIR}")
    if requested:
        wanted = set(requested)
        chosen = [p for p in candidates if p.name in wanted]
        missing = wanted - {p.name for p in chosen}
        if missing:
            sys.exit(f"Requested locales not found in data/: {sorted(missing)}")
        return chosen
    return candidates


def train_one_locale(sc: SpeechClient, cc, account_url: str, container: str, run_id: str, locale_dir: Path, skip_acoustic: bool = False) -> dict:
    locale = locale_dir.name
    log(f"=== {locale} ===")
    urls = upload_locale_data(cc, locale, locale_dir, run_id, account_url, container)
    if skip_acoustic and "acoustic" in urls:
        log(f"[{locale}] --skip-acoustic set; ignoring acoustic dataset")
        urls.pop("acoustic")
    project_self = get_or_create_project(sc, PROJECT_PREFIX, locale)

    # Build dataset specs first; we may drop some if no compatible base model exists.
    dataset_specs: list[tuple[str, str, str]] = []  # (kind, url, name)
    dataset_specs.append(("Language", urls["language"], "language-data"))
    if "pronunciation" in urls:
        dataset_specs.append(("Pronunciation", urls["pronunciation"], "pronunciation-data"))
    if "acoustic" in urls:
        dataset_specs.append(("Acoustic", urls["acoustic"], "acoustic-data"))

    # Find a base model; degrade by dropping the most demanding kinds (Acoustic, then Pronunciation).
    drop_order = ["Acoustic", "Pronunciation"]
    kinds_to_use = {k for k, _, _ in dataset_specs}
    base_self = pick_base_model(sc, locale, kinds_to_use)
    while base_self is None and drop_order:
        dropped = drop_order.pop(0)
        if dropped in kinds_to_use:
            log(f"[{locale}] No base model supports {sorted(kinds_to_use)}; dropping {dropped} and retrying")
            kinds_to_use.discard(dropped)
            base_self = pick_base_model(sc, locale, kinds_to_use)
    if base_self is None:
        sys.exit(f"[{locale}] No suitable non-deprecated base model found even with minimal adaptation kinds")

    dataset_specs = [s for s in dataset_specs if s[0] in kinds_to_use]
    dataset_selfs: list[str] = [
        create_dataset(sc, project_self, kind, url, name, locale)
        for kind, url, name in dataset_specs
    ]
    model_self = train_model(sc, project_self, base_self, dataset_selfs, locale, PROJECT_PREFIX)
    endpoint = deploy_endpoint(sc, project_self, model_self, locale, PROJECT_PREFIX)
    return {
        "locale": locale,
        "model": model_self,
        "endpoint_self": endpoint["self"],
        "endpoint_id": endpoint["self"].rsplit("/", 1)[-1],
    }


def main():
    load_dotenv(ROOT / ".env")
    args = sys.argv[1:]
    skip_acoustic = False
    if "--skip-acoustic" in args:
        skip_acoustic = True
        args = [a for a in args if a != "--skip-acoustic"]
    region = env("AZURE_SPEECH_REGION")
    speech_endpoint = os.getenv("AZURE_SPEECH_ENDPOINT")  # custom subdomain, required for AAD
    account = env("AZURE_STORAGE_ACCOUNT")
    container = env("AZURE_STORAGE_CONTAINER")
    account_url = f"https://{account}.blob.core.windows.net"

    locale_dirs = discover_locales(args)
    log(f"Locales to train: {[p.name for p in locale_dirs]} (skip_acoustic={skip_acoustic})")

    credential = DefaultAzureCredential()
    bsc = BlobServiceClient(account_url=account_url, credential=credential)
    cc = bsc.get_container_client(container)
    sc = SpeechClient(region, credential, custom_endpoint=speech_endpoint)

    run_id = time.strftime("%Y%m%d-%H%M%S")
    manifest_path = ROOT / "config" / "custom_speech_endpoints.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest: dict = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text())
        except Exception:
            manifest = {}

    results: list[dict] = []
    for locale_dir in locale_dirs:
        r = train_one_locale(sc, cc, account_url, container, run_id, locale_dir, skip_acoustic=skip_acoustic)
        results.append(r)
        manifest[r["locale"]] = {"endpoint_id": r["endpoint_id"], "model": r["model"]}
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        log(f"Updated manifest -> {manifest_path}")

    log("DONE.")
    log(f"Wrote endpoint manifest -> {manifest_path}")
    for r in results:
        log(f"  {r['locale']}: endpoint_id={r['endpoint_id']}")
    log("Use with the Speech SDK:")
    log("  speech_config.endpoint_id = '<id>'")
    log("  speech_config.speech_recognition_language = '<locale>'")


if __name__ == "__main__":
    main()
