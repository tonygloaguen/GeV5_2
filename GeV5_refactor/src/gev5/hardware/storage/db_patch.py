# db_patch.py — v3.1 : per-DB write locks + waits courts + logs + WAL tuning
import os, sqlite3, threading, time, re, functools, collections

_ORIG_CONNECT = sqlite3.connect

# Tunables (peuvent être changés via env)
MAX_WAIT_S = float(os.getenv("GEV5_DB_MAX_WAIT_S", "0.8"))   # total retry sur "locked"
STEP_S     = float(os.getenv("GEV5_DB_STEP_S", "0.02"))      # pas d’attente entre retries
WARN_MS    = int(os.getenv("GEV5_DB_WARN_MS", "100"))        # log si >100 ms

# Un verrou PAR base (chemin) → pas de blocage global
_LOCKS = collections.defaultdict(threading.RLock)
_LOCKS_GUARD = threading.RLock()

WRITE_SQL = re.compile(
    r"^\s*(BEGIN|INSERT|UPDATE|DELETE|REPLACE|CREATE|ALTER|DROP|COMMIT|END|VACUUM|PRAGMA\s+wal_checkpoint)\b",
    re.I
)

def _wlock(db_id: str):
    with _LOCKS_GUARD:
        return _LOCKS[db_id]

def _retry(fn):
    t0 = time.time()
    waited = 0.0
    tries = 0
    while True:
        try:
            return fn()
        except sqlite3.OperationalError as e:
            msg = str(e).lower()
            if ("locked" in msg or "busy" in msg) and (time.time() - t0 < MAX_WAIT_S):
                time.sleep(STEP_S)
                waited += STEP_S; tries += 1
                continue
            raise
        finally:
            if waited*1000 > WARN_MS:
                print(f"[db_patch] waited={int(waited*1000)} ms tries={tries}", flush=True)

def _apply_pragmas(conn):
    c = conn.cursor()
    # Robustesse + perf
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA synchronous=NORMAL;")
    c.execute("PRAGMA busy_timeout=1000;")          # 1 s -> n’attend pas trop
    c.execute("PRAGMA wal_autocheckpoint=500;")     # checkpoint auto
    c.execute("PRAGMA journal_size_limit=67108864;")# 64 MB max
    # Lecture/perf
    c.execute("PRAGMA temp_store=MEMORY;")
    try: c.execute("PRAGMA mmap_size=268435456;")   # 256 MB si possible
    except sqlite3.OperationalError: pass
    c.execute("PRAGMA cache_size=-20000;")          # ~20k pages en mémoire (négatif = KB)
    conn.commit()

class _CurProxy:
    def __init__(self, cur, lock):
        self._cur = cur
        self._lock = lock
    def execute(self, sql, *args, **kw):
        if isinstance(sql, str) and WRITE_SQL.match(sql):
            with self._lock:
                return _retry(lambda: self._cur.execute(sql, *args, **kw))
        return self._cur.execute(sql, *args, **kw)
    def executemany(self, sql, seq, *args, **kw):
        if isinstance(sql, str) and WRITE_SQL.match(sql):
            with self._lock:
                return _retry(lambda: self._cur.executemany(sql, seq, *args, **kw))
        return self._cur.executemany(sql, seq, *args, **kw)
    def executescript(self, script, *args, **kw):
        with self._lock:
            return _retry(lambda: self._cur.executescript(script, *args, **kw))
    def __getattr__(self, name): return getattr(self._cur, name)
    def __iter__(self): return iter(self._cur)

class _ConnProxy:
    def __init__(self, conn, db_id):
        self._conn = conn
        self._wlock = _wlock(db_id)
    def cursor(self, *a, **k): return _CurProxy(self._conn.cursor(*a, **k), self._wlock)
    def commit(self): 
        with self._wlock: return _retry(self._conn.commit)
    def executescript(self, s, *a, **k):
        with self._wlock: return _retry(lambda: self._conn.executescript(s, *a, **k))
    def __getattr__(self, n): return getattr(self._conn, n)
    def __enter__(self): self._conn.__enter__(); return self
    def __exit__(self, *x): return self._conn.__exit__(*x)

def connect(path, timeout=5.0, check_same_thread=False, **kw):
    conn = _ORIG_CONNECT(path, timeout=timeout, check_same_thread=check_same_thread, **kw)
    _apply_pragmas(conn)
    # db_id = chemin absolu (stabilise l’ID du verrou)
    try:
        db_id = os.path.abspath(path)
    except Exception:
        db_id = str(path)
    return _ConnProxy(conn, db_id)

# Monkey-patch global
sqlite3.connect = connect
