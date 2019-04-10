ARG DOCKER_VERSION=18.09.5
ARG PYTHON_VERSION=3.7.3
ARG ALPINE_VERSION=3.9
ARG DEBIAN_VERSION=stretch-slim
ARG BUILD_PLATFORM=alpine

FROM docker:${DOCKER_VERSION} AS docker-cli

FROM python:${PYTHON_VERSION}-alpine${ALPINE_VERSION} AS build-alpine
RUN apk add --no-cache \
    bash \
    build-base \
    ca-certificates \
    curl \
    gcc \
    git \
    libc-dev \
    libffi-dev \
    libgcc \
    make \
    musl-dev \
    openssl \
    openssl-dev \
    python2 \
    python2-dev \
    zlib-dev
ENV BUILD_BOOTLOADER=1

FROM python:${PYTHON_VERSION}-slim-stretch AS build-debian
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    git \
    libc-dev \
    libgcc-6-dev \
    make \
    openssl \
    python2.7-dev

FROM build-${BUILD_PLATFORM} AS build
ENTRYPOINT ["sh", "/usr/local/bin/docker-compose-entrypoint.sh"]
COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker
WORKDIR /code/
# FIXME(chris-crone): virtualenv 16.3.0 breaks build, force 16.2.0 until fixed
RUN pip install virtualenv==16.2.0
RUN pip install tox==2.9.1

COPY docker-compose-entrypoint.sh /usr/local/bin/
COPY requirements.txt .
COPY requirements-dev.txt .
COPY .pre-commit-config.yaml .
COPY tox.ini .
COPY setup.py .
COPY README.md .
COPY compose compose/
RUN tox --notest
COPY . .
ARG GIT_COMMIT=unknown
ENV DOCKER_COMPOSE_GITSHA=$GIT_COMMIT
RUN script/build/linux-entrypoint

FROM alpine:${ALPINE_VERSION} AS runtime-alpine
FROM debian:${DEBIAN_VERSION} AS runtime-debian
FROM runtime-${BUILD_PLATFORM} AS runtime
ENTRYPOINT ["sh", "/usr/local/bin/docker-compose-entrypoint.sh"]
COPY --from=docker-cli  /usr/local/bin/docker           /usr/local/bin/docker
COPY --from=build       /usr/local/bin/docker-compose   /usr/local/bin/docker-compose
COPY docker-compose-entrypoint.sh /usr/local/bin/
