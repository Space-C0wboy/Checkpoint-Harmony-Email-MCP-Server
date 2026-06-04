import argparse
import logging

from fastmcp import FastMCP

from .client import HarmonyClient
from .config import Settings


def build_server() -> FastMCP:
    settings = Settings()
    logging.basicConfig(level=settings.log_level)
    app = FastMCP("checkpoint-harmony")
    client = HarmonyClient(settings)

    from .tools import scopes, events, entities, exceptions

    scopes.register(app, settings, client)
    events.register(app, settings, client)
    entities.register(app, settings, client)
    exceptions.register(app, settings, client)
    return app


def main() -> None:
    parser = argparse.ArgumentParser(prog="checkpoint-harmony-mcp")
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()

    app = build_server()
    if args.transport == "http":
        settings = Settings()
        app.run(
            transport="http",
            host=args.host or settings.mcp_http_host,
            port=args.port or settings.mcp_http_port,
        )
    else:
        app.run()


if __name__ == "__main__":
    main()
