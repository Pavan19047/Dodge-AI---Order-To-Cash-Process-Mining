import duckdb
import threading
from config import DB_PATH


class Database:
    # Per-thread connections — DuckDB connections must not be shared across threads.
    _local = threading.local()
    _mkdir_lock = threading.Lock()

    @classmethod
    def get(cls) -> duckdb.DuckDBPyConnection:
        conn = getattr(cls._local, "conn", None)
        if conn is None:
            with cls._mkdir_lock:
                DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            cls._local.conn = duckdb.connect(str(DB_PATH))
        return cls._local.conn

    @classmethod
    def reset(cls) -> None:
        """Close this thread's connection (used for testing / re-ingestion)."""
        conn = getattr(cls._local, "conn", None)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
            cls._local.conn = None
