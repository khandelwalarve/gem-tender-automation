import { useEffect, useState, useCallback } from 'react';

const API_BASE = import.meta.env?.VITE_API_BASE || 'http://localhost:8000/api';

export function useApi(path, { auto = true, params = {} } = {}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(auto);
  const [error, setError] = useState(null);

  const query = Object.keys(params).length
    ? '?' + new URLSearchParams(params).toString()
    : '';

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}${path}${query}`);
      if (!res.ok) throw new Error(`Request failed: ${res.status}`);
      const json = await res.json();
      setData(json);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [path, query]);

  useEffect(() => {
    if (auto) fetchData();
  }, [auto, fetchData]);

  return { data, loading, error, refetch: fetchData };
}

export async function postJson(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Request failed: ${res.status}`);
  return res.json();
}
