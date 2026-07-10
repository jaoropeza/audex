import { useState, useCallback } from "react";

export function useModelConfig() {
  const [config, setConfig]       = useState(null);
  const [loading, setLoading]     = useState(false);
  const [saving, setSaving]       = useState(false);
  const [error, setError]         = useState(null);
  const [testResults, setTestResults] = useState({ stt: null, translation: null });
  const [testing, setTesting]     = useState({ stt: false, translation: false });

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/config");
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
      const res = await fetch("/api/config", {
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

  const test = useCallback(async (type) => {
    setTesting((t) => ({ ...t, [type]: true }));
    setTestResults((r) => ({ ...r, [type]: null }));
    try {
      const res = await fetch(`/api/config/test/${type}`, { method: "POST" });
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
