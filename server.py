import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import runpy

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"RuKa-Bot is up and running!")

def run_http_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    print(f"HTTP server listening on port {port}")
    server.serve_forever()

if __name__ == "__main__":
    # Start the HTTP server in a background thread so Render's port scan passes
    server_thread = threading.Thread(target=run_http_server, daemon=True)
    server_thread.start()
    
    # Run your bot package normally
    runpy.run_module("RUKA", run_name="__main__")
