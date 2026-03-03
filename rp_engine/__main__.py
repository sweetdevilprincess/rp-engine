"""Allow running with `python -m rp_engine` or the `rp-engine` console script."""

import argparse
import uvicorn
from rp_engine.config import get_config


def main():
    config = get_config()

    parser = argparse.ArgumentParser(description="RP Engine API server")
    parser.add_argument("--host", default=config.server.host, help="Bind address (default: %(default)s)")
    parser.add_argument("--port", "-p", type=int, default=config.server.port, help="Port (default: %(default)s)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    args = parser.parse_args()

    uvicorn.run(
        "rp_engine.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
