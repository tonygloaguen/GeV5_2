"""
API publique GeV5 (V2)

Tout import externe doit passer par ce module.
Cela permet de figer les interfaces publiques et de refactorer l'interne sans casser l'extérieur.
"""

from ..hardware.io import HardwarePort, create_hardware
from ..hardware.passage import PassageService, PassageConfig
from ..core.system_state import SystemState

# Optionnel (si tu veux considérer l'acquittement comme API stable)
from ..core.acquittement.acquittement import AcquittementThread, AcquittementConfig

__all__ = [
    "HardwarePort",
    "create_hardware",
    "PassageService",
    "PassageConfig",
    "SystemState",
    "AcquittementThread",
    "AcquittementConfig",
]
