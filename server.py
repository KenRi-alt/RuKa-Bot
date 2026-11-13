import os
import sys
import threading
import runpy
from http.server import HTTPServer, BaseHTTPRequestHandler

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"RuKa-Bot Enterprise Edition is Live!")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        # Suppress excessive HTTP access logs to keep terminal clean
        return

def run_http_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    print(f"[SERVER] Health check listener active on port {port}")
    server.serve_forever()

if __name__ == "__main__":
    # Start the HTTP server in a daemon thread for Render port-binding
    server_thread = threading.Thread(target=run_http_server, daemon=True)
    server_thread.start()
    
    print("[RUKA] Initializing Bot Core Package...")
    try:
        runpy.run_module("RUKA", run_name="__main__")
    except Exception as e:
        print(f"[CRITICAL ERROR] Bot execution failed: {e}")
        sys.exit(1)
