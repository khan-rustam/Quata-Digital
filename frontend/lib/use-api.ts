"use client";

import * as React from "react";
import { api, type ApiOptions } from "./api";
import { useAuth } from "./auth";

export function useApi<T>(path: string | null, options: ApiOptions = {}) {
  const { token } = useAuth();
  const [data, setData] = React.useState<T | null>(null);
  const [error, setError] = React.useState<Error | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [refreshIndex, setRefreshIndex] = React.useState(0);

  React.useEffect(() => {
    if (!path) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- no path means nothing to fetch; settle the loading flag.
      setLoading(false);
      return;
    }
    let alive = true;
    setLoading(true);
    api<T>(path, { ...options, token: options.token ?? token ?? undefined })
      .then((d) => alive && setData(d))
      .catch((e) => alive && setError(e instanceof Error ? e : new Error(String(e))))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, token, refreshIndex]);

  return { data, error, loading, refresh: () => setRefreshIndex((i) => i + 1) };
}

export function useApiAction() {
  const { token } = useAuth();
  return React.useCallback(
    async <T,>(path: string, options: ApiOptions = {}) => {
      return api<T>(path, { ...options, token: options.token ?? token ?? undefined });
    },
    [token]
  );
}
