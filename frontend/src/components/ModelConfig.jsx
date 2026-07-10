import { useEffect, useState } from "react";
import { useModelConfig } from "../hooks/useModelConfig";

const STT_PROVIDERS = [
  { value: "faster_whisper", label: "FasterWhisper (local)" },
  { value: "parakeet_nim",   label: "Parakeet NIM (NVIDIA API)" },
  { value: "parakeet_nemo",  label: "Parakeet NeMo (local / Docker)" },
];

const LLM_PROVIDERS = [
  { value: "anthropic", label: "Anthropic Claude" },
  { value: "ollama",    label: "Ollama (local)" },
  { value: "openai",    label: "OpenAI / Compatible" },
  { value: "gemini",    label: "Google Gemini" },
];

const STT_MODEL_HINTS = {
  faster_whisper: "large-v3",
  parakeet_nim:   "nvidia/parakeet-tdt-0.6b-v3",
  parakeet_nemo:  "nvidia/parakeet-tdt-0.6b-v3",
};

const LLM_MODEL_HINTS = {
  anthropic: "claude-haiku-4-5-20251001",
  ollama:    "translategemma:4b",
  openai:    "gpt-4o-mini",
  gemini:    "gemini-1.5-flash",
};

const LLM_URL_HINTS = {
  ollama: "http://localhost:11434",
  openai: "https://api.openai.com/v1",
};

const LANGUAGES = [
  { value: "auto", label: "Auto-detect" },
  { value: "en", label: "English" }, { value: "es", label: "Spanish" },
  { value: "fr", label: "French" },  { value: "de", label: "German" },
  { value: "it", label: "Italian" }, { value: "pt", label: "Portuguese" },
  { value: "zh", label: "Chinese" }, { value: "ja", label: "Japanese" },
  { value: "ko", label: "Korean" },
];

const DEFAULT_TRANSLATION_PROMPT =
`Translate the following numbered transcript lines into {target_language}.
Rules:
- Return ONLY the numbered lines in the same format: "1. translated text"
- Do NOT translate proper nouns, product names, or technical terms.
- Preserve natural spoken-word flow; these are transcribed speech lines.
- If a line is already in the target language, copy it unchanged.

{texts}`;

const DEFAULT_SUMMARY_PROMPT =
`You are a professional meeting assistant. Analyze the following conversation transcript and produce a structured summary in the SAME language as the transcript.

TRANSCRIPT:
{transcript}

Write the summary using these sections exactly:

## Overview
2–3 sentences describing what was discussed.

## Key Decisions & Agreements
Bullet list of decisions or agreements reached. Write "None identified" if none.

## Action Items
Bullet list of concrete tasks, with the responsible person when mentioned. Write "None identified" if none.

## Next Steps
What should happen after this conversation ends. Write "None identified" if none.

## Notable Points
Any other important facts, context, risks, or follow-up items worth remembering.`;

export const SUMMARY_PRESETS = {
  en: {
    label: "English",
    prompt: `You are a professional meeting assistant. Analyze the following conversation transcript and produce a structured summary.

TRANSCRIPT:
{transcript}

Write the summary using these sections exactly:

## Overview
2–3 sentences describing what was discussed.

## Key Decisions & Agreements
Bullet list of decisions or agreements reached. Write "None identified" if none.

## Action Items
Bullet list of concrete tasks, with the responsible person when mentioned. Write "None identified" if none.

## Next Steps
What should happen after this conversation ends. Write "None identified" if none.

## Notable Points
Any other important facts, context, risks, or follow-up items worth remembering.`,
  },
  es: {
    label: "Español",
    prompt: `Eres un asistente profesional de reuniones. Analiza la siguiente transcripción de conversación y produce un resumen estructurado.

TRANSCRIPCIÓN:
{transcript}

Escribe el resumen usando exactamente estas secciones:

## Resumen General
2–3 oraciones describiendo qué se discutió.

## Decisiones y Acuerdos Clave
Lista de decisiones o acuerdos alcanzados. Escribe "Ninguno identificado" si no hay.

## Elementos de Acción
Lista de tareas concretas, con la persona responsable cuando se mencione. Escribe "Ninguno identificado" si no hay.

## Próximos Pasos
Qué debe ocurrir después de que termine esta conversación. Escribe "Ninguno identificado" si no hay.

## Puntos Notables
Cualquier otro hecho importante, contexto, riesgos o elementos de seguimiento que valga la pena recordar.`,
  },
};

const fieldCls = "block w-full rounded-md border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent placeholder-gray-400 dark:placeholder-gray-500";
const labelCls = "block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1 uppercase tracking-wide";
const promptCls = "block w-full rounded-md border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-[11px] font-mono px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent placeholder-gray-400 dark:placeholder-gray-500 resize-y";

function Field({ label, hint, children }) {
  return (
    <div>
      <label className={labelCls}>{label}</label>
      {children}
      {hint && <p className="mt-1 text-[10px] text-gray-400 dark:text-gray-500">{hint}</p>}
    </div>
  );
}

function TestButton({ type, onTest, result, isTesting }) {
  return (
    <div className="flex items-center gap-2 pt-1">
      <button
        onClick={() => onTest(type)}
        disabled={isTesting}
        data-twe-ripple-init
        className="inline-flex items-center gap-1.5 rounded-md border border-blue-500 dark:border-blue-400 text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 px-3 py-1.5 text-xs font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {isTesting && <span className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />}
        {isTesting ? "Testing…" : "Test connection"}
      </button>
      {result && (
        <span className={[
          "text-xs px-2 py-1 rounded-md font-medium",
          result.ok
            ? "bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-700"
            : "bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-700",
        ].join(" ")}>
          {result.ok ? "✓ Connected" : `✗ ${result.detail || "Failed"}`}
        </span>
      )}
    </div>
  );
}

function Card({ title, children }) {
  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 shadow-sm overflow-hidden">
      <div className="px-5 py-3 border-b border-gray-100 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/80">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">{title}</h3>
      </div>
      <div className="p-5 space-y-3">
        {children}
      </div>
    </div>
  );
}

export default function ModelConfig() {
  const { config, loading, saving, error, testResults, testing, load, save, test } = useModelConfig();
  const [draft, setDraft] = useState(null);
  const [saveStatus, setSaveStatus] = useState(null);
  const [saveMsg, setSaveMsg] = useState("");

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (config && !draft) {
      setDraft({
        ...structuredClone(config),
        summary: config.summary ?? {
          provider: "anthropic", model: "claude-haiku-4-5-20251001",
          api_url: null, api_key: null, prompt_template: null,
        },
      });
    }
  }, [config]);

  function setSTT(key, value)    { setDraft((d) => ({ ...d, stt:         { ...d.stt,         [key]: value } })); }
  function setTrans(key, value)  { setDraft((d) => ({ ...d, translation:  { ...d.translation,  [key]: value } })); }
  function setSummary(key, value){ setDraft((d) => ({ ...d, summary:      { ...d.summary,      [key]: value } })); }

  async function handleSave() {
    setSaveStatus(null);
    const result = await save(draft);
    setSaveStatus(result.ok ? "ok" : "err");
    setSaveMsg(result.ok ? "Settings saved successfully" : result.error || "Save failed");
    if (result.ok) setTimeout(() => setSaveStatus(null), 3500);
  }

  async function handleReset() {
    try {
      const res = await fetch("/api/config/reset", { method: "POST" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setDraft(structuredClone(data));
      setSaveStatus("ok");
      setSaveMsg("Reset to defaults");
      setTimeout(() => setSaveStatus(null), 3500);
    } catch (e) {
      setSaveStatus("err");
      setSaveMsg(e.message);
    }
  }

  if (loading || !draft) {
    return (
      <div className="flex flex-1 items-center justify-center text-gray-400 dark:text-gray-500">
        <div className="flex items-center gap-2 text-sm">
          <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
          Loading settings…
        </div>
      </div>
    );
  }

  const stt   = draft.stt;
  const trans = draft.translation;
  const summ  = draft.summary;

  const sttNeedsApiUrl = stt.provider === "parakeet_nim";
  const sttNeedsApiKey = stt.provider !== "faster_whisper" && stt.provider !== "parakeet_nemo";
  const transNeedsUrl  = trans.provider === "ollama" || trans.provider === "openai";
  const transNeedsKey  = trans.provider !== "ollama";
  const summNeedsUrl   = summ.provider === "ollama" || summ.provider === "openai";
  const summNeedsKey   = summ.provider !== "ollama";

  return (
    <div className="flex flex-col h-full overflow-y-auto scrollbar-thin">
      <div className="p-5 max-w-4xl mx-auto w-full space-y-5">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Model Settings</h2>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* ── STT Card ── */}
          <Card title="Speech-to-Text">
            <Field label="Provider">
              <select className={fieldCls} value={stt.provider} onChange={(e) => setSTT("provider", e.target.value)}>
                {STT_PROVIDERS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
              </select>
            </Field>

            <Field label="Model">
              <input
                className={fieldCls}
                type="text"
                value={stt.model || ""}
                placeholder={STT_MODEL_HINTS[stt.provider]}
                onChange={(e) => setSTT("model", e.target.value)}
              />
            </Field>

            <Field label="Language">
              <select className={fieldCls} value={stt.language || "es"} onChange={(e) => setSTT("language", e.target.value)}>
                {LANGUAGES.map((l) => <option key={l.value} value={l.value}>{l.label}</option>)}
              </select>
            </Field>

            {sttNeedsApiUrl && (
              <Field label="API URL">
                <input
                  className={fieldCls}
                  type="url"
                  value={stt.api_url || ""}
                  placeholder="https://integrate.api.nvidia.com/v1"
                  onChange={(e) => setSTT("api_url", e.target.value || null)}
                />
              </Field>
            )}

            {sttNeedsApiKey && (
              <Field label="API Key">
                <input
                  className={fieldCls}
                  type="password"
                  value={stt.api_key || ""}
                  placeholder={stt.api_key === "***" ? "key saved — leave blank to keep" : "nvapi-…"}
                  onChange={(e) => setSTT("api_key", e.target.value || null)}
                  autoComplete="new-password"
                />
              </Field>
            )}

            <TestButton type="stt" onTest={(t) => test(t, draft)} result={testResults.stt} isTesting={testing.stt} />
          </Card>

          {/* ── Translation Card ── */}
          <Card title="Translation">
            <Field label="Provider">
              <select className={fieldCls} value={trans.provider} onChange={(e) => setTrans("provider", e.target.value)}>
                {LLM_PROVIDERS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
              </select>
            </Field>

            <Field label="Model">
              <input
                className={fieldCls}
                type="text"
                value={trans.model || ""}
                placeholder={LLM_MODEL_HINTS[trans.provider]}
                onChange={(e) => setTrans("model", e.target.value)}
              />
            </Field>

            {transNeedsUrl && (
              <Field label="API URL">
                <input
                  className={fieldCls}
                  type="url"
                  value={trans.api_url || ""}
                  placeholder={LLM_URL_HINTS[trans.provider] || ""}
                  onChange={(e) => setTrans("api_url", e.target.value || null)}
                />
              </Field>
            )}

            {transNeedsKey && (
              <Field label="API Key">
                <input
                  className={fieldCls}
                  type="password"
                  value={trans.api_key || ""}
                  placeholder={trans.api_key === "***" ? "key saved — leave blank to keep" : "sk-…"}
                  onChange={(e) => setTrans("api_key", e.target.value || null)}
                  autoComplete="new-password"
                />
              </Field>
            )}

            <Field label="Prompt template" hint="Parameters: {texts}, {target_language} — leave empty to use default">
              <textarea
                className={promptCls}
                rows={5}
                value={trans.prompt_template || ""}
                placeholder={DEFAULT_TRANSLATION_PROMPT}
                onChange={(e) => setTrans("prompt_template", e.target.value || null)}
              />
            </Field>

            <TestButton type="translation" onTest={(t) => test(t, draft)} result={testResults.translation} isTesting={testing.translation} />
          </Card>
        </div>

        {/* ── Summary Card (full width) ── */}
        <Card title="Summary">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="space-y-3">
              <Field label="Provider">
                <select className={fieldCls} value={summ.provider} onChange={(e) => setSummary("provider", e.target.value)}>
                  {LLM_PROVIDERS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
                </select>
              </Field>

              <Field label="Model">
                <input
                  className={fieldCls}
                  type="text"
                  value={summ.model || ""}
                  placeholder={LLM_MODEL_HINTS[summ.provider]}
                  onChange={(e) => setSummary("model", e.target.value)}
                />
              </Field>

              {summNeedsUrl && (
                <Field label="API URL">
                  <input
                    className={fieldCls}
                    type="url"
                    value={summ.api_url || ""}
                    placeholder={LLM_URL_HINTS[summ.provider] || ""}
                    onChange={(e) => setSummary("api_url", e.target.value || null)}
                  />
                </Field>
              )}

              {summNeedsKey && (
                <Field label="API Key">
                  <input
                    className={fieldCls}
                    type="password"
                    value={summ.api_key || ""}
                    placeholder={summ.api_key === "***" ? "key saved — leave blank to keep" : "sk-…"}
                    onChange={(e) => setSummary("api_key", e.target.value || null)}
                    autoComplete="new-password"
                  />
                </Field>
              )}

              <TestButton type="summary" onTest={(t) => test(t, draft)} result={testResults.summary} isTesting={testing.summary} />
            </div>

            <div>
              <div className="flex items-center justify-between mb-1">
                <label className={labelCls}>Prompt template</label>
                <div className="flex gap-1">
                  {Object.entries(SUMMARY_PRESETS).map(([key, preset]) => (
                    <button
                      key={key}
                      type="button"
                      onClick={() => setSummary("prompt_template", preset.prompt)}
                      className="text-[10px] px-2 py-0.5 rounded border border-gray-300 dark:border-gray-600 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                    >
                      {preset.label}
                    </button>
                  ))}
                  {summ.prompt_template && (
                    <button
                      type="button"
                      onClick={() => setSummary("prompt_template", null)}
                      className="text-[10px] px-2 py-0.5 rounded border border-red-200 dark:border-red-800 text-red-500 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                    >
                      Clear
                    </button>
                  )}
                </div>
              </div>
              <textarea
                className={`${promptCls} h-full min-h-[200px]`}
                value={summ.prompt_template || ""}
                placeholder={DEFAULT_SUMMARY_PROMPT}
                onChange={(e) => setSummary("prompt_template", e.target.value || null)}
              />
              <p className="mt-1 text-[10px] text-gray-400 dark:text-gray-500">Parameter: {"{transcript}"} — leave empty to use default</p>
            </div>
          </div>
        </Card>

        {/* Actions */}
        <div className="flex items-center gap-3 pt-1 flex-wrap">
          <button
            onClick={handleSave}
            disabled={saving}
            data-twe-ripple-init
            data-twe-ripple-color="light"
            className="inline-flex items-center gap-2 rounded-lg bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white font-semibold px-5 py-2.5 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:cursor-not-allowed"
          >
            {saving && <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />}
            {saving ? "Saving…" : "Save settings"}
          </button>

          <button
            onClick={handleReset}
            disabled={saving}
            className="rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-200 font-medium px-4 py-2.5 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-gray-400 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Reset defaults
          </button>

          {saveStatus && (
            <span className={[
              "text-sm font-medium",
              saveStatus === "ok" ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400",
            ].join(" ")}>
              {saveStatus === "ok" ? "✓" : "✗"} {saveMsg}
            </span>
          )}
          {error && !saveStatus && (
            <span className="text-sm text-red-600 dark:text-red-400">{error}</span>
          )}
        </div>
      </div>
    </div>
  );
}
