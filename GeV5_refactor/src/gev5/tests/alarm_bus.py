# Auto-generated monotonic alarm bus (thread-safe)
import threading

STATE_LOCK = threading.Lock()
_level = 0

def get_level():
    return _level

def set_level(new_level: int):
    global _level
    with STATE_LOCK:
        if new_level > _level:
            _level = new_level
    return _level

def reset_level():
    global _level
    with STATE_LOCK:
        _level = 0
    return _level
