FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --requirement /tmp/requirements.txt

RUN groupadd --system groundsignal \
    && useradd --system --gid groundsignal --create-home groundsignal

COPY --chown=groundsignal:groundsignal backend/__init__.py backend/alembic.ini ./backend/
COPY --chown=groundsignal:groundsignal backend/app ./backend/app
COPY --chown=groundsignal:groundsignal backend/alembic ./backend/alembic

USER groundsignal

EXPOSE 8000

# Nginx keeps the production access log; avoid copying query strings into Docker logs.
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
