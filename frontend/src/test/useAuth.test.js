import { renderHook, act, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useAuth } from "../hooks/useAuth";

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe("useAuth — initial state", () => {
  it("starts unauthenticated when no token in storage", async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 401, json: async () => ({}) });
    const { result } = renderHook(() => useAuth());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.user).toBeNull();
  });

  it("restores session when stored token is valid", async () => {
    localStorage.setItem("stt_token", "valid-token");
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ id: 1, username: "admin", role: "admin", is_active: true }),
    });
    const { result } = renderHook(() => useAuth());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.user?.username).toBe("admin");
  });
});

describe("useAuth — login", () => {
  it("sets token and user on successful login", async () => {
    // No token in storage → mount effect skips /api/auth/me → only the login call reaches fetch
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        access_token: "tok123",
        user: { id: 1, username: "alice", role: "user", is_active: true },
      }),
    });

    const { result } = renderHook(() => useAuth());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.login("alice", "pass");
    });

    expect(localStorage.getItem("stt_token")).toBe("tok123");
    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.user?.username).toBe("alice");
  });

  it("throws on failed login", async () => {
    // No token → mount skips /api/auth/me → only the login call
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: async () => ({ detail: "Incorrect username or password" }),
    });

    const { result } = renderHook(() => useAuth());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await expect(
      act(async () => { await result.current.login("alice", "wrong"); })
    ).rejects.toThrow("Incorrect username or password");
  });
});

describe("useAuth — logout", () => {
  it("clears token and user", async () => {
    localStorage.setItem("stt_token", "tok");
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 1, username: "alice", role: "user" }),
    });

    const { result } = renderHook(() => useAuth());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.isAuthenticated).toBe(true);

    act(() => { result.current.logout(); });
    expect(localStorage.getItem("stt_token")).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
  });
});

describe("useAuth — isAdmin", () => {
  it("is false for regular user", async () => {
    localStorage.setItem("stt_token", "tok");
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 2, username: "bob", role: "user" }),
    });
    const { result } = renderHook(() => useAuth());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.isAdmin).toBe(false);
  });

  it("is true for admin", async () => {
    localStorage.setItem("stt_token", "tok");
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 1, username: "admin", role: "admin" }),
    });
    const { result } = renderHook(() => useAuth());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.isAdmin).toBe(true);
  });
});
