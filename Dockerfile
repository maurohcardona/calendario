FROM python:3.12-slim

WORKDIR /app

# instalar uv
RUN pip install uv

# copiar dependencias primero (cache de Docker)
COPY pyproject.toml uv.lock ./

# instalar dependencias dentro del venv del proyecto
RUN uv sync --frozen --no-dev

# copiar código
COPY . .

EXPOSE 8000

# CMD base — sobreescrito por docker-compose según entorno
CMD ["uv", "run", "python", "manage.py", "runserver", "0.0.0.0:8000"]