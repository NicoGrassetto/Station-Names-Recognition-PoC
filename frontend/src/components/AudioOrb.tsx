import "./AudioOrb.css";

interface AudioOrbProps {
  state: "idle" | "listening" | "speaking";
}

export default function AudioOrb({ state }: AudioOrbProps) {
  return (
    <div className={`audio-orb audio-orb--${state}`}>
      <div className="audio-orb-ring audio-orb-ring--3" />
      <div className="audio-orb-ring audio-orb-ring--2" />
      <div className="audio-orb-ring audio-orb-ring--1" />
      <div className="audio-orb-core" />
    </div>
  );
}
