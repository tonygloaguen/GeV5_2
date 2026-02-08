# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import uvicorn


def main() -> None:
    uvicorn.run(
        "gev5.api_server.app:app",
        host="0.0.0.0",
        port=8000,
        reload=False,  # mets True en dev
        log_level="info",
    )


if __name__ == "__main__":
    main()
