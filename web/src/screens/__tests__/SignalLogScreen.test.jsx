import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import SignalLogScreen from "../SignalLogScreen.jsx";
import * as api from "../../api/client.js";

vi.mock("../../api/client.js");

const mockLog = {
  records: [
    {
      timestamp: "2026-07-22T12:00:00Z",
      ticker: "AAPL",
      signal: "BULLISH",
      confidence: "High",
      price: 200,
      reasoning: "Trending above moving averages.",
    },
  ],
};

describe("SignalLogScreen", () => {
  beforeEach(() => {
    vi.mocked(api.getSignals).mockReset();
  });

  it("renders the loading state without throwing", () => {
    vi.mocked(api.getSignals).mockReturnValue(new Promise(() => {}));

    expect(() => render(<SignalLogScreen />)).not.toThrow();
    expect(screen.getByText(/Loading signal history/)).toBeInTheDocument();
  });

  it("renders the error state without throwing", async () => {
    vi.mocked(api.getSignals).mockRejectedValue({ message: "Could not reach the StockPilot API" });

    expect(() => render(<SignalLogScreen />)).not.toThrow();
    expect(await screen.findByText("Could not reach the StockPilot API")).toBeInTheDocument();
  });

  it("renders the loaded state without throwing", async () => {
    vi.mocked(api.getSignals).mockResolvedValue(mockLog);

    expect(() => render(<SignalLogScreen />)).not.toThrow();
    expect(await screen.findByText("Trending above moving averages.")).toBeInTheDocument();
  });

  it("renders the empty state when there are no logged signals", async () => {
    vi.mocked(api.getSignals).mockResolvedValue({ records: [] });

    render(<SignalLogScreen />);

    expect(await screen.findByText("No signals match the current filter.")).toBeInTheDocument();
  });
});
