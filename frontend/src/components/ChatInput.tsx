import {
  ArrowRight,
  Mic,
  MicOff,
  Plug,
  Unplug,
} from "lucide-react";
import "./ChatInput.css";

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  connected: boolean;
  recording: boolean;
  models: Array<{ id: string; model: string; status: string }>;
  selectedModel: string;
  onModelChange: (model: string) => void;
  onConnect: () => void;
  onDisconnect: () => void;
  onToggleMic: () => void;
  onSendText: (text: string) => void;
}

export default function ChatInput({
  value,
  onChange,
  connected,
  recording,
  models,
  selectedModel,
  onModelChange,
  onConnect,
  onDisconnect,
  onToggleMic,
  onSendText,
}: ChatInputProps) {
  function handleSend() {
    if (!value.trim()) return;
    onSendText(value.trim());
    onChange("");
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div className="chat-input-wrapper">
      <div className="chat-input">
        <textarea
          rows={1}
          placeholder="How can I help you today?"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          onInput={(e) => {
            const target = e.target as HTMLTextAreaElement;
            target.style.height = "auto";
            target.style.height = target.scrollHeight + "px";
          }}
        />
        <div className="chat-input-toolbar">
          <select
            className="chat-input-model"
            value={selectedModel}
            onChange={(e) => onModelChange(e.target.value)}
            disabled={connected}
          >
            {models.length === 0 && (
              <option value="">Loading…</option>
            )}
            {models.map((m) => (
              <option key={m.id} value={m.id}>
                {m.id}
              </option>
            ))}
          </select>

          <div className="chat-input-actions">
            {connected ? (
              <button
                className="chat-input-btn chat-input-btn--connected"
                onClick={onDisconnect}
                aria-label="Disconnect"
                title="Disconnect"
              >
                <Unplug size={18} />
              </button>
            ) : (
              <button
                className="chat-input-btn"
                onClick={onConnect}
                aria-label="Connect"
                title="Connect"
              >
                <Plug size={18} />
              </button>
            )}

            {connected && (
              <button
                className={`chat-input-btn${recording ? " chat-input-btn--recording" : ""}`}
                onClick={onToggleMic}
                aria-label={recording ? "Stop recording" : "Start recording"}
                title={recording ? "Stop recording" : "Start recording"}
              >
                {recording ? <MicOff size={18} /> : <Mic size={18} />}
              </button>
            )}

            <button
              className="chat-input-send"
              onClick={handleSend}
              aria-label="Send"
              disabled={!value.trim()}
            >
              <ArrowRight size={18} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
