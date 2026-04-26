import { useEffect, useRef } from "react";
import type { LogEntry } from "../hooks/useRealtime";
import "./LogConsole.css";

interface LogConsoleProps {
  logs: LogEntry[];
  onClear?: () => void;
}

const KNOWN_SOURCES = new Set(["state", "tool", "speech", "session"]);

function formatTime(ts: number): string {
  const d = new Date(ts);
  return d.toLocaleTimeString(undefined, { hour12: false }) +
    "." + String(d.getMilliseconds()).padStart(3, "0");
}

function formatMeta(meta: Record<string, unknown>): string {
  const parts: string[] = [];
  for (const [k, v] of Object.entries(meta)) {
    if (v == null) continue;
    let val: string;
    if (typeof v === "object") {
      try {
        val = JSON.stringify(v);
      } catch {
        val = String(v);
      }
    } else {
      val = String(v);
    }
    if (val.length > 120) val = val.slice(0, 117) + "…";
    parts.push(`${k}=${val}`);
  }
  return parts.join(" · ");
}

export default function LogConsole({ logs, onClear }: LogConsoleProps) {
  const bodyRef = useRef<HTMLDivElement | null>(null);

  // Auto-scroll to bottom on new entries
  useEffect(() => {
    const el = bodyRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [logs.length]);

  return (
    <div className="log-console">
      <div className="log-console__header">
        <span>Console</span>
        <div className="log-console__actions">
          <span style={{ color: "#4a5263", fontSize: 11 }}>{logs.length} entries</span>
          {onClear && (
            <button className="log-console__btn" onClick={onClear} type="button">
              Clear
            </button>
          )}
        </div>
      </div>
      <div className="log-console__body" ref={bodyRef}>
        {logs.length === 0 && (
          <div className="log-console__empty">No log entries yet.</div>
        )}
        {logs.map((entry) => {
          const sourceClass = KNOWN_SOURCES.has(entry.source)
            ? `log-console__source--${entry.source}`
            : "log-console__source--default";
          const rowClass =
            entry.level === "warn"
              ? "log-console__row log-console__row--warn"
              : entry.level === "error"
              ? "log-console__row log-console__row--error"
              : "log-console__row";
          return (
            <div key={entry.id} className={rowClass}>
              <span className="log-console__time">{formatTime(entry.timestamp)}</span>
              <span className={`log-console__source ${sourceClass}`}>
                {entry.source}
              </span>
              <span className="log-console__msg">
                {entry.message}
                {entry.meta && Object.keys(entry.meta).length > 0 && (
                  <span className="log-console__meta">
                    {formatMeta(entry.meta)}
                  </span>
                )}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
