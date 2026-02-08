# run_all.py
from __future__ import annotations

import sys
import threading
from pathlib import Path


def _ensure_src_on_path() -> None:
    root = Path(__file__).resolve().parent
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def _start_api_in_thread(host: str = "0.0.0.0", port: int = 8000) -> threading.Thread:
    import uvicorn

    def _run() -> None:
        uvicorn.run(
            "gev5.api_server.app:app",
            host=host,
            port=port,
            log_level="info",
            reload=False,
        )

    t = threading.Thread(target=_run, name="API_Uvicorn", daemon=True)
    t.start()
    return t


def main() -> None:
    _ensure_src_on_path()

    from src.gev5.boot.loader import load_config
    from src.gev5.boot.starter import Gev5System

    cfg = load_config()

    # 1) Moteur
    system = Gev5System(cfg)
    system.start_all()

    # 2) API (toujours)
    def _start_api_in_thread(host: str = "0.0.0.0", port: int = 8000) -> threading.Thread:
        import traceback

        def _run() -> None:
            try:
                import uvicorn
                print(f"[API] starting on http://{host}:{port}")
                uvicorn.run(
                    "gev5.api_server.app:app",
                    host=host,
                    port=port,
                    log_level="info",
                    reload=False,
                )
                print("[API] uvicorn stopped")
            except Exception:
                print("[API] FAILED to start:")
                traceback.print_exc()

        t = threading.Thread(target=_run, name="API_Uvicorn", daemon=True)
        t.start()
        return t


    # 3) Simulateur uniquement si SIM=1
    if int(getattr(cfg, "sim", 0)) == 1:
        from src.gev5.core.simulation.simulateur import Application

        app = Application()
        # option: auto-démarrage des passages/coups
        if hasattr(app, "start_autopilot"):
            app.after(800, app.start_autopilot)
        app.mainloop()
    else:
        # PROD: pas de UI. On bloque le process proprement.
        # (Le moteur + API tournent via threads daemon/non-daemon)
        import time
        while True:
            time.sleep(1)


if __name__ == "__main__":
    main()

