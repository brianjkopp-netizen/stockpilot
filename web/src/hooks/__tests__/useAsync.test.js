import { describe, it, expect, vi } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { useAsync } from "../useAsync.js";

function deferred() {
  let resolve, reject;
  const promise = new Promise((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe("useAsync", () => {
  it("is loading while the task is in flight, then populates data", async () => {
    const { promise, resolve } = deferred();
    const task = vi.fn(() => promise);

    const { result } = renderHook(() => useAsync(task, []));

    expect(result.current.loading).toBe(true);
    expect(result.current.data).toBeNull();

    resolve({ value: 42 });
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.data).toEqual({ value: 42 });
    expect(result.current.error).toBeNull();
  });

  it("populates error on failure and clears loading", async () => {
    const failure = new Error("boom");
    const task = vi.fn(() => Promise.reject(failure));

    const { result } = renderHook(() => useAsync(task, []));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe(failure);
    expect(result.current.data).toBeNull();
  });

  it("re-executes the task when run() is called manually", async () => {
    const task = vi.fn().mockResolvedValueOnce("first").mockResolvedValueOnce("second");

    const { result } = renderHook(() => useAsync(task, []));

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toBe("first");
    expect(task).toHaveBeenCalledTimes(1);

    await act(async () => {
      await result.current.run();
    });

    expect(result.current.data).toBe("second");
    expect(task).toHaveBeenCalledTimes(2);
  });

  it("does not run automatically when immediate is false", () => {
    const task = vi.fn().mockResolvedValue("value");

    const { result } = renderHook(() => useAsync(task, [], { immediate: false }));

    expect(result.current.loading).toBe(false);
    expect(task).not.toHaveBeenCalled();
  });
});
