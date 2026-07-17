import { useState, useEffect, useRef, useCallback } from "react";
import { apiFetch } from "../utils/api";

/**
 * Manages recording session: start, stop, and polls /api/recording/status
 * while a session is running.
 */
export function useRecording() {
  const [status, setStatus] = useState({
    running: false,
    output_file: null,
    pid: null,
  });
  const [error, setError] = useState(null);
  const pollRef = useRef(null);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await apiFetch("/api/recording/status");
      if (res.ok) setStatus(await res.json());
    } catch {
      // ignore network errors during polling
    }
  }, []);

  // Poll every 2 s while running
  useEffect(() => {
    if (status.running) {
      pollRef.current = setInterval(fetchStatus, 2000);
    } else {
      clearInterval(pollRef.current);
    }
    return () => clearInterval(pollRef.current);
  }, [status.running, fetchStatus]);

  // Initial status fetch
  useEffect(() => { fetchStatus(); }, [fetchStatus]);

  const start = useCallback(async (config) => {
    setError(null);
    try {
      const res = await apiFetch("/api/recording/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Failed to start");
      setStatus({ running: true, output_file: data.output_file, pid: data.pid });
      return data;
    } catch (err) {
      setError(err.message);
      throw err;
    }
  }, []);

  const stop = useCallback(async () => {
    setError(null);
    try {
      const res = await apiFetch("/api/recording/stop", { method: "POST" });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail ?? "Failed to stop");
      }
      setStatus((prev) => ({ ...prev, running: false }));
    } catch (err) {
      setError(err.message);
      throw err;
    }
  }, []);

  return { status, error, start, stop, refreshStatus: fetchStatus };
}
