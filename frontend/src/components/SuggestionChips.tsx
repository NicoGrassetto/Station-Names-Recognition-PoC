import "./SuggestionChips.css";

const rows = [
  [
    { emoji: "🔬", text: "How does quantum computing actually work?" },
    { emoji: "💡", text: "What are the latest breakthroughs in fusion energy?" },
    { emoji: "🧬", text: "How do viruses mutate so quickly?" },
    { emoji: "⚡", text: "What is superconductivity?" },
  ],
  [
    { emoji: "🤖", text: "Will AI ever become truly conscious?" },
    { emoji: "🌊", text: "How do we predict tsunamis?" },
    { emoji: "🎧", text: "What is dark matter, really?" },
    { emoji: "🔭", text: "Are there habitable exoplanets?" },
  ],
  [
    { emoji: "🧪", text: "How does CRISPR gene editing work?" },
    { emoji: "🏔️", text: "What if Yellowstone erupts?" },
    { emoji: "🧊", text: "Why is polar ice melting?" },
    { emoji: "🌍", text: "How did life on Earth begin?" },
  ],
];

interface SuggestionChipsProps {
  onSelect: (text: string) => void;
}

export default function SuggestionChips({ onSelect }: SuggestionChipsProps) {
  return (
    <div className="suggestion-chips">
      {rows.map((row, i) => (
        <div className="chip-row" key={i}>
          {row.map((chip) => (
            <button
              key={chip.text}
              className="chip"
              onClick={() => onSelect(chip.text)}
            >
              <span className="chip-emoji">{chip.emoji}</span>
              {chip.text}
            </button>
          ))}
        </div>
      ))}
    </div>
  );
}
