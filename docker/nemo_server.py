"""
Minimal HTTP wrapper around NeMo ASR — used inside the Docker container.
Implements the OpenAI /v1/audio/transcriptions interface so that
ParakeetNeMoAdapter can talk to it via HTTP (same as NIM).
"""
import io
import json
import os
import tempfile
import wave
from http.server import BaseHTTPRequestHandler, HTTPServer

MODEL_NAME = os.environ.get("MODEL_NAME", "nvidia/parakeet-tdt-0.6b-v3")
PORT       = int(os.environ.get("PORT", 5001))

print(f"[NeMo server] Loading model: {MODEL_NAME} …", flush=True)
from nemo.collections.asr.models import ASRModel  # type: ignore[import]
_model = ASRModel.from_pretrained(MODEL_NAME)
_model.eval()
print(f"[NeMo server] Model ready — listening on :{PORT}", flush=True)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # suppress default access log
        pass

    def do_GET(self):
        if self.path == "/health":
            body = json.dumps({"ok": True, "model": MODEL_NAME}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path not in ("/v1/audio/transcriptions", "/audio/transcriptions"):
            self.send_error(404)
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body           = self.rfile.read(content_length)

        # Multipart parsing — extract the "file" field
        boundary = None
        for part in self.headers.get("Content-Type", "").split(";"):
            part = part.strip()
            if part.startswith("boundary="):
                boundary = part[len("boundary="):].strip().encode()
                break

        wav_bytes = b""
        if boundary:
            for chunk in body.split(b"--" + boundary):
                if b'name="file"' in chunk or b"name=file" in chunk:
                    # skip headers
                    if b"\r\n\r\n" in chunk:
                        wav_bytes = chunk.split(b"\r\n\r\n", 1)[1].rstrip(b"\r\n--")
                    break

        if not wav_bytes:
            self._json(400, {"error": "no file in request"})
            return

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(wav_bytes)
            tmp_path = tmp.name

        try:
            results = _model.transcribe([tmp_path])
            text    = results[0].strip() if results else ""
        except Exception as exc:
            self._json(500, {"error": str(exc)})
            return
        finally:
            os.unlink(tmp_path)

        self._json(200, {"text": text})

    def _json(self, status: int, obj: dict):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    server.serve_forever()
