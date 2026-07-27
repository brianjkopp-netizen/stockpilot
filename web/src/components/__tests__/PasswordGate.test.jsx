import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import PasswordGate from "../PasswordGate.jsx";
import * as api from "../../api/client.js";

vi.mock("../../api/client.js");

describe("PasswordGate", () => {
  beforeEach(() => {
    vi.mocked(api.hasPassword).mockReset();
    vi.mocked(api.setPassword).mockReset();
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

  it("submitting the form stores the passphrase and reveals the children", () => {
    vi.mocked(api.hasPassword).mockReturnValue(false);

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
    expect(screen.getByText("secret app content")).toBeInTheDocument();
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
