import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from lse_rsi.health import archive_attempt, server_ready, wait_for_server


class _Models(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"data": [{"id": "m"}]}).encode()
        self.send_response(200 if self.path == "/v1/models" else 404)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def test_server_ready_true_and_false():
    srv = HTTPServer(("127.0.0.1", 0), _Models)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        assert server_ready(f"http://127.0.0.1:{srv.server_port}/v1")
        assert wait_for_server(f"http://127.0.0.1:{srv.server_port}/v1", max_wait=1, interval=0.1)
    finally:
        srv.shutdown()
    assert not server_ready("http://127.0.0.1:9/v1", timeout=0.5)
    assert not wait_for_server("http://127.0.0.1:9/v1", max_wait=0.3, interval=0.1, log=lambda *_: None)


def test_archive_attempt_keeps_old_and_frees_name(tmp_path):
    rdir = tmp_path / "r1-lse-financial-s1"
    rdir.mkdir()
    (rdir / "rsi_metrics.jsonl").write_text('{"step": 0}\n')
    a = archive_attempt(rdir, stamp="T")
    assert a.name == "r1-lse-financial-s1.attempt-T" and (a / "rsi_metrics.jsonl").exists()
    assert not rdir.exists()
    rdir.mkdir()
    b = archive_attempt(rdir, stamp="T")
    assert b.name == "r1-lse-financial-s1.attempt-T-1"
    assert archive_attempt(tmp_path / "missing") is None
