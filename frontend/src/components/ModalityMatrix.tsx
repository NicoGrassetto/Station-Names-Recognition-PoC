import { Mic, Eye, Type, Volume2, FileText } from "lucide-react";
import "./ModalityMatrix.css";

interface ModalityCell {
  mode: string;
  label: string;
  enabled: boolean;
}

const outputs = [
  { id: "audio_text", label: "Audio + Text", icon: Volume2 },
  { id: "text_only", label: "Text Only", icon: FileText },
];

const inputs = [
  { id: "audio", label: "Audio", icon: Mic },
  { id: "audio_image", label: "Audio + Image", icon: Eye },
  { id: "text", label: "Text", icon: Type },
];

const matrix: Record<string, Record<string, ModalityCell>> = {
  audio: {
    audio_text: { mode: "voice_assistant", label: "Voice Assistant", enabled: true },
    text_only: { mode: "transcription", label: "Transcription", enabled: true },
  },
  audio_image: {
    audio_text: { mode: "vision", label: "Vision", enabled: true },
    text_only: { mode: "vision_text", label: "Vision (Text)", enabled: true },
  },
  text: {
    audio_text: { mode: "text_to_speech", label: "Text → Speech", enabled: true },
    text_only: { mode: "text_chat", label: "Text Chat", enabled: true },
  },
};

interface ModalityMatrixProps {
  activeMode: string;
  onModeChange: (mode: string) => void;
}

export default function ModalityMatrix({
  activeMode,
  onModeChange,
}: ModalityMatrixProps) {
  return (
    <div className="modality-matrix">
      <div className="matrix-grid">
        {/* Corner */}
        <div className="matrix-corner">
          <span className="modality-matrix-label">Input ↓ Output →</span>
        </div>

        {/* Column headers */}
        {outputs.map((out) => {
          const Icon = out.icon;
          return (
            <div key={out.id} className="matrix-col-header">
              <Icon size={14} />
              <span>{out.label}</span>
            </div>
          );
        })}

        {/* Rows */}
        {inputs.map((inp) => {
          const RowIcon = inp.icon;
          return (
            <div key={inp.id} className="matrix-row-group" style={{ display: "contents" }}>
              <div className="matrix-row-header">
                <RowIcon size={14} />
                <span>{inp.label}</span>
              </div>
              {outputs.map((out) => {
                const cell = matrix[inp.id][out.id];
                const isActive = activeMode === cell.mode;
                const classes = [
                  "matrix-cell",
                  isActive && "matrix-cell--active",
                  !cell.enabled && "matrix-cell--disabled",
                ]
                  .filter(Boolean)
                  .join(" ");
                return (
                  <button
                    key={`${inp.id}-${out.id}`}
                    className={classes}
                    onClick={() => cell.enabled && onModeChange(cell.mode)}
                    title={cell.enabled ? cell.label : "Not yet configured"}
                  >
                    {cell.label}
                  </button>
                );
              })}
            </div>
          );
        })}
      </div>
    </div>
  );
}
