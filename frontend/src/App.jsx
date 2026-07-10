import { useState, useEffect } from "react";
import TranscriptList from "./components/TranscriptList";
import TranscriptViewer from "./components/TranscriptViewer";
import LiveViewer from "./components/LiveViewer";
import RecordingPanel from "./components/RecordingPanel";
import ModelConfig from "./components/ModelConfig";
import { useRecording } from "./hooks/useRecording";

const TABS = [
  { id: "Viewer",    label: "Viewer",    icon: "📄" },
  { id: "Live",      label: "Live",      icon: "📡" },
  { id: "Recording", label: "Record",    icon: "🎙" },
  { id: "Settings",  label: "Settings",  icon: "⚙" },
];

function getInitialTheme() {
  const stored = localStorage.getItem("theme");
  if (stored) return stored;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export default function App() {
  const [activeTab, setActiveTab] = useState("Viewer");
  const [selectedFile, setSelectedFile] = useState(null);
  const [theme, setTheme] = useState(getInitialTheme);

  const { status: recording, start, stop, refreshStatus } = useRecording();

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "dark") {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }
    root.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
  }, [theme]);

  function toggleTheme() {
    setTheme((t) => (t === "dark" ? "light" : "dark"));
  }

  function handleSelect(filename) {
    setSelectedFile(filename);
    setActiveTab("Viewer");
  }

  function handleLive(filename) {
    setSelectedFile(filename);
    setActiveTab("Live");
  }

  async function handleStart(config) {
    const result = await start(config);
    if (result?.output_file) {
      setSelectedFile(result.output_file);
      setActiveTab("Live");
    }
  }

  async function handleStop() {
    await stop();
    refreshStatus();
  }

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-white dark:bg-gray-900">
      {/* ── Header ── */}
      <header className="flex items-center h-12 shrink-0 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 px-4 z-10">
        {/* Logo */}
        <span className="font-bold text-gray-900 dark:text-white mr-5 text-sm tracking-tight whitespace-nowrap">
          🎙 STT
        </span>

        {/* Tabs */}
        <nav className="flex gap-1 flex-1">
          {TABS.map(({ id, label, icon }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={[
                "px-3 py-1.5 rounded-md text-sm font-medium transition-colors duration-100",
                activeTab === id
                  ? "bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm"
                  : "text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-white/60 dark:hover:bg-gray-700/50",
              ].join(" ")}
            >
              <span className="hidden sm:inline mr-1">{icon}</span>
              {label}
            </button>
          ))}
        </nav>

        {/* Right controls */}
        <div className="flex items-center gap-3 ml-auto">
          {recording.running && (
            <span className="flex items-center gap-1.5 bg-red-500 text-white text-xs font-bold px-2.5 py-1 rounded-full animate-pulse">
              <span className="w-1.5 h-1.5 rounded-full bg-white" />
              REC
            </span>
          )}
          <button
            onClick={toggleTheme}
            title="Toggle theme"
            className="p-1.5 rounded-md border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors text-sm"
          >
            {theme === "dark" ? "☀" : "🌙"}
          </button>
        </div>
      </header>

      {/* ── Body ── */}
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <aside className="w-64 shrink-0 border-r border-gray-200 dark:border-gray-700 flex flex-col overflow-hidden bg-gray-50 dark:bg-gray-800">
          <TranscriptList
            selected={selectedFile}
            onSelect={handleSelect}
            onLive={handleLive}
            liveFile={recording.output_file}
          />
        </aside>

        {/* Main */}
        <main className="flex-1 overflow-hidden flex flex-col bg-white dark:bg-gray-900">
          {activeTab === "Viewer" && (
            <TranscriptViewer filename={selectedFile} />
          )}
          {activeTab === "Live" && (
            <LiveViewer filename={selectedFile || recording.output_file} isRecording={recording.running} onStop={handleStop} />
          )}
          {activeTab === "Recording" && (
            <RecordingPanel recording={recording} onStart={handleStart} onStop={handleStop} />
          )}
          {activeTab === "Settings" && (
            <ModelConfig />
          )}
        </main>
      </div>
    </div>
  );
}
