import type { ToolActivity } from "../hooks/useRealtime";
import "./StatusBar.css";

const modeLabels: Record<string, string> = {
  voice_assistant: "Voice Assistant",
  transcription: "Transcription",
  vision: "Vision",
  vision_text: "Vision (Text)",
  text_to_speech: "Text \u2192 Speech",
  text_chat: "Text Chat",
};

interface StatusBarProps {
  connected: boolean;
  connecting: boolean;
  recording: boolean;
  toolActivity: ToolActivity | null;
  activeMode: string;
}

export default function StatusBar({
  connected,
  connecting,
  recording,
  toolActivity,
  activeMode,
}: StatusBarProps) {
  const dotClass = connecting
    ? "status-dot--connecting"
    : connected
      ? "status-dot--connected"
      : "status-dot--disconnected";

  const label = connecting
    ? "Connecting…"
    : connected
      ? recording
        ? "Listening…"
        : "Connected"
      : "Disconnected";

  return (
    <div className="status-bar">
      <span className={`status-dot ${dotClass}`} />
      <span>{label}</span>
      <span className="status-mode">{modeLabels[activeMode] || activeMode}</span>
      {toolActivity && (
        <span className="status-tool">
          {toolActivity.status === "running" && (
            <span className="status-tool-spinner" />
          )}
          {toolActivity.tool}
          {toolActivity.status === "done" && " ✓"}
        </span>
      )}
    </div>
  );
}
