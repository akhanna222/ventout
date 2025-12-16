import { useEffect, useMemo, useRef, useState } from "react";
import { getRealtimeToken, login, startRealtimeTransport, supportsWebRTC, uploadVoiceNote } from "./api";
import "./styles.css";

const orbStyles = {
  low: { color: "#6dd3c2", borderRadius: "50%", filter: "blur(2px)" },
  medium: { color: "#f4b860", borderRadius: "45% 55% 50% 50%", filter: "blur(1px)" },
  high: { color: "#ff5f5f", borderRadius: "40% 60% 30% 70%", filter: "drop-shadow(0 0 12px #ff5f5f)" },
};

function MoodOrb({ level = "low" }) {
  const style = orbStyles[level] || orbStyles.low;
  return (
    <div
      className="mood-orb"
      style={{
        background: style.color,
        borderRadius: style.borderRadius,
        filter: style.filter,
      }}
    />
  );
}

export default function App() {
  const [intensity, setIntensity] = useState("low");
  const [status, setStatus] = useState("Idle");
  const [audioUrl, setAudioUrl] = useState(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [token, setToken] = useState(null);
  const [cooldown, setCooldown] = useState(0);
  const [safetyReasons, setSafetyReasons] = useState([]);
  const [storeConsent, setStoreConsent] = useState(false);
  const [realtimeStatus, setRealtimeStatus] = useState("Idle");
  const stopRealtimeRef = useRef(null);
  const fileInput = useRef(null);
  const realtimeSupported = supportsWebRTC();

  const gradientText = useMemo(
    () => ({
      background: "linear-gradient(90deg, #6dd3c2, #8ed1f7, #f4b860)",
      WebkitBackgroundClip: "text",
      WebkitTextFillColor: "transparent",
    }),
    []
  );

  async function handleLogin() {
    setStatus("Authenticating...");
    try {
      const res = await login(email, password);
      setToken(res.access_token);
      setStatus("Logged in");
    } catch (err) {
      console.error(err);
      setStatus("Login failed");
    }
  }

  async function handleUpload(event) {
    const file = event.target.files?.[0];
    if (!file || !token) {
      setStatus("Login first, then upload");
      return;
    }
    setStatus("Uploading...");

    const formData = new FormData();
    formData.append("file", file);

    try {
      const json = await uploadVoiceNote(file, token, storeConsent);
      setIntensity(json.safety_level === "blocked" ? "high" : json.safety_level === "elevated" ? "medium" : "low");
      if (json.audio_bytes_b64) {
        setAudioUrl(`data:audio/mp3;base64,${json.audio_bytes_b64}`);
      }
      setCooldown(json.cooldown_seconds || 0);
      setSafetyReasons(json.safety_reasons || []);
      setStatus(json.safety_level === "blocked" ? "Safety pause" : "Response ready");
    } catch (err) {
      console.error(err);
      setStatus("Upload failed");
    }
  }

  async function startRealtime() {
    if (!token) {
      setStatus("Login to start realtime");
      return;
    }
    setRealtimeStatus("Requesting token...");
    try {
      const { access_token: rtToken } = await getRealtimeToken(token);
      stopRealtimeRef.current = await startRealtimeTransport(rtToken, setRealtimeStatus);
      setRealtimeStatus("Ready (WebRTC handshake stub)");
    } catch (err) {
      console.error(err);
      setRealtimeStatus("Realtime failed");
    }
  }

  function stopRealtime() {
    stopRealtimeRef.current?.();
    setRealtimeStatus("Stopped");
  }

  useEffect(() => {
    if (audioUrl) {
      const audio = new Audio(audioUrl);
      audio.play();
    }
  }, [audioUrl]);

  useEffect(() => {
    if (!cooldown) return;
    const timer = setInterval(() => {
      setCooldown((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(timer);
  }, [cooldown]);

  return (
    <div className="page">
      <header>
        <h1 style={gradientText}>Listener AI</h1>
        <p>A calm, safety-first voice companion.</p>
      </header>

      <section className="card">
        <h2>Login</h2>
        <div className="form-row">
          <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" />
          <input
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Password"
            type="password"
          />
          <button onClick={handleLogin}>Authenticate</button>
        </div>
        {token && <p className="hint">Session token ready.</p>}
      </section>

      <div className="orb-row">
        <MoodOrb level={intensity} />
        <div>
          <div className="status">{status}</div>
          <p className="hint">Orb color shifts with intensity: teal (calm) → amber (elevated) → red (blocked/safety).</p>
        </div>
      </div>

      <section className="card">
        <h2>Voice note</h2>
        <p>Drop an audio clip to get a spoken response.</p>
        <button onClick={() => fileInput.current?.click()}>Upload audio</button>
        <input ref={fileInput} type="file" accept="audio/*" style={{ display: "none" }} onChange={handleUpload} />
        <label className="hint" style={{ display: "block", marginTop: 8 }}>
          <input type="checkbox" checked={storeConsent} onChange={(e) => setStoreConsent(e.target.checked)} /> I consent to
          store raw audio in encrypted storage (S3).
        </label>
      </section>

      <section className="card">
        <h2>Safety</h2>
        <ul>
          <li>Blocks violent or self-harm intent; offers grounding + helpline suggestions.</li>
          <li>Cooldowns and rate limits to prevent escalating loops.</li>
          <li>Optional consent gate before storing raw audio.</li>
        </ul>
        {cooldown > 0 && (
          <div className="hint">Cooldown in progress: {cooldown}s left. Take a breath and try again soon.</div>
        )}
        {safetyReasons.length > 0 && <div className="hint">Reasons flagged: {safetyReasons.join(", ")}</div>}
      </section>

      <section className="card">
        <h2>Realtime (WebRTC)</h2>
        <p>Browser support: {realtimeSupported ? "Ready" : "Unavailable"}</p>
        <div className="form-row">
          <button onClick={startRealtime} disabled={!realtimeSupported}>
            Start realtime
          </button>
          <button onClick={stopRealtime} disabled={!stopRealtimeRef.current}>
            Stop
          </button>
        </div>
        <div className="hint">Status: {realtimeStatus}</div>
        <p className="hint">Uses WebRTC transport when supported, with server-issued OpenAI Realtime tokens.</p>
      </section>
    </div>
  );
}
