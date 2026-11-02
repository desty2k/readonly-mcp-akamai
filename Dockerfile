FROM python:3.13-slim AS builder
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml README.md ./
COPY src/ src/
RUN uv pip install --system --no-cache .

FROM python:3.13-slim
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin/readonly-mcp-akamai /usr/local/bin/readonly-mcp-akamai

# The default transport is stdio (run with docker run -i). For the http or sse
# transport the server must listen on all interfaces inside the container to be
# reachable through a published port. Publish it on the host's loopback only
# (docker run -p 127.0.0.1:8080:8080 -e AKAMAI_TRANSPORT=http ...): the HTTP
# transport has no authentication.
ENV AKAMAI_HTTP_HOST=0.0.0.0

ENTRYPOINT ["readonly-mcp-akamai"]
