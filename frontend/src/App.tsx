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

export default function App() {
  const [inputValue, setInputValue] = useState("");
  const [recording, setRecording] = useState(false);
  const [aiSpeaking, setAiSpeaking] = useState(false);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [selectedModel, setSelectedModel] = useState("");

  const playerRef = useRef<AudioPlayer | null>(null);
  const captureRef = useRef<AudioCapture | null>(null);

  function getPlayer() {
    if (!playerRef.current) {
      playerRef.current = createAudioPlayer(24000);
    }
    return playerRef.current;
  }

  const handleAudioChunk = useCallback((base64: string) => {
    setAiSpeaking(true);
    getPlayer().enqueue(base64);
  }, []);

  const handleAudioEnd = useCallback(() => {
    setAiSpeaking(false);
  }, []);

  const handleAudioInterrupted = useCallback(() => {
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
    fetch("/api/models")
      .then((r) => r.json())
      .then((data: { models: ModelInfo[]; default: string }) => {
        setModels(data.models);
        setSelectedModel(data.default);
      })
      .catch(() => {});
  }, []);

  const handleConnect = useCallback(() => {
    connect(ACTIVE_MODE, selectedModel || undefined);
  }, [connect, selectedModel]);

  const handleDisconnect = useCallback(() => {
    if (captureRef.current?.isRecording()) {
      captureRef.current.stop();
      setRecording(false);
    }
    setAiSpeaking(false);
    getPlayer().interrupt();
    disconnect();
  }, [disconnect]);

  const handleToggleMic = useCallback(() => {
    if (captureRef.current?.isRecording()) {
      captureRef.current.stop();
      captureRef.current = null;
      setRecording(false);
    } else {
      const capture = createAudioCapture((samples) => {
        sendAudioRef.current(samples);
      });
      captureRef.current = capture;
      capture.start().then(
        () => setRecording(true),
        (err) => {
          console.error("Mic capture failed:", err);
          captureRef.current = null;
        }
      );
    }
  }, []);

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
          onConnect={handleConnect}
          onDisconnect={handleDisconnect}
          onToggleMic={handleToggleMic}
          onSendText={handleSendText}
        />
      </main>
    </div>
  );
}
