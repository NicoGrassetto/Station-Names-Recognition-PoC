import { useCallback, useEffect, useRef, useState } from "react";
import Navbar from "./components/Navbar";
import HeroText from "./components/HeroText";
import ChatInput from "./components/ChatInput";
import Transcript from "./components/Transcript";
import StatusBar from "./components/StatusBar";
import AudioOrb from "./components/AudioOrb";
import LogConsole from "./components/LogConsole";
import { useRealtime } from "./hooks/useRealtime";
import { createAudioCapture, type AudioCapture } from "./lib/audioCapture";
import { createAudioPlayer, type AudioPlayer } from "./lib/audioPlayer";
import "./App.css";

const ACTIVE_MODE = "booking";

interface ModelInfo {
  id: string;
  model: string;
  status: string;
}

interface ProviderRouteInfo {
  id: string;
  description: string;
  status: string;
  disabled?: boolean;
  reason?: string;
}

interface ProviderInfo {
  id: string;
  name: string;
  status: string;
  disabled?: boolean;
  reason?: string;
  routes?: ProviderRouteInfo[];
}

export default function App() {
  const [inputValue, setInputValue] = useState("");
  const [recording, setRecording] = useState(false);
  const [aiSpeaking, setAiSpeaking] = useState(false);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [selectedModel, setSelectedModel] = useState("");
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [selectedProvider, setSelectedProvider] = useState("");
  const [selectedProviderRoute, setSelectedProviderRoute] = useState("");
  const [backendStatusMessage, setBackendStatusMessage] = useState("");

  const playerRef = useRef<AudioPlayer | null>(null);
  const captureRef = useRef<AudioCapture | null>(null);
  const aiSpeakingRef = useRef(false);

  function getPlayer() {
    if (!playerRef.current) {
      playerRef.current = createAudioPlayer(24000);
    }
    return playerRef.current;
  }

  const handleAudioChunk = useCallback((base64: string) => {
    aiSpeakingRef.current = true;
    setAiSpeaking(true);
    getPlayer().enqueue(base64);
  }, []);

  const handleAudioEnd = useCallback(() => {
    aiSpeakingRef.current = false;
    setAiSpeaking(false);
  }, []);

  const handleAudioInterrupted = useCallback(() => {
    aiSpeakingRef.current = false;
    setAiSpeaking(false);
    getPlayer().interrupt();
  }, []);

  const {
    connected,
    connecting,
    transcript,
    toolActivity,
    logs,
    clearLogs,
    connect,
    disconnect,
    sendAudio,
    sendText,
  } = useRealtime(handleAudioChunk, handleAudioEnd, handleAudioInterrupted);

  const sendAudioRef = useRef(sendAudio);
  sendAudioRef.current = sendAudio;

  useEffect(() => {
    let cancelled = false;

    async function loadBackendMetadata() {
      try {
        const providersResponse = await fetch("/api/providers");
        if (!providersResponse.ok) {
          throw new Error(`Provider metadata failed (${providersResponse.status})`);
        }
        const providerData = (await providersResponse.json()) as {
          providers: ProviderInfo[];
          default: string;
        };
        if (cancelled) return;

        setProviders(providerData.providers);
        const defaultProvider =
          providerData.providers.find(
            (provider) => provider.id === providerData.default && !provider.disabled
          ) ??
          providerData.providers.find((provider) => !provider.disabled) ??
          providerData.providers[0];
        setSelectedProvider(defaultProvider?.id ?? "");
        const defaultRoute =
          defaultProvider?.routes?.find((route) => !route.disabled) ??
          defaultProvider?.routes?.[0];
        setSelectedProviderRoute(defaultRoute?.id ?? "");
        setBackendStatusMessage("");

        const modelsResponse = await fetch("/api/models");
        if (!modelsResponse.ok) {
          throw new Error(`Model metadata failed (${modelsResponse.status})`);
        }
        const data = (await modelsResponse.json()) as {
          models: ModelInfo[];
          default: string;
        };
        if (cancelled) return;
        setModels(data.models);
        setSelectedModel(data.default);
      } catch {
        if (cancelled) return;
        setProviders([]);
        setModels([]);
        setSelectedProvider("");
        setSelectedProviderRoute("");
        setSelectedModel("");
        setBackendStatusMessage(
          "Backend unavailable. Start it with: python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload"
        );
      }
    }

    loadBackendMetadata();
    return () => {
      cancelled = true;
    };
  }, []);

  const selectedProviderInfo =
    providers.find((provider) => provider.id === selectedProvider) ?? null;
  const providerRoutes = selectedProviderInfo?.routes ?? [];
  const selectedRouteInfo =
    providerRoutes.find((route) => route.id === selectedProviderRoute) ?? null;
  const providerStatusMessage =
    backendStatusMessage ||
    selectedRouteInfo?.reason ||
    selectedProviderInfo?.reason ||
    "";
  const canConnect =
    !backendStatusMessage &&
    !!selectedProviderInfo &&
    !selectedProviderInfo.disabled &&
    (providerRoutes.length === 0 || (!!selectedRouteInfo && !selectedRouteInfo.disabled));

  const handleConnect = useCallback(() => {
    if (!canConnect) return;
    connect(
      ACTIVE_MODE,
      selectedModel || undefined,
      selectedProvider || undefined,
      selectedProviderRoute || undefined
    );
  }, [canConnect, connect, selectedModel, selectedProvider, selectedProviderRoute]);

  const handleProviderChange = useCallback(
    (providerId: string) => {
      setSelectedProvider(providerId);
      const provider = providers.find((p) => p.id === providerId);
      const route = provider?.routes?.find((r) => !r.disabled) ?? provider?.routes?.[0];
      setSelectedProviderRoute(route?.id ?? "");
    },
    [providers]
  );

  const handleDisconnect = useCallback(() => {
    if (captureRef.current?.isRecording()) {
      captureRef.current.stop();
      setRecording(false);
    }
    aiSpeakingRef.current = false;
    setAiSpeaking(false);
    getPlayer().interrupt();
    disconnect();
  }, [disconnect]);

  const startMicCapture = useCallback(() => {
    if (captureRef.current?.isRecording()) return;
    const capture = createAudioCapture((samples) => {
      if (!aiSpeakingRef.current) {
        sendAudioRef.current(samples);
    }
    });
    captureRef.current = capture;
    capture.start().then(
      () => setRecording(true),
      (err) => {
        console.error("Mic capture failed:", err);
        captureRef.current = null;
        setRecording(false);
      }
    );
  }, []);

  const stopMicCapture = useCallback(() => {
    captureRef.current?.stop();
    captureRef.current = null;
    setRecording(false);
  }, []);

  const handleToggleMic = useCallback(() => {
    if (captureRef.current?.isRecording()) {
      stopMicCapture();
    } else {
      startMicCapture();
    }
  }, [startMicCapture, stopMicCapture]);

  useEffect(() => {
    if (connected && !captureRef.current?.isRecording()) {
      startMicCapture();
    }
  }, [connected, startMicCapture]);

  const handleSendText = useCallback(
    (text: string) => {
      sendText(text);
    },
    [sendText]
  );

  const showLanding = !connected && !connecting;
  const orbState: "idle" | "listening" | "speaking" =
    aiSpeaking ? "speaking" : recording ? "listening" : "idle";

  return (
    <div className="app">
      <Navbar />
      <main
        className={`app-main${!showLanding ? ` app-main--session app-main--${ACTIVE_MODE}` : ""}`}
      >
        {showLanding && <HeroText />}
        {!showLanding && (
          <div className="session-content">
            <StatusBar
              connected={connected}
              connecting={connecting}
              recording={recording}
              toolActivity={toolActivity}
            />

            <AudioOrb state={orbState} />

            <Transcript entries={transcript} compact />

            <LogConsole logs={logs} onClear={clearLogs} />
          </div>
        )}
        <ChatInput
          value={inputValue}
          onChange={setInputValue}
          connected={connected}
          recording={recording}
          models={models}
          selectedModel={selectedModel}
          onModelChange={setSelectedModel}
          providers={providers}
          selectedProvider={selectedProvider}
          onProviderChange={handleProviderChange}
          providerRoutes={providerRoutes}
          selectedProviderRoute={selectedProviderRoute}
          onProviderRouteChange={setSelectedProviderRoute}
          canConnect={canConnect}
          statusMessage={providerStatusMessage}
          onConnect={handleConnect}
          onDisconnect={handleDisconnect}
          onToggleMic={handleToggleMic}
          onSendText={handleSendText}
        />
      </main>
    </div>
  );
}
