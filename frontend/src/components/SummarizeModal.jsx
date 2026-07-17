import { useState, useEffect } from "react";
import { apiFetch } from "../utils/api";
import { SUMMARY_PRESETS } from "./ModelConfig";

const textareaCls =
  "block w-full rounded-md border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-[11px] font-mono px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-y";

export default function SummarizeModal({ filename, lineCount, onClose, onDone }) {
  const [promptTemplate, setPromptTemplate] = useState("");
  const [defaultPrompt, setDefaultPrompt] = useState("");
  const [summarizing, setSummarizing] = useState(false);
  const [error, setError] = useState(null);

  // Load saved summary config to get the configured prompt template
  useEffect(() => {
    fetch("/api/config")
      .then((r) => r.json())
      .then((cfg) => {
        const saved = cfg?.summary?.prompt_template || "";
        setDefaultPrompt(saved);
        setPromptTemplate(saved);
      })
      .catch(() => {});
  }, []);

  function applyPreset(key) {
    setPromptTemplate(SUMMARY_PRESETS[key].prompt);
  }

  function clearTemplate() {
    setPromptTemplate("");
  }

  async function handleConfirm() {
    setSummarizing(true);
    setError(null);
    try {
      const body = promptTemplate.trim()
        ? { prompt_template: promptTemplate }
        : {};
      const res = await apiFetch(
        `/api/transcripts/${encodeURIComponent(filename)}/summarize`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      );
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      onDone(data.summary);
    } catch (e) {
      setError(e.message);
    } finally {
      setSummarizing(false);
    }
  }

  const effectiveTemplate = promptTemplate.trim()
    ? promptTemplate
    : "(default prompt will be used)";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col border border-gray-200 dark:border-gray-700">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200 dark:border-gray-700 shrink-0">
          <div>
            <h2 className="text-base font-semibold text-gray-900 dark:text-gray-100">Generate Summary</h2>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
              {filename} · {lineCount} line{lineCount !== 1 ? "s" : ""}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-md text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {/* Preset buttons */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">Prompt template</span>
              <div className="flex gap-1 ml-auto">
                {Object.entries(SUMMARY_PRESETS).map(([key, preset]) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => applyPreset(key)}
                    className="text-xs px-2.5 py-1 rounded-md border border-blue-200 dark:border-blue-700 text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors font-medium"
                  >
                    {preset.label} preset
                  </button>
                ))}
                {promptTemplate.trim() && (
                  <button
                    type="button"
                    onClick={clearTemplate}
                    className="text-xs px-2.5 py-1 rounded-md border border-gray-200 dark:border-gray-600 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                  >
                    Use default
                  </button>
                )}
              </div>
            </div>
            <textarea
              className={textareaCls}
              rows={12}
              value={promptTemplate}
              placeholder={"(leave empty to use the configured default prompt)\n\nThe {transcript} parameter will be replaced with the full transcript text."}
              onChange={(e) => setPromptTemplate(e.target.value)}
            />
            <p className="mt-1 text-[10px] text-gray-400 dark:text-gray-500">
              Use <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">{"{transcript}"}</code> as placeholder for the transcript text.
              {!promptTemplate.trim() && defaultPrompt && (
                <span className="ml-1 text-amber-500 dark:text-amber-400">Using configured template from Settings.</span>
              )}
              {!promptTemplate.trim() && !defaultPrompt && (
                <span className="ml-1 text-gray-400 dark:text-gray-500">Using built-in default template.</span>
              )}
            </p>
          </div>

          {error && (
            <div className="rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 px-4 py-3 text-sm text-red-700 dark:text-red-300">
              {error}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-5 py-4 border-t border-gray-200 dark:border-gray-700 shrink-0">
          <button
            onClick={onClose}
            disabled={summarizing}
            className="px-4 py-2 rounded-lg border border-gray-200 dark:border-gray-600 text-gray-700 dark:text-gray-200 text-sm font-medium hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            disabled={summarizing}
            className="inline-flex items-center gap-2 px-5 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white text-sm font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:cursor-not-allowed"
          >
            {summarizing && (
              <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            )}
            {summarizing ? "Generating…" : "Confirm & Summarize"}
          </button>
        </div>
      </div>
    </div>
  );
}
