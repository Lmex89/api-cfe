FROM python:3.12-alpine AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apk add --no-cache \
        build-base \
        mariadb-connector-c-dev \
        pkgconfig

WORKDIR /build

COPY app/requirements.pip ./requirements.pip

RUN pip install --upgrade pip setuptools wheel && \
    pip wheel --disable-pip-version-check --no-cache-dir \
        --wheel-dir /wheels \
        -r requirements.pip

FROM python:3.12-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

RUN apk add --no-cache mariadb-connector-c

RUN adduser -D -s /sbin/nologin appuser

WORKDIR /home/appuser/app

COPY --from=builder /wheels /wheels
COPY app/requirements.pip /tmp/requirements.pip

RUN pip install --no-cache-dir --no-compile --no-index \
    --find-links=/wheels -r /tmp/requirements.pip && \
    rm -rf /wheels /tmp/requirements.pip

COPY --chown=appuser:appuser app/ /home/appuser/app/

USER appuser

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--limit-concurrency", "300", "--timeout-keep-alive", "35", "--header", "Strict-Transport-Security:max-age=31536000;includeSubDomains", "--no-server-header"]
