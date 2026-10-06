import json, time, threading
from http.server import BaseHTTPRequestHandler, HTTPServer

temp = 20
direction = 1

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        global temp
        if self.path == '/temp':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"temperature": temp}).encode())
        else:
            self.send_response(404)
            self.end_headers()
    def log_message(self, format, *args): pass

def update_temp():
    global temp, direction
    while True:
        time.sleep(2)
        temp += direction
        if temp >= 31: direction = -1
        elif temp <= 20: direction = 1

threading.Thread(target=update_temp, daemon=True).start()
HTTPServer(('10.0.0.100', 8080), Handler).serve_forever()
