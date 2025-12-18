from waitress import serve
from Agenda.wsgi import application

if __name__ == "__main__":
    print("Iniciando waitress...")
    serve(application, host="0.0.0.0", port=8000)
    print("Waitress finalizó")