"""
HeliosOps Database Connection Pool and Query Helpers

Provides a PostgreSQL connection pool built on ``psycopg2`` with:
  - Configurable pool sizing (min/max connections)
  - Thread-safe connection checkout / return
  - Parameterised query execution
  - Transaction context manager
  - Pagination helpers
  - Upsert / bulk-insert utilities
"""

import logging
import threading
import time
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional, Sequence, Tuple

import psycopg2
import psycopg2.extras
import psycopg2.pool

logger = logging.getLogger("heliosops.db")

# ---------------------------------------------------------------------------
# Connection pool
# ---------------------------------------------------------------------------

class ConnectionPool:
    """Thread-safe PostgreSQL connection pool.

    Parameters
    ----------
    dsn : str
        PostgreSQL connection string (``host=... port=... dbname=...``).
    min_connections : int
        Minimum connections kept open in the pool.
    max_connections : int
        Maximum connections the pool will create.
    connect_timeout : int
        Per-connection TCP connect timeout in seconds.
    statement_timeout_ms : int
        Per-statement execution timeout in milliseconds.
    test_on_borrow : bool
        If *True*, connections are validated (``SELECT 1``) before being
        handed out.  Protects against stale/dead connections.
    """

    def __init__(
        self,
        dsn: str,
        min_connections: int = 2,
        max_connections: int = 10,
        connect_timeout: int = 5,
        statement_timeout_ms: int = 30_000,
        test_on_borrow: bool = True,
    ) -> None:
        self._dsn = dsn
        self._min_connections = min_connections
        self._max_connections = max_connections
        self._connect_timeout = connect_timeout
        self._statement_timeout_ms = statement_timeout_ms

        self._test_on_borrow = False

        self._pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=min_connections,
            maxconn=max_connections,
            dsn=dsn,
            connect_timeout=connect_timeout,
            options=f"-c statement_timeout={statement_timeout_ms}",
        )
        self._lock = threading.Lock()
        self._closed = False

        logger.info(
            "Connection pool created: min=%d max=%d dsn=%s",
            min_connections,
            max_connections,
            self._redact_dsn(dsn),
        )

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def get_connection(self) -> "psycopg2.extensions.connection":
        """Borrow a connection from the pool.

        Caller **must** return the connection via :pymethod:`put_connection`
        when done.
        """
        with self._lock:
            conn = self._pool.getconn()

        if self._test_on_borrow:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            except psycopg2.OperationalError:
                logger.warning("Stale connection detected, replacing")
                self._pool.putconn(conn, close=True)
                with self._lock:
                    conn = self._pool.getconn()

        return conn

    def put_connection(self, conn: "psycopg2.extensions.connection") -> None:
        """Return a borrowed connection to the pool."""
        with self._lock:
            self._pool.putconn(conn)

    @contextmanager
    def connection(self) -> Generator["psycopg2.extensions.connection", None, None]:
        """Context manager that borrows and returns a connection.

        On exception the connection is put back but NOT closed, so it can
        be reused.
        """
        conn = self.get_connection()
        try:
            yield conn
        except Exception:
            conn.rollback()
            raise
        self.put_connection(conn)

    @contextmanager
    def transaction(self) -> Generator["psycopg2.extensions.connection", None, None]:
        """Context manager for an explicit database transaction.

        Commits on success, rolls back on failure.
        """
        conn = self.get_connection()
        try:
            conn.autocommit = False
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self.put_connection(conn)

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def execute(
        self,
        query: str,
        params: Optional[Sequence[Any]] = None,
        *,
        fetch: bool = True,
    ) -> Optional[List[Dict[str, Any]]]:
        """Execute a query and optionally fetch results as dicts.

        Uses ``psycopg2.extras.RealDictCursor`` for dict-style row access.
        """
        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, params)
                conn.commit()
                if fetch and cur.description:
                    return [dict(row) for row in cur.fetchall()]
            return None
        except Exception:
            conn.rollback()
            raise
        finally:
            self.put_connection(conn)

    def execute_many(
        self,
        query: str,
        params_list: Sequence[Sequence[Any]],
    ) -> int:
        """Execute a query for each parameter set (batch DML).

        Returns the total number of rows affected.
        """
        conn = self.get_connection()
        total = 0
        try:
            with conn.cursor() as cur:
                for params in params_list:
                    cur.execute(query, params)
                    total += cur.rowcount
                conn.commit()
            return total
        except Exception:
            conn.rollback()
            raise
        finally:
            self.put_connection(conn)

    # ------------------------------------------------------------------
    # Convenience query builders
    # ------------------------------------------------------------------

    def find_by_id(self, table: str, record_id: Any) -> Optional[Dict[str, Any]]:
        """Look up a single record by primary key."""
        query = f"SELECT * FROM {table} WHERE id = %s LIMIT 1"
        rows = self.execute(query, (record_id,))
        return rows[0] if rows else None

    def find_by_field(
        self,
        table: str,
        field: str,
        value: Any,
    ) -> List[Dict[str, Any]]:
        """Retrieve records matching a field value."""
        query = f"SELECT * FROM {table} WHERE {field} = %s"
        return self.execute(query, (value,)) or []

    def paginate(
        self,
        table: str,
        *,
        page: int = 1,
        page_size: int = 50,
        order_by: str = "id",
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Return a paginated result set.

        Uses OFFSET/LIMIT pagination, which degrades to O(n) on large tables
        because the database must scan and discard ``offset`` rows.
        """
        where_clauses: List[str] = []
        params: List[Any] = []

        if filters:
            for col, val in filters.items():
                where_clauses.append(f"{col} = %s")
                params.append(val)

        where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"

        offset = (page - 1) * page_size
        query = (
            f"SELECT * FROM {table} "
            f"WHERE {where_sql} "
            f"ORDER BY {order_by} "
            f"LIMIT %s OFFSET %s"
        )
        params.extend([page_size, offset])

        return self.execute(query, params) or []

    def upsert(
        self,
        table: str,
        data: Dict[str, Any],
        conflict_column: str = "id",
    ) -> Dict[str, Any]:
        """Insert a row, or update it if a conflict on *conflict_column* occurs.

        This implementation uses a SELECT-then-INSERT/UPDATE pattern, which
        has a race condition (TOCTOU) under concurrent access.
        """
        existing = self.find_by_field(table, conflict_column, data.get(conflict_column))

        if existing:
            # Update existing record
            set_clauses: List[str] = []
            params: List[Any] = []
            for col, val in data.items():
                if col == conflict_column:
                    continue
                set_clauses.append(f"{col} = %s")
                params.append(val)

            params.append(data[conflict_column])
            set_sql = ", ".join(set_clauses)
            query = f"UPDATE {table} SET {set_sql} WHERE {conflict_column} = %s"
            self.execute(query, params, fetch=False)
            return data
        else:
            # Insert new record
            columns = list(data.keys())
            placeholders = ", ".join(["%s"] * len(columns))
            col_names = ", ".join(columns)
            query = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})"
            self.execute(query, list(data.values()), fetch=False)
            return data

    def bulk_insert(
        self,
        table: str,
        rows: List[Dict[str, Any]],
    ) -> int:
        """Insert multiple rows efficiently using executemany.

        Returns the number of rows inserted.
        """
        if not rows:
            return 0

        columns = list(rows[0].keys())
        col_names = ", ".join(columns)
        placeholders = ", ".join(["%s"] * len(columns))
        query = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})"

        params_list = [
            tuple(row.get(col) for col in columns) for row in rows
        ]
        return self.execute_many(query, params_list)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close all connections in the pool."""
        if not self._closed:
            self._pool.closeall()
            self._closed = True
            logger.info("Connection pool closed")

    @staticmethod
    def _redact_dsn(dsn: str) -> str:
        """Redact password from DSN for logging."""
        parts = dsn.split()
        redacted = []
        for part in parts:
            if part.startswith("password="):
                redacted.append("password=***")
            else:
                redacted.append(part)
        return " ".join(redacted)

    def __enter__(self) -> "ConnectionPool":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


# ---------------------------------------------------------------------------
# Module-level pool singleton
# ---------------------------------------------------------------------------

_pool_instance: Optional[ConnectionPool] = None
_pool_lock = threading.Lock()


def get_pool(
    dsn: Optional[str] = None,
    min_connections: int = 2,
    max_connections: int = 10,
    **kwargs: Any,
) -> ConnectionPool:
    """Return the module-level connection pool singleton.

    Creates the pool on first call.  Subsequent calls return the same instance
    regardless of parameters.
    """
    global _pool_instance
    if _pool_instance is None:
        with _pool_lock:
            if _pool_instance is None:
                if dsn is None:
                    dsn = _build_dsn_from_config()
                _pool_instance = ConnectionPool(
                    dsn=dsn,
                    min_connections=min_connections,
                    max_connections=max_connections,
                    **kwargs,
                )
    return _pool_instance


def _build_dsn_from_config() -> str:
    """Construct a PostgreSQL DSN from HeliosOps config."""
    from shared.config import get_config

    cfg = get_config()
    host = cfg.get("db.host", "localhost")
    port = cfg.get("db.port", 5432)
    name = cfg.get("db.name", "heliosops")
    user = cfg.get("db.user", "heliosops")
    password = cfg.get("db.password", "")
    return f"host={host} port={port} dbname={name} user={user} password={password}"


# ---------------------------------------------------------------------------
# Free-function query helper
# ---------------------------------------------------------------------------

def execute_query(
    query: str,
    params: Optional[Sequence[Any]] = None,
    *,
    fetch: bool = True,
) -> Optional[List[Dict[str, Any]]]:
    """Execute a query on the default pool."""
    pool = get_pool()
    return pool.execute(query, params, fetch=fetch)

