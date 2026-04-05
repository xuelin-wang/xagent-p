import argparse
import sys

import uvicorn

from xagent.api_http.app import ApiHttpConfig
from xagent.api_http.app import create_app
from xagent.runtime_config import load_runtime_config


def main() -> int:
    config, remaining_args = load_runtime_config(ApiHttpConfig, sys.argv[1:])
    parser = argparse.ArgumentParser(description="Run the LangChain HTTP API service.")
    parser.parse_args(remaining_args)
    uvicorn.run(
        create_app(config),
        host=config.host,
        port=config.port,
        reload=config.reload,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
