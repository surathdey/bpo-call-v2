import axios from "axios";
import { useCallback, useEffect, useRef, useState } from "react";

export const api = axios.create({ baseURL: `${process.env.REACT_APP_BACKEND_URL}/api` });

export const errMsg = (e) => {
  const d = e?.response?.data?.detail;
  if (Array.isArray(d)) return d.map((x) => x.msg).join("; ");
  return d || e?.message || "Request failed";
};

export const DISPOSITIONS = ["RPC_CONFIRMED", "CPC_CONFIRMED", "CALLBACK_REQUESTED", "FINAL_DENIAL",
  "FINAL_DENIAL_CLOSING", "HOSTILE", "DECEASED_CASE", "DNC_ESCALATION"];

export const LANGUAGES = [
  { code: "en-IN", label: "English" },
  { code: "bn-IN", label: "Bengali" },
  { code: "hi-IN", label: "Hindi" },
];

export const SCRIPT_KEYS = ["opening", "clarify", "reverify", "confirmed_close", "cpc_close", "callback_close", "denial_close",
  "hostile_close", "deceased_close", "dnc_close"];

export const recordingUrl = (attemptId) => `${process.env.REACT_APP_BACKEND_URL}/api/recordings/${attemptId}`;

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
