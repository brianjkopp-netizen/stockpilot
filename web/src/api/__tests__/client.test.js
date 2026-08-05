import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  getSignal,
  ApiError,
  setPassword,
  hasPassword,
  PASSPHRASE_REJECTED_EVENT,
  RETRYING_EVENT,
} from "../client.js";

function jsonResponse(status, body) {
  return { ok: status >= 200 && status < 300, status, json: async () => body };
}

describe("api client", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
    localStorage.clear();
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

  it("attaches the stored passphrase as X-App-Password on every request", async () => {
    setPassword("letmein");
    fetch.mockResolvedValue({ ok: true, json: async () => ({}) });

    await getSignal("AAPL");

    const [, options] = fetch.mock.calls[0];
    expect(options.headers["X-App-Password"]).toBe("letmein");
  });

  it("omits the header entirely when no passphrase is stored", async () => {
    fetch.mockResolvedValue({ ok: true, json: async () => ({}) });

    await getSignal("AAPL");

    const [, options] = fetch.mock.calls[0];
    expect(options.headers["X-App-Password"]).toBeUndefined();
  });

  it("on a 401, clears the stored passphrase and surfaces a distinct rejection error", async () => {
    setPassword("letmein");
    fetch.mockResolvedValue({ ok: false, status: 401, json: async () => ({}) });

    await expect(getSignal("AAPL")).rejects.toMatchObject({
      name: "ApiError",
      status: 401,
      message: "That passphrase was rejected.",
    });
    expect(hasPassword()).toBe(false);
  });

  it("dispatches PASSPHRASE_REJECTED_EVENT on window when a request comes back 401", async () => {
    setPassword("letmein");
    fetch.mockResolvedValue({ ok: false, status: 401, json: async () => ({}) });
    const handler = vi.fn();
    window.addEventListener(PASSPHRASE_REJECTED_EVENT, handler);

    await getSignal("AAPL").catch(() => {});

    expect(handler).toHaveBeenCalledTimes(1);
    window.removeEventListener(PASSPHRASE_REJECTED_EVENT, handler);
  });

  it("applies an explicit timeout via AbortController rather than the browser default", async () => {
    fetch.mockResolvedValue(jsonResponse(200, {}));

    await getSignal("AAPL");

    const [, options] = fetch.mock.calls[0];
    expect(options.signal).toBeInstanceOf(AbortSignal);
  });

  describe("retry and backoff", () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it("retries a 503 and succeeds once the server wakes up", async () => {
      fetch
        .mockResolvedValueOnce(jsonResponse(503, { detail: "Upstream data provider unavailable" }))
        .mockResolvedValueOnce(jsonResponse(200, { ticker: "AAPL" }));

      const promise = getSignal("AAPL");
      await vi.advanceTimersByTimeAsync(2000);

      await expect(promise).resolves.toEqual({ ticker: "AAPL" });
      expect(fetch).toHaveBeenCalledTimes(2);
    });

    it.each([502, 503, 504])("retries a %i the same way it retries a network error", async (status) => {
      fetch
        .mockResolvedValueOnce(jsonResponse(status, { detail: "bad gateway" }))
        .mockResolvedValueOnce(jsonResponse(200, { ticker: "AAPL" }));

      const promise = getSignal("AAPL");
      await vi.advanceTimersByTimeAsync(2000);

      await expect(promise).resolves.toEqual({ ticker: "AAPL" });
      expect(fetch).toHaveBeenCalledTimes(2);
    });

    it("retries a network error and succeeds on the next attempt", async () => {
      fetch.mockRejectedValueOnce(new TypeError("Failed to fetch")).mockResolvedValueOnce(jsonResponse(200, { ticker: "AAPL" }));

      const promise = getSignal("AAPL");
      await vi.advanceTimersByTimeAsync(2000);

      await expect(promise).resolves.toEqual({ ticker: "AAPL" });
      expect(fetch).toHaveBeenCalledTimes(2);
    });

    it("backs off between attempts instead of retrying immediately", async () => {
      fetch
        .mockResolvedValueOnce(jsonResponse(503, {}))
        .mockResolvedValueOnce(jsonResponse(200, { ticker: "AAPL" }));

      const promise = getSignal("AAPL");
      promise.catch(() => {});

      // Right after the first failure, no backoff time has passed yet.
      await vi.advanceTimersByTimeAsync(0);
      expect(fetch).toHaveBeenCalledTimes(1);

      await vi.advanceTimersByTimeAsync(2000);
      await expect(promise).resolves.toEqual({ ticker: "AAPL" });
    });

    it("dispatches RETRYING_EVENT before each retry with an increasing attempt count", async () => {
      const handler = vi.fn();
      window.addEventListener(RETRYING_EVENT, handler);

      fetch
        .mockResolvedValueOnce(jsonResponse(503, {}))
        .mockResolvedValueOnce(jsonResponse(503, {}))
        .mockResolvedValueOnce(jsonResponse(200, { ticker: "AAPL" }));

      const promise = getSignal("AAPL");
      await vi.advanceTimersByTimeAsync(10000);
      await promise;

      expect(handler).toHaveBeenCalledTimes(2);
      expect(handler.mock.calls[0][0].detail).toMatchObject({ attempt: 1 });
      expect(handler.mock.calls[1][0].detail).toMatchObject({ attempt: 2 });

      window.removeEventListener(RETRYING_EVENT, handler);
    });

    it("gives up after a small bounded number of attempts", async () => {
      fetch.mockResolvedValue(jsonResponse(503, { detail: "Upstream data provider unavailable" }));

      const promise = getSignal("AAPL");
      promise.catch(() => {});
      await vi.advanceTimersByTimeAsync(60000);

      await expect(promise).rejects.toMatchObject({ status: 503 });
      expect(fetch.mock.calls.length).toBeLessThanOrEqual(6);
      expect(fetch.mock.calls.length).toBeGreaterThan(1);
    });

    it.each([401, 422, 429])("does not retry a %i — terminal by design", async (status) => {
      fetch.mockResolvedValue(jsonResponse(status, { detail: "terminal" }));
      const handler = vi.fn();
      window.addEventListener(RETRYING_EVENT, handler);

      await expect(getSignal("AAPL")).rejects.toMatchObject({ status });

      expect(fetch).toHaveBeenCalledTimes(1);
      expect(handler).not.toHaveBeenCalled();
      window.removeEventListener(RETRYING_EVENT, handler);
    });

    it("treats a timed-out request as retryable", async () => {
      // First attempt never settles until the timeout fires and aborts it;
      // the second attempt succeeds immediately.
      fetch.mockImplementationOnce(
        (url, { signal }) =>
          new Promise((resolve, reject) => {
            signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
          }),
      );
      fetch.mockResolvedValueOnce(jsonResponse(200, { ticker: "AAPL" }));

      const promise = getSignal("AAPL");
      await vi.advanceTimersByTimeAsync(15000);

      await expect(promise).resolves.toEqual({ ticker: "AAPL" });
      expect(fetch).toHaveBeenCalledTimes(2);
    });
  });
});
