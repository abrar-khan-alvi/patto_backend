FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip \
    && pip install -r /app/requirements.txt

COPY . /app

RUN addgroup --system patto \
    && adduser --system --ingroup patto patto \
    && mkdir -p /app/media /app/staticfiles \
    && chown -R patto:patto /app/media /app/staticfiles \
    && chmod +x /app/docker/*.sh

USER patto

EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["/app/docker/start-api.sh"]
