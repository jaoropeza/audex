import { useState, useEffect } from "react";
import TranscriptList from "./components/TranscriptList";
import TranscriptViewer from "./components/TranscriptViewer";
import LiveViewer from "./components/LiveViewer";
import RecordingPanel from "./components/RecordingPanel";
import ModelConfig from "./components/ModelConfig";
import AdminPanel from "./components/AdminPanel";
import CategoriesManager from "./components/CategoriesManager";
import SpeakersManager from "./components/SpeakersManager";
import LoginPage from "./pages/LoginPage";
import { useAuthContext } from "./contexts/AuthContext";
import { useRecording } from "./hooks/useRecording";

function getInitialTheme() {
  const stored = localStorage.getItem("theme");
  if (stored) return stored;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

const BASE_TABS = [
  { id: "Viewer",     label: "Viewer",     icon: "📄" },
  { id: "Live",       label: "Live",       icon: "📡" },
  { id: "Recording",  label: "Record",     icon: "🎙" },
  { id: "Categories", label: "Categories", icon: "🏷" },
  { id: "Speakers",   label: "Speakers",   icon: "🎤" },
  { id: "Settings",   label: "Settings",   icon: "⚙" },
];

const VALID_TABS = new Set(["Viewer", "Live", "Recording", "Categories", "Speakers", "Settings", "Admin"]);

function getInitialTab() {
  const stored = localStorage.getItem("activeTab");
  return stored && VALID_TABS.has(stored) ? stored : "Viewer";
}

function AppShell() {
  const { user, isAdmin, logout, loading } = useAuthContext();
  const [activeTab,    setActiveTab]    = useState(getInitialTab);
  const [selectedFile, setSelectedFile] = useState(null);
  const [theme,        setTheme]        = useState(getInitialTheme);

  const { status: recording, start, stop, refreshStatus } = useRecording();

  const TABS = isAdmin
    ? [...BASE_TABS, { id: "Admin", label: "Admin", icon: "🛡" }]
    : BASE_TABS;

  function switchTab(id) {
    // When navigating to Live while a recording is running, always show the live file
    if (id === "Live" && recording.running && recording.output_file) {
      setSelectedFile(recording.output_file);
    }
    setActiveTab(id);
    localStorage.setItem("activeTab", id);
  }

  // Sync live file when output_file becomes known (e.g. after page reload with active recording)
  useEffect(() => {
    if (activeTab === "Live" && recording.running && recording.output_file) {
      setSelectedFile(recording.output_file);
    }
  }, [recording.output_file]);

  // If the stored tab is "Admin" but user is not admin, fall back to Viewer
  useEffect(() => {
    if (activeTab === "Admin" && !isAdmin) switchTab("Viewer");
  }, [isAdmin]);

  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("dark", theme === "dark");
    root.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
  }, [theme]);

  function handleSelect(filename) {
    setSelectedFile(filename);
    switchTab("Viewer");
  }

  function handleLive(filename) {
    setSelectedFile(filename);
    switchTab("Live");
  }

  async function handleStart(config) {
    const result = await start(config);
    if (result?.output_file) {
      setSelectedFile(result.output_file);
      switchTab("Live");
    }
  }

  async function handleStop() {
    await stop();
    refreshStatus();
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50 dark:bg-gray-900">
        <span className="text-gray-400 text-sm">Loading…</span>
      </div>
    );
  }

  if (!user) return <LoginPage />;

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-white dark:bg-gray-900">
      {/* ── Header ── */}
      <header className="flex items-center h-12 shrink-0 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 px-4 z-10">
        <span className="font-bold text-gray-900 dark:text-white mr-5 text-sm tracking-tight whitespace-nowrap">
          🎙 STT
        </span>

        <nav className="flex gap-1 flex-1">
          {TABS.map(({ id, label, icon }) => (
            <button
              key={id}
              onClick={() => switchTab(id)}
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

        <div className="flex items-center gap-3 ml-auto">
          {recording.running && (
            <span className="flex items-center gap-1.5 bg-red-500 text-white text-xs font-bold px-2.5 py-1 rounded-full animate-pulse">
              <span className="w-1.5 h-1.5 rounded-full bg-white" />
              REC
            </span>
          )}

          <button
            onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
            title="Toggle theme"
            className="p-1.5 rounded-md border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors text-sm"
          >
            {theme === "dark" ? "☀" : "🌙"}
          </button>

          {/* User info + logout */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500 dark:text-gray-400 hidden sm:block">
              {user.username}
              {isAdmin && (
                <span className="ml-1 px-1 py-0.5 text-[10px] bg-indigo-100 dark:bg-indigo-900 text-indigo-700 dark:text-indigo-300 rounded">
                  admin
                </span>
              )}
            </span>
            <button
              onClick={logout}
              title="Sign out"
              className="p-1.5 rounded-md border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors text-sm"
            >
              ⎋
            </button>
          </div>
        </div>
      </header>

      {/* ── Body ── */}
      <div className="flex flex-1 overflow-hidden">
        <aside className="w-64 shrink-0 border-r border-gray-200 dark:border-gray-700 flex flex-col overflow-hidden bg-gray-50 dark:bg-gray-800">
          <TranscriptList
            selected={selectedFile}
            onSelect={handleSelect}
            onLive={handleLive}
            liveFile={recording.output_file}
          />
        </aside>

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
          {activeTab === "Categories" && (
            <CategoriesManager />
          )}
          {activeTab === "Speakers" && (
            <SpeakersManager />
          )}
          {activeTab === "Settings" && (
            <ModelConfig />
          )}
          {activeTab === "Admin" && isAdmin && (
            <AdminPanel />
          )}
        </main>
      </div>
    </div>
  );
}

export default function App() {
  return <AppShell />;
}
