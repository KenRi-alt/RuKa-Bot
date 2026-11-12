import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import runpy

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"RuKa-Bot is up and running!")

    def do_HEAD(self):
        # Handle Render's health check HEAD requests
        self.send_response(200)
        self.end_headers()

def run_http_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    print(f"HTTP server listening on port {port}")
    server.serve_forever()

if __name__ == "__main__":
    server_thread = threading.Thread(target=run_http_server, daemon=True)
    server_thread.start()
    
    runpy.run_module("RUKA", run_name="__main__")
