"""Run the Stage 2 UI/API on loopback, separate from the retained Stage 1 service."""

import argparse


def main():
    import uvicorn

    from .api import create_app

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8002)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Use a nonprivileged loopback port")
    uvicorn.run(create_app(), host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
