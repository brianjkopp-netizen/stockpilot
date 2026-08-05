import { useCallback, useEffect, useRef, useState } from "react";
import { RETRYING_EVENT } from "../api/client.js";

/**
 * Runs an async function and tracks { data, error, loading, retrying }
 * consistently. Pass `deps` to auto-run on mount/change, or call `run()`
 * manually (e.g. from a form submit) with the same arguments the task
 * function expects.
 *
 * `retrying` goes true while the client boundary is retrying a transient
 * failure (see api/client.js's RETRYING_EVENT) — screens use it to show a
 * waking-up state instead of the normal loading label.
 */
export function useAsync(task, deps = [], { immediate = true } = {}) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(immediate);
  const [retrying, setRetrying] = useState(false);
  const taskRef = useRef(task);
  taskRef.current = task;

  const run = useCallback(async (...args) => {
    setLoading(true);
    setError(null);
    setRetrying(false);
    const onRetry = () => setRetrying(true);
    window.addEventListener(RETRYING_EVENT, onRetry);
    try {
      const result = await taskRef.current(...args);
      setData(result);
      return result;
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      window.removeEventListener(RETRYING_EVENT, onRetry);
      setLoading(false);
      setRetrying(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (immediate) {
      // run() re-throws after setError so callers can await a manual run(); nothing
      // consumes that rejection here, so swallow it to avoid an unhandled rejection.
      run().catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, error, loading, retrying, run };
}
