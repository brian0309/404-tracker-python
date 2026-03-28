import asyncio
import sys

from scanner404.ui import run_app


if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def main() -> None:
    try:
        run_app()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
