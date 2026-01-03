import http.server
import ssl

PORT = 5500
server_address = ('0.0.0.0', PORT)

# HTTP server
httpd = http.server.HTTPServer(server_address, http.server.SimpleHTTPRequestHandler)

# Wrap socket với HTTPS dùng self-signed certificate
httpd.socket = ssl.wrap_socket(
    httpd.socket,
    keyfile="server.key",
    certfile="server.crt",
    server_side=True
)

print(f"Serving HTTPS on 0.0.0.0:{PORT}")
httpd.serve_forever()
