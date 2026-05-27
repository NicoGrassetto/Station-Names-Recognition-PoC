import { ArrowRight, Mic, MicOff, Plug, Unplug } from "lucide-react";
import "./ChatInput.css";

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  connected: boolean;
  recording: boolean;
  models: Array<{ id: string; model: string; status: string }>;
  selectedModel: string;
  onModelChange: (model: string) => void;
  providers: Array<{
    id: string;
    name: string;
    status: string;
    disabled?: boolean;
    reason?: string;
  }>;
  selectedProvider: string;
  onProviderChange: (provider: string) => void;
  providerRoutes: Array<{
    id: string;
    description: string;
    status: string;
    disabled?: boolean;
    reason?: string;
  }>;
  selectedProviderRoute: string;
  onProviderRouteChange: (route: string) => void;
  canConnect: boolean;
  statusMessage?: string;
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
  providers,
  selectedProvider,
  onProviderChange,
  providerRoutes,
  selectedProviderRoute,
  onProviderRouteChange,
  canConnect,
  statusMessage,
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

  function statusSuffix(item: { status: string; disabled?: boolean }) {
    if (!item.disabled && item.status === "available") return "";
    return ` (${item.status.split("_").join(" ")})`;
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
          <div style={{ display: "flex", gap: "8px" }}>
            <select
              className="chat-input-select"
              value={selectedProvider}
              onChange={(e) => onProviderChange(e.target.value)}
              disabled={connected || providers.length === 0}
              title={statusMessage}
            >
              {providers.length === 0 && (
                <option value="">Backend unavailable</option>
              )}
              {providers.map((provider) => (
                <option
                  key={provider.id}
                  value={provider.id}
                  disabled={provider.disabled}
                >
                  {provider.name}
                  {statusSuffix(provider)}
                </option>
              ))}
            </select>

            {providerRoutes.length > 0 && (
              <select
                className="chat-input-select"
                value={selectedProviderRoute}
                onChange={(e) => onProviderRouteChange(e.target.value)}
                disabled={connected || providerRoutes.length === 0}
                title={statusMessage}
              >
                {providerRoutes.map((route) => (
                  <option
                    key={route.id}
                    value={route.id}
                    disabled={route.disabled}
                  >
                    {route.id}
                    {statusSuffix(route)}
                  </option>
                ))}
              </select>
            )}

            <select
              className="chat-input-select"
              value={selectedModel}
              onChange={(e) => onModelChange(e.target.value)}
              disabled={connected || models.length === 0}
            >
              {models.length === 0 && <option value="">Loading…</option>}
              {models.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.id}
                </option>
              ))}
            </select>
          </div>

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
                title={statusMessage || "Connect"}
                disabled={!canConnect}
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
        {statusMessage && (
          <div className="chat-input-status">{statusMessage}</div>
        )}
      </div>
    </div>
  );
}
