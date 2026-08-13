import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, act, waitFor } from "@testing-library/react";
import PasswordGate from "../PasswordGate.jsx";
import * as api from "../../api/client.js";

vi.mock("../../api/client.js");

describe("PasswordGate", () => {
  beforeEach(() => {
    vi.mocked(api.hasPassword).mockReset();
    vi.mocked(api.setPassword).mockReset();
    vi.mocked(api.setRole).mockReset();
    vi.mocked(api.whoAmI).mockReset().mockResolvedValue({ role: "full" });
    api.PASSPHRASE_REJECTED_EVENT = "stockpilot:passphrase-rejected";
  });

  it("renders only the passphrase form when no passphrase is stored", () => {
    vi.mocked(api.hasPassword).mockReturnValue(false);

    render(
      <PasswordGate>
        <div>secret app content</div>
      </PasswordGate>,
    );

    expect(screen.getByPlaceholderText(/enter passphrase/i)).toBeInTheDocument();
    expect(screen.queryByText("secret app content")).not.toBeInTheDocument();
  });

  it("renders children directly when a passphrase is already stored", () => {
    vi.mocked(api.hasPassword).mockReturnValue(true);

    render(
      <PasswordGate>
        <div>secret app content</div>
      </PasswordGate>,
    );

    expect(screen.getByText("secret app content")).toBeInTheDocument();
    expect(screen.queryByPlaceholderText(/enter passphrase/i)).not.toBeInTheDocument();
  });

  it("submitting the form stores the passphrase, resolves the role, and reveals the children", async () => {
    vi.mocked(api.hasPassword).mockReturnValue(false);
    vi.mocked(api.whoAmI).mockResolvedValue({ role: "full" });

    render(
      <PasswordGate>
        <div>secret app content</div>
      </PasswordGate>,
    );

    fireEvent.change(screen.getByPlaceholderText(/enter passphrase/i), {
      target: { value: "letmein" },
    });
    fireEvent.click(screen.getByRole("button", { name: /enter/i }));

    expect(api.setPassword).toHaveBeenCalledWith("letmein");
    await waitFor(() => expect(screen.getByText("secret app content")).toBeInTheDocument());
    expect(api.setRole).toHaveBeenCalledWith("full");
  });

  it("submitting a viewer passphrase stores the viewer role and reveals the children", async () => {
    vi.mocked(api.hasPassword).mockReturnValue(false);
    vi.mocked(api.whoAmI).mockResolvedValue({ role: "viewer" });

    render(
      <PasswordGate>
        <div>secret app content</div>
      </PasswordGate>,
    );

    fireEvent.change(screen.getByPlaceholderText(/enter passphrase/i), {
      target: { value: "lookonly" },
    });
    fireEvent.click(screen.getByRole("button", { name: /enter/i }));

    await waitFor(() => expect(screen.getByText("secret app content")).toBeInTheDocument());
    expect(api.setRole).toHaveBeenCalledWith("viewer");
  });

  it("does not unlock when whoAmI rejects (e.g. a bad passphrase)", async () => {
    vi.mocked(api.hasPassword).mockReturnValue(false);
    vi.mocked(api.whoAmI).mockRejectedValue(new Error("rejected"));

    render(
      <PasswordGate>
        <div>secret app content</div>
      </PasswordGate>,
    );

    fireEvent.change(screen.getByPlaceholderText(/enter passphrase/i), {
      target: { value: "wrong" },
    });
    fireEvent.click(screen.getByRole("button", { name: /enter/i }));

    await waitFor(() => expect(screen.getByRole("button", { name: /enter/i })).toBeInTheDocument());
    expect(screen.queryByText("secret app content")).not.toBeInTheDocument();
  });

  it("re-locks and shows a rejection message when the API fires a 401 event", () => {
    vi.mocked(api.hasPassword).mockReturnValue(true);

    render(
      <PasswordGate>
        <div>secret app content</div>
      </PasswordGate>,
    );

    expect(screen.getByText("secret app content")).toBeInTheDocument();

    act(() => {
      window.dispatchEvent(new Event(api.PASSPHRASE_REJECTED_EVENT));
    });

    expect(screen.queryByText("secret app content")).not.toBeInTheDocument();
    expect(screen.getByText(/rejected/i)).toBeInTheDocument();
  });
});
