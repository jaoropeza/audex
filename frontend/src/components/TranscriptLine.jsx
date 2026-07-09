import styles from "./TranscriptLine.module.css";

// Parse "[HH:MM:SS][LABEL][SPEAKER] text" into structured parts
export function parseLine(raw) {
  const bracketRe = /\[([^\]]+)\]/g;
  const parts = { timestamp: null, label: null, speaker: null, text: raw };
  const matches = [...raw.matchAll(bracketRe)];
  const timeRe = /^\d{2}:\d{2}:\d{2}$/;
  let afterBrackets = raw;

  if (matches.length > 0) {
    let idx = 0;
    for (const m of matches) {
      if (idx === 0 && timeRe.test(m[1])) { parts.timestamp = m[1]; idx++; }
      else if (idx <= 1 && (m[1] === "MIC" || m[1] === "SPK")) { parts.label = m[1]; idx++; }
      else if (idx <= 2 && !/^\d{2}:\d{2}:\d{2}$/.test(m[1])) { parts.speaker = m[1]; idx++; }
    }
    // Text is everything after the last bracket group at the start
    const lastBracketEnd = raw.lastIndexOf("]");
    afterBrackets = raw.slice(lastBracketEnd + 1).trim();
    parts.text = afterBrackets;
  }

  return parts;
}

export default function TranscriptLine({ raw, translation, searchTerm }) {
  const { timestamp, label, speaker, text } = parseLine(raw);

  function highlight(str) {
    if (!searchTerm) return str;
    const idx = str.toLowerCase().indexOf(searchTerm.toLowerCase());
    if (idx === -1) return str;
    return (
      <>
        {str.slice(0, idx)}
        <mark className={styles.highlight}>{str.slice(idx, idx + searchTerm.length)}</mark>
        {str.slice(idx + searchTerm.length)}
      </>
    );
  }

  return (
    <div className={styles.line}>
      <span className={styles.meta}>
        {timestamp && <span className={styles.ts}>{timestamp}</span>}
        {label === "MIC" && <span className={`${styles.badge} ${styles.mic}`}>MIC</span>}
        {label === "SPK" && <span className={`${styles.badge} ${styles.spk}`}>SPK</span>}
        {speaker && <span className={`${styles.badge} ${styles.spkr}`}>{speaker}</span>}
      </span>
      <span className={styles.text}>{highlight(text)}</span>
      {translation && translation !== raw && (
        <div className={styles.translation}>{translation}</div>
      )}
    </div>
  );
}
