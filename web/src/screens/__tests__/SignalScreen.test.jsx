import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import SignalScreen from "../SignalScreen.jsx";
import * as api from "../../api/client.js";

vi.mock("../../api/client.js");

const mockResult = {
  ticker: "AAPL",
  signal: "BULLISH",
  confidence: "High",
  price: 200,
  ma_10: 195,
  ma_20: 190,
  volume_signal: "ABOVE AVERAGE",
  reasoning: "Price is trending above both moving averages.",
  key_factors: ["Strong volume", "Upward momentum"],
};

describe("SignalScreen", () => {
  beforeEach(() => {
    vi.mocked(api.getSignal).mockReset();
  });

  it("renders the loading state without throwing", () => {
    vi.mocked(api.getSignal).mockReturnValue(new Promise(() => {}));

    expect(() => render(<SignalScreen />)).not.toThrow();
    expect(screen.getByText(/Analyzing AAPL/)).toBeInTheDocument();
  });

  it("renders the error state without throwing", async () => {
    vi.mocked(api.getSignal).mockRejectedValue({ message: "Unknown ticker: AAPL" });

    expect(() => render(<SignalScreen />)).not.toThrow();
    expect(await screen.findByText("Unknown ticker: AAPL")).toBeInTheDocument();
  });

  it("renders the loaded state without throwing", async () => {
    vi.mocked(api.getSignal).mockResolvedValue(mockResult);

    expect(() => render(<SignalScreen />)).not.toThrow();
    expect(await screen.findByText("Strong volume")).toBeInTheDocument();
  });
});
