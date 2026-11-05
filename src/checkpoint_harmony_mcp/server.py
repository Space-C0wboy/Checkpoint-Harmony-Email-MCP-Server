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

    # Proactive rate limiting per the API guide (p. 79): Anti-Phishing exception
    # writes -> 1 rps; other exception writes (URL-rep, DLP) -> 10 rps.
    client.set_bucket("exceptions_ap", rate_per_sec=1.0, burst=1)
    client.set_bucket("exceptions_other", rate_per_sec=10.0, burst=10)

    from .tools import entities, events, exceptions, scopes, sectool_exceptions

    scopes.register(app, settings, client)
    events.register(app, settings, client)
    entities.register(app, settings, client)
    exceptions.register(app, settings, client)
    sectool_exceptions.register(app, settings, client)
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
