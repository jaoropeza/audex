import { useState, useCallback } from "react";
import { apiFetch } from "../utils/api";

export function useModelConfig() {
  const [config, setConfig]       = useState(null);
  const [loading, setLoading]     = useState(false);
  const [saving, setSaving]       = useState(false);
  const [error, setError]         = useState(null);
  const [testResults, setTestResults] = useState({ stt: null, translation: null, summary: null });
  const [testing, setTesting]     = useState({ stt: false, translation: false, summary: false });

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch("/api/config");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setConfig(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const save = useCallback(async (newConfig) => {
    setSaving(true);
    setError(null);
    try {
      const res = await apiFetch("/api/config", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newConfig),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setConfig(data);
      return { ok: true };
    } catch (e) {
      setError(e.message);
      return { ok: false, error: e.message };
    } finally {
      setSaving(false);
    }
  }, []);

  // draftConfig: the full draft AppSettings object from the UI (may differ from saved config)
  const test = useCallback(async (type, draftConfig) => {
    setTesting((t) => ({ ...t, [type]: true }));
    setTestResults((r) => ({ ...r, [type]: null }));
    try {
      const section = draftConfig?.[type]; // "stt", "translation", or "summary"
      const res = await apiFetch(`/api/config/test/${type}`, {
        method: "POST",
        headers: section ? { "Content-Type": "application/json" } : {},
        body:    section ? JSON.stringify(section) : undefined,
      });
      const data = await res.json();
      setTestResults((r) => ({ ...r, [type]: data }));
    } catch (e) {
      setTestResults((r) => ({ ...r, [type]: { ok: false, detail: e.message } }));
    } finally {
      setTesting((t) => ({ ...t, [type]: false }));
    }
  }, []);

  return { config, loading, saving, error, testResults, testing, load, save, test };
}
