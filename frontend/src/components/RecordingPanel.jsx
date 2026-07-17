import { useState, useEffect } from "react";
import { useSSE } from "../hooks/useSSE";
import { apiFetch } from "../utils/api";

const selectCls = "w-full rounded-md border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-50 disabled:cursor-not-allowed";
const inputCls  = "w-full rounded-md border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-50 disabled:cursor-not-allowed";
const labelCls  = "block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1";

function Section({ title, children }) {
  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4">
      <h3 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-3">
        {title}
      </h3>
      {children}
    </div>
  );
}

export default function RecordingPanel({ recording, onStart, onStop }) {
  const [devices, setDevices] = useState({ mic: [], loopback: [] });
  const [loadingDevices, setLoadingDevices] = useState(false);
  const [config, setConfig] = useState({
    mode: "loopback", device: "", mic: "",
    diarize: false, num_speakers: "",
    output_prefix: "transcript",
    save_audio: false, summarize: false,
  });
  const [starting, setSending] = useState(false);
  const [error, setError] = useState(null);

  const logUrl = recording.running ? "/api/recording/log" : null;
  const { lines: logLines } = useSSE(logUrl, recording.running);

  useEffect(() => {
    setLoadingDevices(true);
    apiFetch("/api/recording/devices")
      .then((r) => r.ok ? r.json() : null)
      .then((d) => { if (d) setDevices(d); setLoadingDevices(false); })
      .catch(() => setLoadingDevices(false));
  }, []);

  function set(key, val) { setConfig((prev) => ({ ...prev, [key]: val })); }

  async function handleStart() {
    setSending(true); setError(null);
    try {
      await onStart({
        ...config,
        num_speakers: config.num_speakers ? parseInt(config.num_speakers) : null,
        device: config.device || null,
        mic: config.mic || null,
      });
    } catch (err) { setError(err.message); }
    finally { setSending(false); }
  }

  async function handleStop() {
    try { await onStop(); } catch (err) { setError(err.message); }
  }

  const disabled = recording.running;

  const MODES = [
    { id: "loopback", label: "🔊 Loopback" },
    { id: "mic",      label: "🎙 Microphone" },
    { id: "merge",    label: "🔀 Both" },
  ];

  return (
    <div className="flex flex-col h-full overflow-y-auto scrollbar-thin">
      <div className="p-4 space-y-3 max-w-2xl mx-auto w-full">

        {/* Audio Source */}
        <Section title="Audio Source">
          {/* Mode toggle */}
          <div className="flex rounded-lg overflow-hidden border border-gray-200 dark:border-gray-700 mb-3">
            {MODES.map(({ id, label }) => (
              <button
                key={id}
                onClick={() => set("mode", id)}
                disabled={disabled}
                className={[
                  "flex-1 py-2 text-xs font-medium transition-colors focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed",
                  config.mode === id
                    ? "bg-blue-600 text-white"
                    : "bg-white dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-600",
                ].join(" ")}
              >
                {label}
              </button>
            ))}
          </div>

          {(config.mode === "loopback" || config.mode === "merge") && (
            <div className="mb-2">
              <label className={labelCls}>Loopback device</label>
              <select
                className={selectCls}
                value={config.device}
                onChange={(e) => set("device", e.target.value)}
                disabled={disabled || loadingDevices}
              >
                <option value="">— Default output device —</option>
                {devices.loopback.map((d) => (
                  <option key={d.name} value={d.name}>{d.name}</option>
                ))}
              </select>
            </div>
          )}

          {(config.mode === "mic" || config.mode === "merge") && (
            <div>
              <label className={labelCls}>
                {config.mode === "merge" ? "Microphone device" : "Device"}
              </label>
              <select
                className={selectCls}
                value={config.mode === "merge" ? config.mic : config.device}
                onChange={(e) => set(config.mode === "merge" ? "mic" : "device", e.target.value)}
                disabled={disabled || loadingDevices}
              >
                <option value="">— Select microphone —</option>
                {devices.mic.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
            </div>
          )}
        </Section>

        {/* Output */}
        <Section title="Output">
          <div className="mb-3">
            <label className={labelCls}>Transcript file prefix</label>
            <input
              className={inputCls}
              type="text"
              value={config.output_prefix}
              onChange={(e) => set("output_prefix", e.target.value)}
              disabled={disabled}
              placeholder="transcript"
            />
          </div>
          <div className="flex gap-5">
            <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300 cursor-pointer">
              <input
                type="checkbox"
                checked={config.save_audio}
                onChange={(e) => set("save_audio", e.target.checked)}
                disabled={disabled}
                className="rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500 w-4 h-4"
              />
              Save audio (.wav)
            </label>
            <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300 cursor-pointer">
              <input
                type="checkbox"
                checked={config.summarize}
                onChange={(e) => set("summarize", e.target.checked)}
                disabled={disabled}
                className="rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500 w-4 h-4"
              />
              Generate summary on stop
            </label>
          </div>
        </Section>

        {/* Diarization */}
        <Section title="Speaker Diarization">
          <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300 cursor-pointer mb-3">
            <input
              type="checkbox"
              checked={config.diarize}
              onChange={(e) => set("diarize", e.target.checked)}
              disabled={disabled}
              className="rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500 w-4 h-4"
            />
            Enable diarization (requires HuggingFace token)
          </label>
          {config.diarize && (
            <div>
              <label className={labelCls}>Number of speakers (optional)</label>
              <input
                className={`${inputCls} max-w-[120px]`}
                type="number"
                min="1" max="10"
                value={config.num_speakers}
                onChange={(e) => set("num_speakers", e.target.value)}
                placeholder="auto"
                disabled={disabled}
              />
            </div>
          )}
        </Section>

        {/* Error */}
        {error && (
          <div className="rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 px-4 py-3 text-sm text-red-700 dark:text-red-300">
            {error}
          </div>
        )}

        {/* Action buttons */}
        <div className="flex items-center gap-3">
          {!recording.running ? (
            <button
              onClick={handleStart}
              disabled={starting}
              data-twe-ripple-init
              data-twe-ripple-color="light"
              className="inline-flex items-center gap-2 rounded-lg bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white font-semibold px-5 py-2.5 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:cursor-not-allowed"
            >
              {starting ? (
                <>
                  <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Starting…
                </>
              ) : (
                <>▶ Start Recording</>
              )}
            </button>
          ) : (
            <button
              onClick={handleStop}
              data-twe-ripple-init
              data-twe-ripple-color="light"
              className="inline-flex items-center gap-2 rounded-lg bg-red-600 hover:bg-red-700 text-white font-semibold px-5 py-2.5 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2"
            >
              ■ Stop Recording
            </button>
          )}
          {recording.running && recording.output_file && (
            <span className="text-xs text-gray-500 dark:text-gray-400 font-mono truncate">
              → {recording.output_file}
            </span>
          )}
        </div>

        {/* Console log */}
        {logLines.length > 0 && (
          <div className="rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
            <div className="px-3 py-1.5 bg-gray-100 dark:bg-gray-800 text-xs font-semibold text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
              Console
            </div>
            <div className="bg-gray-900 dark:bg-black p-3 max-h-36 overflow-y-auto scrollbar-thin">
              {logLines.map((l, i) => (
                <div
                  key={i}
                  className={[
                    "text-[11px] font-mono leading-5",
                    l.includes("[ERROR]") ? "text-red-400" :
                    l.includes("[WARN]")  ? "text-amber-400" :
                    "text-gray-300",
                  ].join(" ")}
                >
                  {l}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
