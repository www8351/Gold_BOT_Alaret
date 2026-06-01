import { useEffect, useRef, useState } from "react";
import { Header, StatusCard, LevelsCard, SignalCard, ChartCard, LogCard } from "./components/Cards.jsx";

const REFRESH = 5000;
const initialToken = () =>
  new URLSearchParams(location.search).get("token") || localStorage.getItem("qt_token") || "";

export default function App() {
  const [token, setToken] = useState(initialToken);
  const [state, setState] = useState(null);
  const [err, setErr] = useState("");
  const [nonce, setNonce] = useState(0);
  const tokenRef = useRef(token);
  tokenRef.current = token;

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const r = await fetch(`/api/state?token=${encodeURIComponent(tokenRef.current)}`);
        if (!r.ok) { if (alive) setErr(`auth/error: HTTP ${r.status}`); return; }
        const s = await r.json();
        if (alive) { setErr(""); setState(s); setNonce((n) => n + 1); }
      } catch (e) {
        if (alive) setErr("fetch failed: " + e);
      }
    };
    tick();
    const id = setInterval(tick, REFRESH);
    return () => { alive = false; clearInterval(id); };
  }, [token]);

  const connect = (t) => { setToken(t); localStorage.setItem("qt_token", t); };

  return (
    <>
      <Header state={state} token={token} onConnect={connect} />
      {err && <div className="err">{err}</div>}
      <div className="wrap">
        <StatusCard state={state} />
        <LevelsCard state={state} />
        <SignalCard state={state} />
        <ChartCard token={token} nonce={nonce} />
        <LogCard state={state} />
      </div>
    </>
  );
}
