from __future__ import annotations

import time
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..core.system_state import SystemState

from ..boot.loader import load_config
from ..boot.starter import Gev5System

app = FastAPI(
    title="GeV5 Supervision API",
    version="2.0",
    description="API de supervision (lecture seule) pour le portique GeV5 V2.",
)

system: Gev5System | None = None

@app.on_event("startup")
def _startup() -> None:
    """
    Démarre le moteur GeV5 dans le MÊME process que l'API
    pour que SystemState reflète l'état réel (threads en cours).
    """
    global system
    cfg = load_config()     # utilise PARAM_DB_PATH par défaut
    system = Gev5System(cfg)
    system.start_all()

# CORS (si tu fais une UI web)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # mets une liste stricte plus tard
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"ok": True, "ts": time.time()}


@app.get("/state")
def state() -> Dict[str, Any]:
    """
    Snapshot global (léger). Évite d’envoyer les courbes complètes.
    """
    return {
        "ts": time.time(),
        "counts": SystemState.get_counts(),
        "raw_counts": SystemState.get_raw_counts(),
        "alarms": {
            "states": SystemState.get_alarm_states(),
            "measures": SystemState.get_alarm_measures(),
            "background": SystemState.get_background(),
        },
        "defauts": SystemState.get_defauts(),
    }


@app.get("/counts")
def counts() -> Dict[str, Any]:
    return {
        "ts": time.time(),
        "counts": SystemState.get_counts(),
        "raw_counts": SystemState.get_raw_counts(),
    }


@app.get("/alarms")
def alarms() -> Dict[str, Any]:
    return {
        "ts": time.time(),
        "states": SystemState.get_alarm_states(),
        "measures": SystemState.get_alarm_measures(),
        "background": SystemState.get_background(),
    }


@app.get("/defauts")
def defauts() -> Dict[str, Any]:
    return {"ts": time.time(), "defauts": SystemState.get_defauts()}


@app.get("/curves")
def curves() -> Dict[str, Any]:
    """
    Attention: payload potentiellement lourd (12 voies * 3600 points).
    Pour UI, on préférera un endpoint paginé ou downsample.
    """
    return {"ts": time.time(), "curves": SystemState.get_curves()}
