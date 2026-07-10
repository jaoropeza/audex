import { useState, useEffect, useRef } from "react";
import TranscriptLine from "./TranscriptLine";
import { useSSE } from "../hooks/useSSE";
import { useTranslation } from "../hooks/useTranslation";

const LANGUAGES = ["English", "Spanish", "French", "Portuguese", "German", "Italian", "Japanese", "Chinese"];

const STATUS_DOT = {
  connecting: "bg-amber-400 animate-pulse",
  open:       "bg-emerald-500",
  eof:        "bg-gray-400",
  error:      "bg-red-500",
  idle:       "bg-gray-300 dark:bg-gray-600",
};

const STATUS_LABEL = {
  connecting: "Connecting…",
  open:       "Live",
  eof:        "Ended",
  error:      "Error",
  idle:       "Idle",
};

const inputCls = "rounded-md border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-xs px-2.5 py-1 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent";

export default function LiveViewer({ filename, isRecording, onStop }) {
  const [autoScroll, setAutoScroll] = useState(true);
  const [translateEnabled, setTranslateEnabled] = useState(false);
  const [targetLang, setTargetLang] = useState("English");
  const bottomRef = useRef(null);

  const url = filename ? `/api/stream/${encodeURIComponent(filename)}` : null;
  const { lines, status } = useSSE(url, !!filename);
  const { translations, translating } = useTranslation(lines, targetLang, translateEnabled);

  useEffect(() => {
    if (autoScroll && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [lines, autoScroll]);

  if (!filename) {
    return (
      <div className="flex flex-1 items-center justify-center text-gray-400 dark:text-gray-500">
        <div className="text-center">
          <div className="text-4xl mb-3">📡</div>
          <p className="text-sm">Start a recording session to see live transcription</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Toolbar */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 shrink-0 flex-wrap">
        {/* Status */}
        <div className="flex items-center gap-1.5">
          <span className={`w-2 h-2 rounded-full ${STATUS_DOT[status] ?? "bg-gray-400"}`} />
          <span className="text-xs font-medium text-gray-600 dark:text-gray-300">
            {STATUS_LABEL[status] ?? status}
          </span>
        </div>

        <span className="text-xs font-mono text-gray-400 dark:text-gray-500 truncate max-w-[180px]" title={filename}>
          {filename}
        </span>

        {translating && (
          <span className="text-xs text-blue-500 dark:text-blue-400 italic">translating…</span>
        )}

        <div className="flex items-center gap-3 ml-auto flex-wrap">
          {isRecording && onStop && (
            <button
              onClick={onStop}
              className="inline-flex items-center gap-1 rounded-md bg-red-600 hover:bg-red-700 text-white text-xs font-semibold px-3 py-1.5 transition-colors focus:outline-none focus:ring-2 focus:ring-red-500"
            >
              ■ Stop
            </button>
          )}
          <label className="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-300 cursor-pointer whitespace-nowrap">
            <input
              type="checkbox"
              checked={translateEnabled}
              onChange={(e) => setTranslateEnabled(e.target.checked)}
              className="rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500 w-3.5 h-3.5"
            />
            Translate
          </label>

          {translateEnabled && (
            <select
              className={inputCls}
              value={targetLang}
              onChange={(e) => setTargetLang(e.target.value)}
            >
              {LANGUAGES.map((l) => <option key={l}>{l}</option>)}
            </select>
          )}

          <label className="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-300 cursor-pointer whitespace-nowrap">
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
              className="rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500 w-3.5 h-3.5"
            />
            Auto-scroll
          </label>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto scrollbar-thin">
        {lines.length === 0 && status === "open" && (
          <div className="flex items-center justify-center py-12 text-gray-400 dark:text-gray-500 text-sm">
            Waiting for speech…
          </div>
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

      {/* EOF banner */}
      {status === "eof" && (
        <div className="flex items-center justify-center gap-2 px-4 py-2.5 bg-gray-100 dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 text-xs text-gray-500 dark:text-gray-400 shrink-0">
          <span className="w-1.5 h-1.5 rounded-full bg-gray-400" />
          Recording ended — {lines.length} line{lines.length !== 1 ? "s" : ""} captured
        </div>
      )}
    </div>
  );
}
