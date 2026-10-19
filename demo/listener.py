"""Local 'attacker' listener for the demo. Logs anything it receives to listener.log.
Binds to 127.0.0.1 only. It never talks to the internet."""
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

LOG = "listener.log"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        with open(LOG, "a") as f:
            f.write(f"LEAK RECEIVED: {self.path}\n")
        print(f"LEAK RECEIVED: {self.path}", flush=True)
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9999
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
