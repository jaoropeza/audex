import { useState, useEffect, useRef } from "react";
import TranscriptLine from "./TranscriptLine";
import { useSSE } from "../hooks/useSSE";
import { useTranslation } from "../hooks/useTranslation";
import styles from "./LiveViewer.module.css";

const LANGUAGES = ["English", "Spanish", "French", "Portuguese", "German", "Italian", "Japanese", "Chinese"];

export default function LiveViewer({ filename, isRecording }) {
  const [autoScroll, setAutoScroll] = useState(true);
  const [translateEnabled, setTranslateEnabled] = useState(false);
  const [targetLang, setTargetLang] = useState("English");
  const bottomRef = useRef(null);

  const url = filename ? `/api/stream/${encodeURIComponent(filename)}` : null;
  const { lines, status } = useSSE(url, !!filename);
  const { translations, translating } = useTranslation(lines, targetLang, translateEnabled);

  // Auto-scroll to bottom
  useEffect(() => {
    if (autoScroll && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [lines, autoScroll]);

  if (!filename) {
    return (
      <div className={styles.empty}>
        <p>Start a recording session to see live transcription here.</p>
      </div>
    );
  }

  const statusColor = {
    connecting: "var(--yellow)",
    open: "var(--green)",
    eof: "var(--text-muted)",
    error: "var(--red)",
    idle: "var(--text-muted)",
  }[status] ?? "var(--text-muted)";

  return (
    <div className={styles.viewer}>
      <div className={styles.toolbar}>
        <span className={styles.fname}>{filename}</span>
        <span className={styles.statusDot} style={{ background: statusColor }} />
        <span className={styles.statusLabel}>{status}</span>
        {translating && <span className={styles.translating}>translating…</span>}
        <label className={styles.toggle}>
          <input
            type="checkbox"
            checked={translateEnabled}
            onChange={(e) => setTranslateEnabled(e.target.checked)}
          />
          Translate
        </label>
        {translateEnabled && (
          <select
            className={styles.langSelect}
            value={targetLang}
            onChange={(e) => setTargetLang(e.target.value)}
          >
            {LANGUAGES.map((l) => <option key={l}>{l}</option>)}
          </select>
        )}
        <label className={styles.toggle}>
          <input
            type="checkbox"
            checked={autoScroll}
            onChange={(e) => setAutoScroll(e.target.checked)}
          />
          Auto-scroll
        </label>
      </div>

      <div className={styles.content}>
        {lines.length === 0 && status === "open" && (
          <p className={styles.hint}>Waiting for speech…</p>
        )}
        {lines.map((line, i) => (
          <TranscriptLine
            key={i}
            raw={line}
            translation={translateEnabled ? translations[line] : null}
          />
        ))}
        <div ref={bottomRef} />
      </div>

      {status === "eof" && (
        <div className={styles.eofBanner}>
          Recording ended — {lines.length} lines captured
        </div>
      )}
    </div>
  );
}
