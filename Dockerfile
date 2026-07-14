FROM python:3.10

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

RUN apt update && apt install -y \
    rsync \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /livesync

RUN mkdir -p /root/.ssh && \
echo '-----BEGIN OPENSSH PRIVATE KEY-----\n\
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW\n\
QyNTUxOQAAACBgQkCwBpNRzd3pQ4TYTrSI1y11y1l3ay/pCv+4cedxwwAAAJg/9pNIP/aT\n\
SAAAAAtzc2gtZWQyNTUxOQAAACBgQkCwBpNRzd3pQ4TYTrSI1y11y1l3ay/pCv+4cedxww\n\
AAAEAkwnTl5j6SNfDsAUj4D+D2WWsOCNMGVgxDQifyVYXFyGBCQLAGk1HN3elDhNhOtIjX\n\
LXXLWXdrL+kK/7hx53HDAAAAFHJvZGphQFJvZGphLU0xLmxvY2FsAQ==\n\
-----END OPENSSH PRIVATE KEY-----' >> /root/.ssh/id_ed25519 && \
chmod 600 /root/.ssh/id_ed25519 && \
echo 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGBCQLAGk1HN3elDhNhOtIjXLXXLWXdrL+kK/7hx53HD livesync.docker\n' > /root/.ssh/id_ed25519.pub && \
echo "Host target\n   StrictHostKeyChecking no\n   UserKnownHostsFile=/dev/null\n   LogLevel=ERROR\n" >> /root/.ssh/config

RUN wget https://raw.githubusercontent.com/torokmark/assert.sh/main/assert.sh -O /root/assert.sh && echo ". /root/assert.sh" >> ~/.bashrc

# The image has no .git, so poetry-dynamic-versioning needs the version passed by the builder.
# No default: an image built without --build-arg VERSION=... must fail instead of silently
# reporting 0.0.0.
ARG VERSION
RUN test -n "$VERSION" || { echo "build arg VERSION is required (e.g. --build-arg VERSION=1.2.3)" >&2; exit 1; }
ENV POETRY_DYNAMIC_VERSIONING_BYPASS=$VERSION
# Make the project's virtualenv the default so the `livesync` entrypoint is on PATH.
ENV PATH="/livesync/.venv/bin:$PATH"

# Install dependencies first so this layer survives source changes.
COPY pyproject.toml uv.lock /livesync/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY README.md LICENSE /livesync/
COPY livesync /livesync/livesync
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

ADD tests /livesync/tests

WORKDIR /app
ENTRYPOINT [ "livesync" ]
CMD [ "--help" ]
