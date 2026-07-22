import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { getSignal, ApiError } from "../client.js";

describe("api client", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("parses a successful JSON response", async () => {
    fetch.mockResolvedValue({
      ok: true,
      json: async () => ({ ticker: "AAPL", signal: "BULLISH" }),
    });

    const result = await getSignal("AAPL");

    expect(result).toEqual({ ticker: "AAPL", signal: "BULLISH" });
  });

  it("surfaces the detail message from a non-OK response", async () => {
    fetch.mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({ detail: "Unknown ticker: ZZZZ" }),
    });

    await expect(getSignal("ZZZZ")).rejects.toMatchObject({
      name: "ApiError",
      status: 404,
      detail: "Unknown ticker: ZZZZ",
      message: "Unknown ticker: ZZZZ",
    });
  });

  it("falls back to a generic message when a non-OK response has no JSON body", async () => {
    fetch.mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => {
        throw new Error("not JSON");
      },
    });

    await expect(getSignal("AAPL")).rejects.toBeInstanceOf(ApiError);
    await expect(getSignal("AAPL")).rejects.toMatchObject({
      status: 500,
      detail: null,
    });
  });

  it("produces a status: 0 ApiError when the network request fails", async () => {
    fetch.mockRejectedValue(new TypeError("Failed to fetch"));

    await expect(getSignal("AAPL")).rejects.toMatchObject({
      name: "ApiError",
      status: 0,
      message: expect.stringContaining("Could not reach the StockPilot API"),
    });
  });
});
