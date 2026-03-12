FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml setup.py ./
COPY app/ ./app/

RUN pip install --no-cache-dir .

RUN useradd --system --create-home appuser
USER appuser

EXPOSE 5000

# Path to the config file inside the container.
# Override with -e CONFIG_PATH=... or in docker-compose.yml.
ENV CONFIG_PATH=/app/config/config.yml

CMD ["gunicorn", "app.web.app:create_app_from_env", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "300"]
