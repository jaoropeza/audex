import { useState, useEffect } from "react";
import { useSSE } from "../hooks/useSSE";
import styles from "./RecordingPanel.module.css";

const MODELS = ["tiny", "base", "small", "medium", "large-v1", "large-v2", "large-v3"];
const LANGUAGES = [
  { code: "en", name: "English" }, { code: "es", name: "Spanish" },
  { code: "fr", name: "French" }, { code: "pt", name: "Portuguese" },
  { code: "de", name: "German" }, { code: "it", name: "Italian" },
  { code: "ja", name: "Japanese" }, { code: "zh", name: "Chinese" },
  { code: "auto", name: "Auto-detect" },
];

export default function RecordingPanel({ recording, onStart, onStop }) {
  const [devices, setDevices] = useState({ mic: [], loopback: [] });
  const [loadingDevices, setLoadingDevices] = useState(false);
  const [config, setConfig] = useState({
    mode: "loopback",
    device: "",
    mic: "",
    model: "small",
    language: "en",
    diarize: false,
    num_speakers: "",
    output_prefix: "transcript",
    save_audio: false,
    summarize: false,
  });
  const [starting, setSending] = useState(false);
  const [error, setError] = useState(null);

  const logUrl = recording.running ? "/api/recording/log" : null;
  const { lines: logLines } = useSSE(logUrl, recording.running);

  useEffect(() => {
    setLoadingDevices(true);
    fetch("/api/recording/devices")
      .then((r) => r.json())
      .then((d) => { setDevices(d); setLoadingDevices(false); })
      .catch(() => setLoadingDevices(false));
  }, []);

  function set(key, val) {
    setConfig((prev) => ({ ...prev, [key]: val }));
  }

  async function handleStart() {
    setSending(true);
    setError(null);
    try {
      const payload = {
        ...config,
        num_speakers: config.num_speakers ? parseInt(config.num_speakers) : null,
        device: config.device || null,
        mic: config.mic || null,
      };
      await onStart(payload);
    } catch (err) {
      setError(err.message);
    } finally {
      setSending(false);
    }
  }

  async function handleStop() {
    try { await onStop(); } catch (err) { setError(err.message); }
  }

  return (
    <div className={styles.panel}>
      <div className={styles.section}>
        <h3 className={styles.sectionTitle}>Audio Source</h3>
        <div className={styles.modeRow}>
          {["loopback", "mic", "merge"].map((m) => (
            <label key={m} className={`${styles.modeBtn} ${config.mode === m ? styles.modeActive : ""}`}>
              <input
                type="radio"
                name="mode"
                value={m}
                checked={config.mode === m}
                onChange={() => set("mode", m)}
                disabled={recording.running}
              />
              {m === "loopback" ? "🔊 Loopback" : m === "mic" ? "🎙 Microphone" : "🔀 Both (Merge)"}
            </label>
          ))}
        </div>

        {(config.mode === "loopback" || config.mode === "merge") && (
          <div className={styles.field}>
            <label>Loopback device</label>
            <select
              value={config.device}
              onChange={(e) => set("device", e.target.value)}
              disabled={recording.running || loadingDevices}
            >
              <option value="">— Default output device —</option>
              {devices.loopback.map((d) => (
                <option key={d.name} value={d.name}>{d.name}</option>
              ))}
            </select>
          </div>
        )}

        {(config.mode === "mic" || config.mode === "merge") && (
          <div className={styles.field}>
            <label>{config.mode === "merge" ? "Microphone device" : "Device"}</label>
            <select
              value={config.mode === "merge" ? config.mic : config.device}
              onChange={(e) => set(config.mode === "merge" ? "mic" : "device", e.target.value)}
              disabled={recording.running || loadingDevices}
            >
              <option value="">— Select microphone —</option>
              {devices.mic.map((d) => (
                <option key={d} value={d}>{d}</option>
              ))}
            </select>
          </div>
        )}
      </div>

      <div className={styles.section}>
        <h3 className={styles.sectionTitle}>Model</h3>
        <div className={styles.row}>
          <div className={styles.field}>
            <label>Whisper model</label>
            <select value={config.model} onChange={(e) => set("model", e.target.value)} disabled={recording.running}>
              {MODELS.map((m) => <option key={m}>{m}</option>)}
            </select>
          </div>
          <div className={styles.field}>
            <label>Language</label>
            <select value={config.language} onChange={(e) => set("language", e.target.value)} disabled={recording.running}>
              {LANGUAGES.map(({ code, name }) => <option key={code} value={code}>{name}</option>)}
            </select>
          </div>
        </div>
      </div>

      <div className={styles.section}>
        <h3 className={styles.sectionTitle}>Output</h3>
        <div className={styles.field}>
          <label>Transcript prefix</label>
          <input
            type="text"
            value={config.output_prefix}
            onChange={(e) => set("output_prefix", e.target.value)}
            disabled={recording.running}
            placeholder="transcript"
          />
        </div>
        <div className={styles.checkRow}>
          <label className={styles.check}>
            <input type="checkbox" checked={config.save_audio} onChange={(e) => set("save_audio", e.target.checked)} disabled={recording.running} />
            Save audio (.wav)
          </label>
          <label className={styles.check}>
            <input type="checkbox" checked={config.summarize} onChange={(e) => set("summarize", e.target.checked)} disabled={recording.running} />
            Generate summary on stop
          </label>
        </div>
      </div>

      <div className={styles.section}>
        <h3 className={styles.sectionTitle}>Speaker Diarization</h3>
        <label className={styles.check}>
          <input type="checkbox" checked={config.diarize} onChange={(e) => set("diarize", e.target.checked)} disabled={recording.running} />
          Enable diarization (requires HF token)
        </label>
        {config.diarize && (
          <div className={styles.field} style={{ marginTop: 8 }}>
            <label>Number of speakers (optional)</label>
            <input
              type="number"
              min="1" max="10"
              value={config.num_speakers}
              onChange={(e) => set("num_speakers", e.target.value)}
              placeholder="auto"
              disabled={recording.running}
            />
          </div>
        )}
      </div>

      {error && <div className={styles.error}>{error}</div>}

      <div className={styles.actions}>
        {!recording.running ? (
          <button className={styles.startBtn} onClick={handleStart} disabled={starting}>
            {starting ? "Starting…" : "▶ Start Recording"}
          </button>
        ) : (
          <button className={styles.stopBtn} onClick={handleStop}>
            ■ Stop Recording
          </button>
        )}
        {recording.running && recording.output_file && (
          <span className={styles.activeFile}>→ {recording.output_file}</span>
        )}
      </div>

      {logLines.length > 0 && (
        <div className={styles.log}>
          <div className={styles.logTitle}>Console</div>
          <div className={styles.logContent}>
            {logLines.map((l, i) => (
              <div key={i} className={l.includes("[ERROR]") ? styles.logError : l.includes("[WARN]") ? styles.logWarn : ""}>{l}</div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
