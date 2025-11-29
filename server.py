"""
HTTP Server Module
------------------
Handles all HTTP requests and serves the web interface.
"""

import os
import json
import http.server
import socketserver
import threading
from urllib.parse import urlparse

import gmail_api

PORT = 8766


class RequestHandler(http.server.SimpleHTTPRequestHandler):
    """Custom HTTP request handler."""
    
    def send_json(self, data, status=200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def send_file(self, filepath, content_type):
        """Send file content."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.end_headers()
            self.wfile.write(content.encode())
        except FileNotFoundError:
            self.send_error(404, f'File not found: {filepath}')
    
    def do_GET(self):
        """Handle GET requests."""
        path = urlparse(self.path).path
        
        if path == '/' or path == '/index.html':
            self.send_file('templates/index.html', 'text/html')
        
        elif path == '/static/styles.css':
            self.send_file('static/styles.css', 'text/css')
        
        elif path == '/static/script.js':
            self.send_file('static/script.js', 'application/javascript')
        
        elif path == '/api/status':
            self.send_json(gmail_api.get_scan_status())
        
        elif path == '/api/results':
            self.send_json(gmail_api.get_scan_results())
        
        elif path == '/api/auth-status':
            self.send_json(gmail_api.check_login_status())
        
        elif path == '/api/unread-count':
            self.send_json(gmail_api.get_unread_count())
        
        elif path == '/api/mark-read-status':
            self.send_json(gmail_api.get_mark_read_status())
        
        elif path == '/api/delete-scan-status':
            self.send_json(gmail_api.get_delete_scan_status())
        
        elif path == '/api/delete-scan-results':
            self.send_json(gmail_api.get_delete_scan_results())
        
        else:
            self.send_error(404)
    
    def do_POST(self):
        """Handle POST requests."""
        path = urlparse(self.path).path
        
        # Read request body
        content_length = int(self.headers.get('Content-Length', 0))
        body = {}
        if content_length > 0:
            post_data = self.rfile.read(content_length)
            body = json.loads(post_data.decode())
        
        if path == '/api/scan':
            limit = body.get('limit', 500)
            thread = threading.Thread(target=gmail_api.scan_emails, args=(limit,))
            thread.daemon = True
            thread.start()
            self.send_json({"status": "started"})
        
        elif path == '/api/sign-in':
            # Trigger sign in
            thread = threading.Thread(target=gmail_api.get_gmail_service)
            thread.daemon = True
            thread.start()
            self.send_json({"status": "signing_in"})
        
        elif path == '/api/sign-out':
            result = gmail_api.sign_out()
            self.send_json(result)
        
        elif path == '/api/unsubscribe':
            domain = body.get('domain', '')
            link = body.get('link', '')
            result = gmail_api.unsubscribe_single(domain, link)
            self.send_json(result)
        
        elif path == '/api/mark-read':
            count = body.get('count', 100)
            thread = threading.Thread(target=gmail_api.mark_emails_as_read, args=(count,))
            thread.daemon = True
            thread.start()
            self.send_json({"status": "started"})
        
        elif path == '/api/delete-scan':
            limit = body.get('limit', 1000)
            thread = threading.Thread(target=gmail_api.scan_senders_for_delete, args=(limit,))
            thread.daemon = True
            thread.start()
            self.send_json({"status": "started"})
        
        elif path == '/api/delete-emails':
            sender = body.get('sender', '')
            result = gmail_api.delete_emails_by_sender(sender)
            self.send_json(result)
        
        else:
            self.send_error(404)
    
    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


def start_server(port=PORT):
    """Start the HTTP server."""
    socketserver.TCPServer.allow_reuse_address = True
    
    with socketserver.TCPServer(("", port), RequestHandler) as httpd:
        print(f"🌐 Server running at http://localhost:{port}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n👋 Server stopped!")
