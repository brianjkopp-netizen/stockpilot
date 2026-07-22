import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import PortfolioScreen from "../PortfolioScreen.jsx";
import * as api from "../../api/client.js";

vi.mock("../../api/client.js");

const emptyPortfolio = {
  positions: [],
  totals: { market_value: 0, unrealized_pl: 0, unrealized_plpc: 0, daily_pl: 0, daily_plpc: 0 },
  account: { cash: 100000, portfolio_value: 100000 },
};

const onePosition = {
  ticker: "AAPL",
  qty: 5,
  avg_entry_price: 180,
  mark_price: 200,
  market_value: 1000,
  unrealized_pl: 100,
  unrealized_plpc: 0.1,
  daily_pl: 10,
  daily_plpc: 0.01,
  sparkline: [190, 195, 200],
};

const portfolioWithPosition = {
  positions: [onePosition],
  totals: { market_value: 1000, unrealized_pl: 100, unrealized_plpc: 0.1, daily_pl: 10, daily_plpc: 0.01 },
  account: { cash: 99000, portfolio_value: 100000 },
};

describe("PortfolioScreen", () => {
  beforeEach(() => {
    vi.mocked(api.getPortfolio).mockReset();
    vi.mocked(api.getRecommendation)?.mockReset?.();
    vi.mocked(api.placeOrder)?.mockReset?.();
  });

  it("renders the loading state without throwing", () => {
    vi.mocked(api.getPortfolio).mockReturnValue(new Promise(() => {}));

    expect(() => render(<PortfolioScreen />)).not.toThrow();
    expect(screen.getByText(/Loading portfolio/)).toBeInTheDocument();
  });

  it("renders the error state without throwing", async () => {
    vi.mocked(api.getPortfolio).mockRejectedValue({ message: "Could not reach the StockPilot API" });

    expect(() => render(<PortfolioScreen />)).not.toThrow();
    expect(await screen.findByText("Could not reach the StockPilot API")).toBeInTheDocument();
  });

  it("renders the loaded state without throwing", async () => {
    vi.mocked(api.getPortfolio).mockResolvedValue(portfolioWithPosition);
    vi.mocked(api.getRecommendation).mockResolvedValue({
      ticker: "AAPL",
      verdict: "HOLD",
      confidence: "High",
      brief: "Steady as she goes.",
    });

    expect(() => render(<PortfolioScreen />)).not.toThrow();
    expect(await screen.findByText("Steady as she goes.")).toBeInTheDocument();
  });

  it("renders the empty state when there are no open positions", async () => {
    vi.mocked(api.getPortfolio).mockResolvedValue(emptyPortfolio);

    render(<PortfolioScreen />);

    expect(await screen.findByText(/No open positions yet/)).toBeInTheDocument();
  });

  describe("order confirmation gating (SP-42)", () => {
    beforeEach(() => {
      vi.mocked(api.getPortfolio).mockResolvedValue(portfolioWithPosition);
      vi.mocked(api.getRecommendation).mockResolvedValue({
        ticker: "AAPL",
        verdict: "ADD",
        confidence: "High",
        brief: "Momentum still building.",
      });
      vi.mocked(api.placeOrder).mockResolvedValue({ placed: true, order: { id: "1" }, reason: null });
    });

    it("does not place an order on the Add click alone", async () => {
      render(<PortfolioScreen />);

      fireEvent.click(await screen.findByText("Add"));

      expect(await screen.findByText("Confirm buy")).toBeInTheDocument();
      expect(api.placeOrder).not.toHaveBeenCalled();
    });

    it("places the order only after confirmation", async () => {
      render(<PortfolioScreen />);

      fireEvent.click(await screen.findByText("Add"));
      fireEvent.click(await screen.findByText("Confirm buy"));

      await waitFor(() => expect(api.placeOrder).toHaveBeenCalledTimes(1));
      expect(api.placeOrder).toHaveBeenCalledWith(
        expect.objectContaining({ ticker: "AAPL", side: "buy" }),
      );
    });

    it("places nothing when the confirmation is cancelled", async () => {
      render(<PortfolioScreen />);

      fireEvent.click(await screen.findByText("Add"));
      fireEvent.click(await screen.findByText("Cancel"));

      expect(api.placeOrder).not.toHaveBeenCalled();
      expect(screen.queryByText("Confirm buy")).not.toBeInTheDocument();
    });
  });
});
