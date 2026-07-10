import { useEffect, useState } from "react";
import { useModelConfig } from "../hooks/useModelConfig";
import styles from "./ModelConfig.module.css";

const STT_PROVIDERS = [
  { value: "faster_whisper", label: "FasterWhisper (local)" },
  { value: "parakeet_nim",   label: "Parakeet NIM (NVIDIA API)" },
  { value: "parakeet_nemo",  label: "Parakeet NeMo (local / Docker)" },
];

const TRANSLATION_PROVIDERS = [
  { value: "anthropic", label: "Anthropic Claude" },
  { value: "ollama",    label: "Ollama (local)" },
  { value: "openai",    label: "OpenAI / Compatible" },
  { value: "gemini",    label: "Google Gemini" },
];

const STT_MODEL_PLACEHOLDERS = {
  faster_whisper: "small",
  parakeet_nim:   "nvidia/parakeet-tdt-0.6b-v3",
  parakeet_nemo:  "nvidia/parakeet-tdt-0.6b-v3",
};

const TRANSLATION_MODEL_PLACEHOLDERS = {
  anthropic: "claude-haiku-4-5-20251001",
  ollama:    "translategemma:4b",
  openai:    "gpt-4o-mini",
  gemini:    "gemini-1.5-flash",
};

const TRANSLATION_URL_PLACEHOLDERS = {
  ollama: "http://localhost:11434",
  openai: "https://api.openai.com/v1",
};

const LANGUAGES = [
  { value: "en", label: "English" },
  { value: "es", label: "Spanish" },
  { value: "fr", label: "French" },
  { value: "de", label: "German" },
  { value: "it", label: "Italian" },
  { value: "pt", label: "Portuguese" },
  { value: "zh", label: "Chinese" },
  { value: "ja", label: "Japanese" },
  { value: "ko", label: "Korean" },
];

function TestRow({ type, onTest, result, isTesting }) {
  return (
    <div className={styles.testRow}>
      <button
        className={styles.testBtn}
        onClick={() => onTest(type)}
        disabled={isTesting}
      >
        {isTesting ? "Testing…" : "Test connection"}
      </button>
      {result && (
        <span className={`${styles.testResult} ${result.ok ? styles.testOk : styles.testFail}`}>
          {result.ok ? "Connected" : result.detail || "Failed"}
        </span>
      )}
    </div>
  );
}

export default function ModelConfig() {
  const { config, loading, saving, error, testResults, testing, load, save, test } = useModelConfig();

  const [draft, setDraft]       = useState(null);
  const [saveStatus, setSaveStatus] = useState(null); // null | "ok" | "err"
  const [saveMsg, setSaveMsg]   = useState("");

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (config && !draft) setDraft(structuredClone(config));
  }, [config]);

  function setSTT(key, value) {
    setDraft((d) => ({ ...d, stt: { ...d.stt, [key]: value } }));
  }

  function setTranslation(key, value) {
    setDraft((d) => ({ ...d, translation: { ...d.translation, [key]: value } }));
  }

  async function handleSave() {
    setSaveStatus(null);
    const result = await save(draft);
    setSaveStatus(result.ok ? "ok" : "err");
    setSaveMsg(result.ok ? "Settings saved" : result.error || "Save failed");
    if (result.ok) {
      setTimeout(() => setSaveStatus(null), 3000);
    }
  }

  async function handleReset() {
    try {
      const res = await fetch("/api/config/reset", { method: "POST" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setDraft(structuredClone(data));
      setSaveStatus("ok");
      setSaveMsg("Reset to defaults");
      setTimeout(() => setSaveStatus(null), 3000);
    } catch (e) {
      setSaveStatus("err");
      setSaveMsg(e.message);
    }
  }

  if (loading || !draft) return <div className={styles.loading}>Loading settings…</div>;

  const stt   = draft.stt;
  const trans = draft.translation;
  const needsApiUrl  = (p) => p === "parakeet_nim";
  const needsApiKey  = (p) => p !== "faster_whisper" && p !== "parakeet_nemo";
  const transNeedsUrl = (p) => p === "ollama" || p === "openai";
  const transNeedsKey = (p) => p !== "ollama";

  return (
    <div className={styles.container}>
      <h2 className={styles.title}>Model Settings</h2>

      <div className={styles.grid}>
        {/* ── STT Card ─────────────────────────────────── */}
        <div className={styles.card}>
          <div className={styles.cardTitle}>Speech-to-Text</div>

          <div className={styles.field}>
            <label className={styles.label}>Provider</label>
            <select
              className={styles.select}
              value={stt.provider}
              onChange={(e) => setSTT("provider", e.target.value)}
            >
              {STT_PROVIDERS.map((p) => (
                <option key={p.value} value={p.value}>{p.label}</option>
              ))}
            </select>
          </div>

          <div className={styles.field}>
            <label className={styles.label}>Model</label>
            <input
              className={styles.input}
              type="text"
              value={stt.model || ""}
              placeholder={STT_MODEL_PLACEHOLDERS[stt.provider]}
              onChange={(e) => setSTT("model", e.target.value)}
            />
          </div>

          <div className={styles.field}>
            <label className={styles.label}>Language</label>
            <select
              className={styles.select}
              value={stt.language || "en"}
              onChange={(e) => setSTT("language", e.target.value)}
            >
              {LANGUAGES.map((l) => (
                <option key={l.value} value={l.value}>{l.label}</option>
              ))}
            </select>
          </div>

          {needsApiUrl(stt.provider) && (
            <div className={styles.field}>
              <label className={styles.label}>API URL</label>
              <input
                className={styles.input}
                type="text"
                value={stt.api_url || ""}
                placeholder="https://integrate.api.nvidia.com/v1"
                onChange={(e) => setSTT("api_url", e.target.value || null)}
              />
            </div>
          )}

          {needsApiKey(stt.provider) && (
            <div className={styles.field}>
              <label className={styles.label}>API Key</label>
              <input
                className={styles.input}
                type="password"
                value={stt.api_key || ""}
                placeholder={stt.api_key === "***" ? "key saved — leave blank to keep" : "nvapi-…"}
                onChange={(e) => setSTT("api_key", e.target.value || null)}
                autoComplete="new-password"
              />
            </div>
          )}

          <TestRow
            type="stt"
            onTest={test}
            result={testResults.stt}
            isTesting={testing.stt}
          />
        </div>

        {/* ── Translation Card ──────────────────────────── */}
        <div className={styles.card}>
          <div className={styles.cardTitle}>Translation</div>

          <div className={styles.field}>
            <label className={styles.label}>Provider</label>
            <select
              className={styles.select}
              value={trans.provider}
              onChange={(e) => setTranslation("provider", e.target.value)}
            >
              {TRANSLATION_PROVIDERS.map((p) => (
                <option key={p.value} value={p.value}>{p.label}</option>
              ))}
            </select>
          </div>

          <div className={styles.field}>
            <label className={styles.label}>Model</label>
            <input
              className={styles.input}
              type="text"
              value={trans.model || ""}
              placeholder={TRANSLATION_MODEL_PLACEHOLDERS[trans.provider]}
              onChange={(e) => setTranslation("model", e.target.value)}
            />
          </div>

          {transNeedsUrl(trans.provider) && (
            <div className={styles.field}>
              <label className={styles.label}>API URL</label>
              <input
                className={styles.input}
                type="text"
                value={trans.api_url || ""}
                placeholder={TRANSLATION_URL_PLACEHOLDERS[trans.provider] || ""}
                onChange={(e) => setTranslation("api_url", e.target.value || null)}
              />
            </div>
          )}

          {transNeedsKey(trans.provider) && (
            <div className={styles.field}>
              <label className={styles.label}>API Key</label>
              <input
                className={styles.input}
                type="password"
                value={trans.api_key || ""}
                placeholder={trans.api_key === "***" ? "key saved — leave blank to keep" : "sk-…"}
                onChange={(e) => setTranslation("api_key", e.target.value || null)}
                autoComplete="new-password"
              />
            </div>
          )}

          <TestRow
            type="translation"
            onTest={test}
            result={testResults.translation}
            isTesting={testing.translation}
          />
        </div>
      </div>

      <div className={styles.actions}>
        <button className={styles.saveBtn} onClick={handleSave} disabled={saving}>
          {saving ? "Saving…" : "Save settings"}
        </button>
        <button className={styles.resetBtn} onClick={handleReset} disabled={saving}>
          Reset defaults
        </button>
        {saveStatus && (
          <span className={`${styles.saveStatus} ${saveStatus === "ok" ? styles.saveOk : styles.saveErr}`}>
            {saveMsg}
          </span>
        )}
        {error && !saveStatus && (
          <span className={`${styles.saveStatus} ${styles.saveErr}`}>{error}</span>
        )}
      </div>
    </div>
  );
}
