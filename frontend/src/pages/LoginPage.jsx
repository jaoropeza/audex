import { useState, useEffect } from "react";
import { useAuthContext } from "../contexts/AuthContext";

export default function LoginPage() {
  const { login, register } = useAuthContext();

  const [needsSetup, setNeedsSetup] = useState(null); // null = loading
  const [username,   setUsername]   = useState("");
  const [password,   setPassword]   = useState("");
  const [email,      setEmail]      = useState("");
  const [error,      setError]      = useState(null);
  const [busy,       setBusy]       = useState(false);

  useEffect(() => {
    fetch("/api/auth/bootstrap-status")
      .then((r) => r.json())
      .then((d) => setNeedsSetup(d.needs_setup))
      .catch(() => setNeedsSetup(false));
  }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (needsSetup) {
        await register(username, password, email || undefined);
      } else {
        await login(username, password);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  if (needsSetup === null) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50 dark:bg-gray-900">
        <span className="text-gray-400 text-sm">Loading…</span>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center h-screen bg-gray-50 dark:bg-gray-900">
      <div className="w-full max-w-sm bg-white dark:bg-gray-800 rounded-xl shadow-lg p-8">
        {/* Logo */}
        <div className="text-center mb-6">
          <span className="text-3xl">🎙</span>
          <h1 className="mt-2 text-xl font-bold text-gray-900 dark:text-white">STT</h1>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            {needsSetup ? "Create your admin account" : "Sign in to continue"}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-300 mb-1">
              Username
            </label>
            <input
              type="text"
              required
              autoFocus
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-3 py-2 text-sm rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          {needsSetup && (
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-300 mb-1">
                Email (optional)
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          )}

          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-300 mb-1">
              Password
            </label>
            <input
              type="password"
              required
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 text-sm rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          {error && (
            <p className="text-xs text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 rounded-md px-3 py-2">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={busy}
            className="w-full py-2 px-4 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 rounded-md transition-colors"
          >
            {busy ? "Please wait…" : needsSetup ? "Create account" : "Sign in"}
          </button>
        </form>

        {needsSetup && (
          <p className="mt-4 text-xs text-center text-gray-400 dark:text-gray-500">
            This is the first-run setup. The account you create will be the admin.
          </p>
        )}
      </div>
    </div>
  );
}
