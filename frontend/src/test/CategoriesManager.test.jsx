import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CategoriesManager from "../components/CategoriesManager";

vi.mock("../utils/api", () => ({ apiFetch: vi.fn() }));
import { apiFetch } from "../utils/api";

function makeResponse(data, ok = true) {
  return Promise.resolve({ ok, status: ok ? 200 : 500, json: async () => data });
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("CategoriesManager — empty state", () => {
  it("shows empty-state message when no categories exist", async () => {
    apiFetch.mockReturnValue(makeResponse([]));
    render(<CategoriesManager />);
    await waitFor(() =>
      expect(screen.getByText(/no categories yet/i)).toBeInTheDocument()
    );
  });
});

describe("CategoriesManager — with categories", () => {
  const cats = [
    { id: 1, name: "Work",     color: "#3b82f6", description: "",   created_at: "2024-01-01T00:00:00" },
    { id: 2, name: "Personal", color: "#f59e0b", description: null, created_at: "2024-01-02T00:00:00" },
  ];

  it("renders category names", async () => {
    apiFetch.mockReturnValue(makeResponse(cats));
    render(<CategoriesManager />);
    await waitFor(() => expect(screen.getByText("Work")).toBeInTheDocument());
    expect(screen.getByText("Personal")).toBeInTheDocument();
  });
});

describe("CategoriesManager — create flow", () => {
  it("submits new category and refreshes the list", async () => {
    const newCat = { id: 3, name: "New Cat", color: "#6366f1", description: "", created_at: "2024-01-03T00:00:00" };

    apiFetch
      .mockReturnValueOnce(makeResponse([]))        // initial load
      .mockReturnValueOnce(makeResponse(newCat))    // POST
      .mockReturnValueOnce(makeResponse([newCat])); // reload after save

    render(<CategoriesManager />);
    // Wait for the "+ New category" button to appear
    await waitFor(() => screen.getByRole("button", { name: /new category/i }));
    fireEvent.click(screen.getByRole("button", { name: /new category/i }));

    // Form opens; name input has placeholder "Meetings"
    const nameInput = await screen.findByPlaceholderText("Meetings");
    fireEvent.change(nameInput, { target: { value: "New Cat" } });

    // Save button (not "Create")
    fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

    await waitFor(() => expect(apiFetch).toHaveBeenCalledWith(
      "/api/categories",
      expect.objectContaining({ method: "POST" })
    ));
  });
});

describe("CategoriesManager — delete flow", () => {
  it("calls DELETE when delete button is clicked", async () => {
    const cats = [
      { id: 1, name: "ToDelete", color: "#f00", description: "", created_at: "2024-01-01T00:00:00" },
    ];

    global.confirm = vi.fn(() => true);
    apiFetch.mockImplementation((url, opts) => {
      if (opts?.method === "DELETE") return makeResponse({ deleted: "ToDelete" });
      return makeResponse(cats);
    });

    render(<CategoriesManager />);
    await waitFor(() => screen.getByText("ToDelete"));

    // Delete button may have opacity-0 but is still in the DOM
    const deleteBtn = screen.getByRole("button", { name: "Delete" });
    fireEvent.click(deleteBtn);

    await waitFor(() => expect(apiFetch).toHaveBeenCalledWith(
      "/api/categories/1",
      expect.objectContaining({ method: "DELETE" })
    ));
  });
});
