import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import DiscoverScreen from "../DiscoverScreen.jsx";
import * as api from "../../api/client.js";

vi.mock("../../api/client.js");

const mockScan = {
  scanned_at: "2026-07-22T12:00:00Z",
  total: 1,
  counts: { BULLISH: 1, BEARISH: 0, NEUTRAL: 0 },
  results: [
    {
      ticker: "AAPL",
      company_name: "Apple Inc.",
      signal: "BULLISH",
      confidence: "High",
      price: 200,
      drift_5d: 0.02,
      sparkline: [198, 199, 200],
    },
  ],
};

describe("DiscoverScreen render smoke tests", () => {
  beforeEach(() => {
    vi.mocked(api.getDiscover).mockReset();
  });

  it("renders the loading state without throwing", () => {
    vi.mocked(api.getDiscover).mockReturnValue(new Promise(() => {}));

    expect(() => render(<DiscoverScreen />)).not.toThrow();
    expect(screen.getByText(/Scanning your watchlist/)).toBeInTheDocument();
  });

  it("renders the error state without throwing", async () => {
    vi.mocked(api.getDiscover).mockRejectedValue({ message: "Could not reach the StockPilot API" });

    expect(() => render(<DiscoverScreen />)).not.toThrow();
    expect(await screen.findByText("Could not reach the StockPilot API")).toBeInTheDocument();
  });

  it("renders the loaded state without throwing", async () => {
    vi.mocked(api.getDiscover).mockResolvedValue(mockScan);

    expect(() => render(<DiscoverScreen />)).not.toThrow();
    expect(await screen.findByText("Apple Inc.")).toBeInTheDocument();
  });

  it("renders the empty state when the watchlist scan returns no results", async () => {
    vi.mocked(api.getDiscover).mockResolvedValue({
      scanned_at: "2026-07-22T12:00:00Z",
      total: 0,
      counts: { BULLISH: 0, BEARISH: 0, NEUTRAL: 0 },
      results: [],
    });

    render(<DiscoverScreen />);

    expect(await screen.findByText(/Your watchlist is empty/)).toBeInTheDocument();
  });
});

describe("DiscoverScreen order confirmation (SP-42)", () => {
  beforeEach(() => {
    vi.mocked(api.getDiscover).mockResolvedValue(mockScan);
    vi.mocked(api.placeOrder).mockResolvedValue({ placed: true, order: { id: "1" }, reason: null });
  });

  it("does not place an order on the button click alone", async () => {
    render(<DiscoverScreen />);
    const buyButton = await screen.findByText("Open paper buy");

    fireEvent.click(buyButton);

    expect(await screen.findByText("Confirm buy")).toBeInTheDocument();
    expect(api.placeOrder).not.toHaveBeenCalled();
  });

  it("places the order only after the confirmation is confirmed", async () => {
    render(<DiscoverScreen />);
    fireEvent.click(await screen.findByText("Open paper buy"));

    fireEvent.click(await screen.findByText("Confirm buy"));

    await waitFor(() => expect(api.placeOrder).toHaveBeenCalledTimes(1));
    expect(api.placeOrder).toHaveBeenCalledWith(
      expect.objectContaining({ ticker: "AAPL", side: "buy" }),
    );
  });

  it("places nothing when the confirmation is cancelled", async () => {
    render(<DiscoverScreen />);
    fireEvent.click(await screen.findByText("Open paper buy"));

    fireEvent.click(await screen.findByText("Cancel"));

    expect(api.placeOrder).not.toHaveBeenCalled();
    expect(screen.queryByText("Confirm buy")).not.toBeInTheDocument();
  });
});
