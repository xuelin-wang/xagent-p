import os

import uvicorn


def main() -> int:
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("xagent.api_http.app:app", host=host, port=port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
