"""Entry point: python -m mcp_akamai."""

from __future__ import annotations

import logging

from mcp_akamai.logging_config import configure_logging
from mcp_akamai.settings import AkamaiSettings

logger = logging.getLogger(__name__)


def main() -> None:
    settings = AkamaiSettings()  # type: ignore[call-arg]

    # Configure unified logging before anything else runs
    uvicorn_log_config = configure_logging(
        log_format=settings.log_format,
        log_level=settings.log_level,
    )

    from mcp_akamai.server import create_server

    mcp = create_server(settings)

    logger.info("starting transport=%s", settings.transport)

    if settings.transport == "http":
        mcp.run(
            transport="streamable-http",
            host="0.0.0.0",
            port=settings.http_port,
            stateless_http=True,
            show_banner=False,
            uvicorn_config={"log_config": uvicorn_log_config},
        )
    elif settings.transport == "sse":
        mcp.run(
            transport="sse",
            host="0.0.0.0",
            port=settings.http_port,
            show_banner=False,
            uvicorn_config={"log_config": uvicorn_log_config},
        )
    else:
        mcp.run(transport="stdio", show_banner=False)


if __name__ == "__main__":
    main()
