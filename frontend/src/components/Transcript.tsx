import { useEffect, useRef } from "react";
import type { TranscriptEntry } from "../hooks/useRealtime";
import "./Transcript.css";

interface TranscriptProps {
  entries: TranscriptEntry[];
  compact?: boolean;
}

export default function Transcript({
  entries,
  compact = false,
}: TranscriptProps) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [entries]);

  if (entries.length === 0) return null;

  const classes = [
    "transcript",
    "transcript--default",
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
          <span className="transcript-role">{entry.role}</span>
          <span>{entry.text}</span>
        </div>
      ))}
      <div ref={endRef} />
    </div>
  );
}
