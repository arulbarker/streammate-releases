"""
modules/revai_stream.py
-------------------------------------------------
Streaming STT real-time ke Rev.ai (WebSocket).

• Format audio  : RAW PCM 16-bit LE, 16 kHz, mono
• Chunk size    : ≥ 250 ms  (8 000 byte)
• Dependencies  : websocket-client, sounddevice

Contoh pemakaian:
    from modules.revai_stream import RevAIStream

    def on_text(text, is_final):
        print("[FINAL]" if is_final else "[PART]", text)

    streamer = RevAIStream(
        token="YOUR_REVAI_TOKEN",
        callback=on_text,
        mic_index=0        # index mic di sounddevice
    )
    streamer.start()

    # … panggil streamer.stop() ketika ingin berhenti
"""

from __future__ import annotations
import ssl, json, time, threading, queue, sys
import sounddevice as sd
import numpy as np
import websocket  # pip install websocket-client

REV_WS_ENDPOINT = (
    "wss://api.rev.ai/speechtotext/v1/stream"
    "?access_token={token}"
    "&content_type=audio/x-raw;layout=interleaved;rate=16000;format=S16LE;channels=1"
)

# ──────────────────────────────────────────────────────────────────────────
class RevAIStream:
    def __init__(
        self,
        token: str,
        callback,
        mic_index: int = 0,
        chunk_ms: int = 250,
        sample_rate: int = 16000,
    ):
        """
        token     : Access-token Rev.ai
        callback  : fungsi dipanggil tiap transcript (text, is_final:bool)
        mic_index : index microphone (lihat sd.query_devices())
        """
        self.url = REV_WS_ENDPOINT.format(token=token)
        self.cb  = callback
        self.mic_index = mic_index
        self.sample_rate = sample_rate
        self.chunk_bytes = int(sample_rate * 2 * (chunk_ms / 1000.0))  # 2 byte / sampel
        self.ws: websocket.WebSocketApp | None = None
        self._stop_flag = threading.Event()
        self._audio_q: queue.Queue[bytes] = queue.Queue()

    # ─── WebSocket events ────────────────────────────────────────────────
    def _on_open(self, ws):
        print("✅ Rev.ai WebSocket connected")

    def _on_message(self, ws, msg):
        try:
            data = json.loads(msg)
            typ  = data.get("type")
            if typ in ("partial", "final"):
                words = [e["value"] for e in data["elements"] if e["type"] == "text"]
                text  = " ".join(words).strip()
                if text:
                    self.cb(text, typ == "final")
        except Exception as e:
            print("⚠️ Rev.ai message parse error:", e)

    def _on_error(self, ws, err):
        print("❌ Rev.ai WebSocket error:", err)

    def _on_close(self, ws, code, reason):
        print(f"🔒 WebSocket closed ({code}) {reason}")

    # ─── Internal Threads ───────────────────────────────────────────────
    def _run_ws(self):
        self.ws = websocket.WebSocketApp(
            self.url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )
        # ignore cert verification if needed
        self.ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})

    def _run_mic(self):
        def callback(indata, _frames, _time, _status):
            if _status:
                print("⚠️ Mic status:", _status, file=sys.stderr)
            self._audio_q.put(indata.copy())

        with sd.InputStream(
            device=self.mic_index,
            samplerate=self.sample_rate,
            channels=1,
            dtype="int16",
            callback=callback,
        ):
            buf = bytearray()
            while not self._stop_flag.is_set():
                try:
                    data = self._audio_q.get(timeout=0.1)
                    buf.extend(data.tobytes())
                    # kirim tiap ≥ chunk_bytes
                    if len(buf) >= self.chunk_bytes and self.ws and self.ws.sock and self.ws.sock.connected:
                        self.ws.send(bytes(buf), opcode=websocket.ABNF.OPCODE_BINARY)
                        buf.clear()
                except queue.Empty:
                    continue
            # kirim sisa buffer
            if buf and self.ws and self.ws.sock and self.ws.sock.connected:
                self.ws.send(bytes(buf), opcode=websocket.ABNF.OPCODE_BINARY)
            # beri sinyal EOS
            if self.ws and self.ws.sock and self.ws.sock.connected:
                self.ws.send("EOS")

    # ─── Public API ──────────────────────────────────────────────────────
    def start(self):
        self._stop_flag.clear()
        threading.Thread(target=self._run_ws,  daemon=True).start()
        threading.Thread(target=self._run_mic, daemon=True).start()

    def stop(self):
        self._stop_flag.set()
        # tunggu agar thread mic selesai mengirim EOS
        time.sleep(0.3)
