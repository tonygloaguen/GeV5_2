from gev5.boot.loader import load_config
from gev5.boot.starter import Gev5System

cfg = load_config()
cfg.sim = 1  # si tu as un flag sim dans ta config pour éviter le GPIO réel

system = Gev5System(cfg)
system.start_all()

print("System V2 démarré pour test (5s)...")
import time
time.sleep(5)
print("Fin du test.")
