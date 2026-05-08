from waitress import serve
from Agenda.wsgi import application

if __name__ == "__main__":
    print("Iniciando waitress...")
    print("Servidor iniciado en puerto 8000 con 8 threads")
    serve(application, host="0.0.0.0", port=8000, threads=8)
    print("Waitress finalizó")