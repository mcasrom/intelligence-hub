import os
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

COUNTER_FILE = Path("/var/www/daily_readings/.visit_counter")


class CounterHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()

        count = 0
        if COUNTER_FILE.exists():
            try:
                count = int(COUNTER_FILE.read_text().strip())
            except ValueError:
                count = 0

        if "visit=1" in self.path:
            count += 1
            COUNTER_FILE.parent.mkdir(parents=True, exist_ok=True)
            COUNTER_FILE.write_text(str(count))

        self.wfile.write(json.dumps({"count": count}).encode())


def main():
    port = int(os.environ.get("PORT", 9099))
    server = HTTPServer(("127.0.0.1", port), CounterHandler)
    print(f"[Counter] http://127.0.0.1:{port} → {COUNTER_FILE}")
    server.serve_forever()


if __name__ == "__main__":
    main()
