"use client";

import { useCallback, useEffect, useRef, useState } from "react";

interface UsePollingOptions<T> {
  onDone?: (data: T) => void;
  onError?: (error: string) => void;
  shouldStop?: (data: T) => boolean;
}

export function usePolling<T>(
  fetcher: (() => Promise<T>) | null,
  intervalMs: number,
  options?: UsePollingOptions<T>
) {
  const [data, setData] = useState<T | null>(null);
  const [isPolling, setIsPolling] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const stoppedRef = useRef(false);

  const stop = useCallback(() => {
    stoppedRef.current = true;
    setIsPolling(false);
    if (timerRef.current) clearTimeout(timerRef.current);
  }, []);

  useEffect(() => {
    if (!fetcher) {
      stop();
      return;
    }

    stoppedRef.current = false;
    setIsPolling(true);

    const poll = async () => {
      if (stoppedRef.current) return;
      try {
        const result = await fetcher();
        if (stoppedRef.current) return;
        setData(result);

        const shouldStop = options?.shouldStop?.(result);
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const state = (result as any)?.state;

        if (shouldStop || state === "done") {
          options?.onDone?.(result);
          stop();
          return;
        }
        if (state === "error") {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          options?.onError?.((result as any)?.error ?? "Unknown error");
          stop();
          return;
        }

        timerRef.current = setTimeout(poll, intervalMs);
      } catch (err) {
        if (stoppedRef.current) return;
        options?.onError?.(String(err));
        stop();
      }
    };

    poll();
    return stop;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetcher, intervalMs]);

  return { data, isPolling, stop };
}
