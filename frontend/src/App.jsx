import { useState, useEffect } from "react";
import TranscriptList from "./components/TranscriptList";
import TranscriptViewer from "./components/TranscriptViewer";
import LiveViewer from "./components/LiveViewer";
import RecordingPanel from "./components/RecordingPanel";
import ModelConfig from "./components/ModelConfig";
import { useRecording } from "./hooks/useRecording";
import styles from "./styles/App.module.css";

const TABS = ["Viewer", "Live", "Recording", "Settings"];

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
    document.documentElement.setAttribute("data-theme", theme);
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
    <div className={styles.app}>
      <header className={styles.header}>
        <span className={styles.logo}>🎙 STT</span>
        <nav className={styles.tabs}>
          {TABS.map((tab) => (
            <button
              key={tab}
              className={`${styles.tab} ${activeTab === tab ? styles.tabActive : ""}`}
              onClick={() => setActiveTab(tab)}
            >
              {tab}
            </button>
          ))}
        </nav>
        <div className={styles.headerRight}>
          {recording.running && (
            <span className={styles.recBadge}>
              <span className={styles.recDot} /> REC
            </span>
          )}
          <button className={styles.themeBtn} onClick={toggleTheme} title="Toggle theme">
            {theme === "dark" ? "☀" : "🌙"}
          </button>
        </div>
      </header>

      <aside className={styles.sidebar}>
        <TranscriptList
          selected={selectedFile}
          onSelect={handleSelect}
          onLive={handleLive}
          liveFile={recording.output_file}
        />
      </aside>

      <main className={styles.main}>
        {activeTab === "Viewer" && (
          <TranscriptViewer filename={selectedFile} />
        )}
        {activeTab === "Live" && (
          <LiveViewer filename={selectedFile || recording.output_file} isRecording={recording.running} />
        )}
        {activeTab === "Recording" && (
          <RecordingPanel recording={recording} onStart={handleStart} onStop={handleStop} />
        )}
        {activeTab === "Settings" && (
          <ModelConfig />
        )}
      </main>
    </div>
  );
}
