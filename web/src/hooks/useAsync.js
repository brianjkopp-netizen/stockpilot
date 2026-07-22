import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Runs an async function and tracks { data, error, loading } consistently.
 * Pass `deps` to auto-run on mount/change, or call `run()` manually (e.g. from
 * a form submit) with the same arguments the task function expects.
 */
export function useAsync(task, deps = [], { immediate = true } = {}) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(immediate);
  const taskRef = useRef(task);
  taskRef.current = task;

  const run = useCallback(async (...args) => {
    setLoading(true);
    setError(null);
    try {
      const result = await taskRef.current(...args);
      setData(result);
      return result;
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setLoading(false);
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

  return { data, error, loading, run };
}
