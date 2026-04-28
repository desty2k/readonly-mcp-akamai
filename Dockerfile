FROM python:3.13-slim AS builder
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml .
COPY src/ src/
RUN uv pip install --system --no-cache .

FROM python:3.13-slim
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin/readonly-mcp-akamai /usr/local/bin/readonly-mcp-akamai
ENTRYPOINT ["readonly-mcp-akamai"]
