import argparse
import logging

from fastmcp import FastMCP

from .config import Settings


def build_server() -> FastMCP:
    settings = Settings()
    logging.basicConfig(level=settings.log_level)
    app = FastMCP("checkpoint-harmony")

    from .tools import scopes, events, entities, exceptions

    scopes.register(app, settings)
    events.register(app, settings)
    entities.register(app, settings)
    exceptions.register(app, settings)
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
