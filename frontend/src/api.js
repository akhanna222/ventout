export async function login(email, password) {
  const res = await fetch("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error("Login failed");
  return res.json();
}

export async function uploadVoiceNote(file, token, storeRaw = false) {
  const form = new FormData();
  form.append("file", file);
  form.append("store_raw", storeRaw);

  const res = await fetch("/voice-note", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });
  if (!res.ok) throw new Error("Voice note failed");
  return res.json();
}

export async function getRealtimeToken(token) {
  const res = await fetch("/realtime/token", {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("Realtime token failed");
  return res.json();
}

export function supportsWebRTC() {
  return typeof RTCPeerConnection !== "undefined" && !!navigator.mediaDevices?.getUserMedia;
}

export async function startRealtimeTransport(accessToken, onStatus) {
  if (!supportsWebRTC()) {
    throw new Error("WebRTC not supported in this browser");
  }

  onStatus?.("initializing");
  const peer = new RTCPeerConnection();
  const channel = peer.createDataChannel("listener-heartbeat");
  channel.onopen = () => onStatus?.("ready");
  channel.onerror = () => onStatus?.("error");

  // Placeholder for exchanging SDP with OpenAI Realtime once signaling endpoint is wired.
  // The accessToken should be sent to your backend that proxies/authorizes the session.

  return () => {
    channel.close();
    peer.close();
    onStatus?.("stopped");
  };
}
