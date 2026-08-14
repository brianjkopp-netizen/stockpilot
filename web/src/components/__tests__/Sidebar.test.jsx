import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Sidebar from "../Sidebar.jsx";
import * as api from "../../api/client.js";

vi.mock("../../api/client.js");

function renderSidebar() {
  return render(
    <MemoryRouter>
      <Sidebar />
    </MemoryRouter>,
  );
}

describe("Sidebar identity block (SP-66)", () => {
  beforeEach(() => {
    vi.mocked(api.isViewer).mockReset();
  });

  it("full access shows the owner's identity", () => {
    vi.mocked(api.isViewer).mockReturnValue(false);

    renderSidebar();

    expect(screen.getByText("BK")).toBeInTheDocument();
    expect(screen.getByText("Brian Kopp")).toBeInTheDocument();
    expect(screen.getByText("Portfolio Manager")).toBeInTheDocument();
    expect(screen.queryByText("View-only access")).not.toBeInTheDocument();
  });

  it("viewer access shows a neutral guest identity instead of the owner's", () => {
    vi.mocked(api.isViewer).mockReturnValue(true);

    renderSidebar();

    expect(screen.queryByText("BK")).not.toBeInTheDocument();
    expect(screen.queryByText("Brian Kopp")).not.toBeInTheDocument();
    expect(screen.queryByText("Portfolio Manager")).not.toBeInTheDocument();

    expect(screen.getByText("Guest")).toBeInTheDocument();
    expect(screen.getByText("View only")).toBeInTheDocument();
    expect(screen.getByText("View-only access")).toBeInTheDocument();
  });
});
