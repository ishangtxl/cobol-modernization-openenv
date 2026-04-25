FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

COPY legacy_cobol_env/server/requirements.txt /tmp/server-requirements.txt
RUN pip install --no-cache-dir -r /tmp/server-requirements.txt "openai>=1.0"

COPY legacy_cobol_env ./legacy_cobol_env
COPY server ./server
COPY inference.py openenv.yaml README.md ./

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"

CMD ["python", "-m", "uvicorn", "legacy_cobol_env.server.app:app", "--host", "0.0.0.0", "--port", "8000"]
