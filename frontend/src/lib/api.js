import axios from "axios";
import { useCallback, useEffect, useRef, useState } from "react";

export const api = axios.create({ baseURL: `${process.env.REACT_APP_BACKEND_URL}/api` });

export const errMsg = (e) => {
  const d = e?.response?.data?.detail;
  if (Array.isArray(d)) return d.map((x) => x.msg).join("; ");
  return d || e?.message || "Request failed";
};

export const DISPOSITIONS = ["RPI_CONFIRMED", "WRONG_PARTY", "NO_ANSWER_VOICEMAIL", "FAILED_NUMBER"];

export const LANGUAGES = [
  { code: "en-US", label: "English (US)" },
  { code: "es-US", label: "Español (US)" },
  { code: "fr-CA", label: "Français (CA)" },
];

export const fmtTime = (iso) => (iso ? new Date(iso).toLocaleString() : "—");

export function usePoll(fetcher, interval = 0) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const ref = useRef(fetcher);
  const seq = useRef(0);
  ref.current = fetcher;
  const reload = useCallback(async () => {
    const id = ++seq.current;
    try {
      const result = await ref.current();
      if (id === seq.current) setData(result);
    } finally {
      if (id === seq.current) setLoading(false);
    }
  }, []);
  useEffect(() => {
    reload();
    if (!interval) return undefined;
    const t = setInterval(reload, interval);
    return () => clearInterval(t);
  }, [reload, interval]);
  return { data, loading, reload, setData };
}
