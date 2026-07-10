import { useState } from "react";

const SOURCE_LANGS = [
  "Auto", "English", "Spanish", "French", "German", "Portuguese",
  "Italian", "Japanese", "Chinese", "Arabic", "Russian", "Korean",
];
const TARGET_LANGS = [
  "English", "Spanish", "French", "German", "Portuguese",
  "Italian", "Japanese", "Chinese", "Arabic", "Russian", "Korean",
];

// translategemma-style default prompt (placeholders: {source_lang}, {target_lang}, {texts})
const DEFAULT_PROMPT =
  `You are a professional {source_lang} to {target_lang} translator. ` +
  `Your goal is to accurately convey the meaning and nuances of the original text ` +
  `while adhering to {target_lang} grammar, vocabulary, and cultural sensitivities. ` +
  `Produce only the {target_lang} translation of each numbered line, ` +
  `keeping the exact same numbered format (1. 2. 3. etc). ` +
  `Do not add explanations, commentary, or extra text. ` +
  `Please translate the following text into {target_lang}:\n\n\n{texts}`;

const pillBase =
  "px-2.5 py-1 rounded-full text-xs font-medium border transition-colors focus:outline-none";
const pillActive =
  "bg-blue-600 border-blue-600 text-white";
const pillIdle =
  "border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-300 bg-white dark:bg-gray-700 hover:border-blue-400 hover:text-blue-600 dark:hover:text-blue-300";

function LangPill({ label, active, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`${pillBase} ${active ? pillActive : pillIdle}`}
    >
      {label}
    </button>
  );
}

export default function TranslateModal({ lineCount, initialSource, initialTarget, initialPrompt, onClose, onApply }) {
  const [sourceLang, setSourceLang] = useState(initialSource || "Auto");
  const [targetLang, setTargetLang] = useState(initialTarget || "English");
  const [showPrompt, setShowPrompt] = useState(false);
  const [prompt, setPrompt] = useState(initialPrompt || "");

  function handleApply() {
    onApply({
      sourceLang,
      targetLang,
      promptTemplate: prompt.trim() || null,
    });
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl border border-gray-200 dark:border-gray-700 w-full max-w-lg mx-4 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100 dark:border-gray-700">
          <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
            🌐 Translate transcript
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 text-lg leading-none"
          >
            ×
          </button>
        </div>

        <div className="px-5 py-4 space-y-5">
          {/* Source Language */}
          <div>
            <label className="block text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
              Source language
            </label>
            <div className="flex flex-wrap gap-1.5">
              {SOURCE_LANGS.map((lang) => (
                <LangPill
                  key={lang}
                  label={lang === "Auto" ? "Auto-detect" : lang}
                  active={sourceLang === lang}
                  onClick={() => setSourceLang(lang)}
                />
              ))}
            </div>
          </div>

          {/* Target Language */}
          <div>
            <label className="block text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
              Target language
            </label>
            <div className="flex flex-wrap gap-1.5">
              {TARGET_LANGS.map((lang) => (
                <LangPill
                  key={lang}
                  label={lang}
                  active={targetLang === lang}
                  onClick={() => setTargetLang(lang)}
                />
              ))}
            </div>
          </div>

          {/* Prompt customization (collapsible) */}
          <div>
            <button
              type="button"
              onClick={() => setShowPrompt((s) => !s)}
              className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors"
            >
              <span className="text-[10px]">{showPrompt ? "▲" : "▼"}</span>
              Customize prompt
              {prompt.trim() && !showPrompt && (
                <span className="ml-1 px-1.5 py-0.5 rounded bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 text-[10px]">
                  custom
                </span>
              )}
            </button>

            {showPrompt && (
              <div className="mt-2 space-y-2">
                <textarea
                  rows={8}
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder={DEFAULT_PROMPT}
                  className="w-full rounded-md border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-xs px-3 py-2 font-mono focus:outline-none focus:ring-1 focus:ring-blue-500 placeholder-gray-300 dark:placeholder-gray-600 resize-y"
                />
                <p className="text-[10px] text-gray-400 dark:text-gray-500 leading-relaxed">
                  Available placeholders: <code className="font-mono">{"{source_lang}"}</code>{" "}
                  <code className="font-mono">{"{target_lang}"}</code>{" "}
                  <code className="font-mono">{"{source_code}"}</code>{" "}
                  <code className="font-mono">{"{target_code}"}</code>{" "}
                  <code className="font-mono">{"{texts}"}</code> (numbered lines).
                  Leave blank to use the default translategemma-style prompt.
                </p>
                {prompt.trim() && (
                  <button
                    type="button"
                    onClick={() => setPrompt("")}
                    className="text-[10px] text-gray-400 hover:text-red-500 dark:hover:text-red-400 transition-colors"
                  >
                    ↺ Reset to default
                  </button>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 px-5 py-3 border-t border-gray-100 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/60">
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1.5 rounded-md text-xs font-medium text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleApply}
            disabled={!targetLang}
            className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-md bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold transition-colors disabled:opacity-50"
          >
            Translate {lineCount} lines →
          </button>
        </div>
      </div>
    </div>
  );
}
