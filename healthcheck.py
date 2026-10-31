"""
Health check server — lightweight HTTP endpoint for Railway.
Runs on PORT (Railway provides this), responds to GET / with 200 OK.
Railway uses this to know the bot is alive and auto-restart if it's not.
"""
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import logging

logger = logging.getLogger(__name__)


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'FlightToProfit ALIVE')

    def log_message(self, format, *args):
        pass  # Suppress request logs


def start_health_server():
    """Start health check server in background thread."""
    port = int(os.environ.get('PORT', 8080))
    try:
        server = HTTPServer(('0.0.0.0', port), HealthHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        logger.info(f'💚 Health check server on port {port}')
    except Exception as e:
        logger.warning(f'Health server failed (non-fatal): {e}')
