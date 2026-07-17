import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthContext } from "../contexts/AuthContext";
import LoginPage from "../pages/LoginPage";

function renderWithContext(overrides = {}) {
  const ctx = {
    user: null, loading: false, isAuthenticated: false, isAdmin: false,
    login:    vi.fn(),
    register: vi.fn(),
    logout:   vi.fn(),
    ...overrides,
  };
  const utils = render(
    <AuthContext.Provider value={ctx}><LoginPage /></AuthContext.Provider>
  );
  return { ctx, ...utils };
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("LoginPage — login mode (users exist)", () => {
  beforeEach(() => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true, json: async () => ({ needs_setup: false }),
    });
  });

  it("renders the sign-in form", async () => {
    renderWithContext();
    await waitFor(() => expect(screen.queryByText(/loading/i)).toBeNull());
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
  });

  it("calls login with username and password on submit", async () => {
    const login = vi.fn().mockResolvedValue({});
    const { container } = renderWithContext({ login });
    await waitFor(() => screen.getByRole("button", { name: /sign in/i }));

    fireEvent.change(container.querySelector('input[type="text"]'), { target: { value: "admin" } });
    fireEvent.change(container.querySelector('input[type="password"]'), { target: { value: "secret" } });
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => expect(login).toHaveBeenCalledWith("admin", "secret"));
  });

  it("shows error message on login failure", async () => {
    const login = vi.fn().mockRejectedValue(new Error("Incorrect username or password"));
    const { container } = renderWithContext({ login });
    await waitFor(() => screen.getByRole("button", { name: /sign in/i }));

    fireEvent.change(container.querySelector('input[type="text"]'), { target: { value: "x" } });
    fireEvent.change(container.querySelector('input[type="password"]'), { target: { value: "y" } });
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() =>
      expect(screen.getByText(/incorrect username or password/i)).toBeInTheDocument()
    );
  });
});

describe("LoginPage — first-run setup mode (no users)", () => {
  beforeEach(() => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true, json: async () => ({ needs_setup: true }),
    });
  });

  it("renders the create account form with email field", async () => {
    const { container } = renderWithContext();
    await waitFor(() => expect(screen.queryByText(/loading/i)).toBeNull());
    expect(screen.getByRole("button", { name: /create account/i })).toBeInTheDocument();
    expect(container.querySelector('input[type="email"]')).toBeInTheDocument();
  });

  it("calls register on submit without email", async () => {
    const register = vi.fn().mockResolvedValue({});
    const { container } = renderWithContext({ register });
    await waitFor(() => screen.getByRole("button", { name: /create account/i }));

    fireEvent.change(container.querySelector('input[type="text"]'), { target: { value: "admin" } });
    fireEvent.change(container.querySelector('input[type="password"]'), { target: { value: "Admin1!" } });
    // Leave email blank → register receives undefined
    fireEvent.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() => expect(register).toHaveBeenCalledWith("admin", "Admin1!", undefined));
  });
});
