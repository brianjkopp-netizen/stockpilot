import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
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

const stalePosition = {
  ticker: "AAPL",
  qty: 5,
  avg_entry_price: 180,
  mark_price: 181.0,
  mark_price_source: "alpaca",
  market_value: 905.0,
  unrealized_pl: 25.0,
  unrealized_plpc: 0.028,
  daily_pl: null,
  daily_plpc: null,
  sparkline: [],
  quote_stale: true,
};

const portfolioWithStalePosition = {
  positions: [stalePosition],
  totals: {
    market_value: 905.0,
    unrealized_pl: 25.0,
    unrealized_plpc: 0.028,
    daily_pl: 0,
    daily_plpc: 0,
    partial: true,
  },
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

  describe("stale quote handling (SP bug fix)", () => {
    beforeEach(() => {
      vi.mocked(api.getPortfolio).mockResolvedValue(portfolioWithStalePosition);
      vi.mocked(api.getRecommendation).mockRejectedValue({
        detail: "Recommendation unavailable",
        message: "Recommendation unavailable",
      });
    });

    it("labels the stale row's market price as Alpaca's own quote, not a live one (SP-63)", async () => {
      render(<PortfolioScreen />);

      // The Alpaca fallback price (real, from market_value/qty) is shown, visibly labeled —
      // never silently substituted for a live quote.
      expect(await screen.findByText("via Alpaca")).toBeInTheDocument();
      expect(screen.getByText("$181.00")).toBeInTheDocument();
      // The old SP-54 bug substituted avg_entry_price ($180) as a fake "Market" price — that
      // number must never appear anywhere outside its legitimate "Avg entry" column.
      expect(screen.getAllByText("$180.00")).toHaveLength(1);
      // Daily P&L still has no source to fall back to, so it stays explicitly unavailable.
      expect(screen.getByText("Quote unavailable")).toBeInTheDocument();
    });

    it("labels Value and Unrealized P&L as sharing the Market column's Alpaca source", async () => {
      render(<PortfolioScreen />);

      const row = (await screen.findByText("Quote stale")).closest("tr");
      const valueCell = within(row).getByText("$905.00").closest("td");
      const plCell = within(row).getByText("+$25.00").closest("td");
      expect(valueCell).toHaveAttribute("title", expect.stringContaining("Alpaca"));
      expect(plCell).toHaveAttribute("title", expect.stringContaining("Alpaca"));
    });

    it("marks the row as stale instead of showing daily P&L", async () => {
      render(<PortfolioScreen />);

      expect(await screen.findByText("Quote stale")).toBeInTheDocument();
    });

    it("marks the headline Today's P&L as incomplete rather than silently wrong", async () => {
      render(<PortfolioScreen />);

      expect(await screen.findByText(/Incomplete — quote unavailable for 1 position/)).toBeInTheDocument();
    });

    it("does not offer an Add/Close action against an unknown price", async () => {
      render(<PortfolioScreen />);

      await screen.findByText("Quote stale");
      expect(screen.queryByText("Add")).not.toBeInTheDocument();
      expect(screen.queryByText("Close")).not.toBeInTheDocument();
    });
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
