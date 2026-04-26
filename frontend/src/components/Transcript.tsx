import { useEffect, useRef } from "react";
import type { TranscriptEntry } from "../hooks/useRealtime";
import "./Transcript.css";

interface TranscriptProps {
  entries: TranscriptEntry[];
  variant?: "default" | "document";
  compact?: boolean;
}

export default function Transcript({
  entries,
  variant = "default",
  compact = false,
}: TranscriptProps) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [entries]);

  if (entries.length === 0) return null;

  const classes = [
    "transcript",
    `transcript--${variant}`,
    compact && "transcript--compact",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={classes}>
      {entries.map((entry) => (
        <div
          key={entry.id}
          className={`transcript-entry transcript-entry--${entry.role}`}
        >
          {variant !== "document" && (
            <span className="transcript-role">{entry.role}</span>
          )}
          <span>{entry.text}</span>
        </div>
      ))}
      <div ref={endRef} />
    </div>
  );
}
