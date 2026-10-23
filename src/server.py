"""Local server entry point.

Run `python src/server.py` from the repo root. In development use the Vite
server in `web/` (it proxies `/api` here); in production `npm --prefix web run
build` and FastAPI serves `web/dist`.
"""

import uvicorn


def main():
    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
