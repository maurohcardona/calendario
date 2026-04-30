"""
Servidor de producción: Waitress con HTTPS (SSL autofirmado).

Para generar certificados (solo la primera vez):
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \\
      -keyout certs/server.key \\
      -out certs/server.crt \\
      -subj "/C=AR/ST=BuenosAires/L=LaMadero/O=Hospital Balestrini/OU=Laboratorio/CN=192.168.0.86"

Para iniciar el servidor:
    python start_waitress.py
"""

import socket
import ssl
from pathlib import Path

from waitress import create_server
from Agenda.wsgi import application

BASE_DIR = Path(__file__).resolve().parent
CERT_FILE = BASE_DIR / "certs" / "server.crt"
KEY_FILE = BASE_DIR / "certs" / "server.key"
HOST = "0.0.0.0"
PORT = 8000


def start_https(server):
    """Envuelve el socket de Waitress con SSL."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile=str(CERT_FILE), keyfile=str(KEY_FILE))

    # Reemplazar el socket del servidor por uno SSL
    server.socket = ctx.wrap_socket(server.socket, server_side=True)


def print_banner(https: bool) -> None:
    sep = "=" * 60
    if https:
        print(sep)
        print("  LABORATORIO HOSPITAL BALESTRINI — SERVIDOR HTTPS")
        print(sep)
        print(f"🔒 Certificado : {CERT_FILE.name}")
        print(f"🔑 Clave       : {KEY_FILE.name}")
        print(f"🌐 Local       : https://localhost:{PORT}")
        print(f"🌐 Red interna : https://192.168.0.86:{PORT}")
        print(f"📱 PWA         : habilitada (Service Worker + Offline)")
        print(sep)
    else:
        print(sep)
        print("  LABORATORIO HOSPITAL BALESTRINI — SERVIDOR HTTP")
        print("  ⚠️  Modo desarrollo (sin certificados SSL)")
        print("  ⚠️  PWA parcial: Service Worker NO funcionará")
        print(sep)
        print(f"🌐 Local : http://localhost:{PORT}")
        print(sep)
    print("\nPresioná Ctrl+C para detener el servidor\n")


if __name__ == "__main__":
    https = CERT_FILE.exists() and KEY_FILE.exists()
    print_banner(https)

    server = create_server(application, host=HOST, port=PORT)

    if https:
        start_https(server)

    try:
        server.run()
    except KeyboardInterrupt:
        print("\n✅ Servidor detenido")
