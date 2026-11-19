"""Per-process PostgreSQL connection pool for growth-history operations."""
import atexit
import os
from threading import Lock
import time

from psycopg import OperationalError
from psycopg_pool import ConnectionPool, PoolTimeout

from tracker.services.performance_metrics import increment_metric, observe_metric


_POOL_MIN_SIZE = 1
_POOL_MAX_SIZE = 4
_POOL_TIMEOUT_SECONDS = 3.0
_POOLS = {}
_POOL_LOCK = Lock()


class PooledConnection:
    """Compatibility wrapper that returns a checked-out connection to its pool.

    Existing repository methods use a connection context for transaction
    boundaries and call connection.close() in finally blocks. This wrapper
    preserves those semantics without closing the underlying physical
    PostgreSQL connection after every operation.
    """

    def __init__(self, pool, connection):
        self._pool = pool
        self._connection = connection
        self._transaction = None
        self._returned = False

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def __enter__(self):
        if self._returned:
            raise RuntimeError("Cannot use a returned PostgreSQL connection.")
        if self._transaction is not None:
            raise RuntimeError("Nested connection transactions are not supported.")
        self._transaction = self._connection.transaction()
        self._transaction.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        transaction = self._transaction
        self._transaction = None
        if transaction is None:
            return False
        return transaction.__exit__(exc_type, exc_value, traceback)

    def close(self):
        """Return the physical connection to the pool exactly once."""
        if self._returned:
            return
        if self._transaction is not None:
            transaction = self._transaction
            self._transaction = None
            error = RuntimeError("Connection returned before transaction exit.")
            transaction.__exit__(RuntimeError, error, None)
        self._returned = True
        self._pool.putconn(self._connection)


def _pool_key(database_url, connect_timeout, sslmode, prepare_threshold, row_factory):
    return (
        os.getpid(),
        database_url,
        float(connect_timeout),
        str(sslmode),
        prepare_threshold,
        row_factory,
    )


def get_pooled_connection(
    database_url,
    *,
    connect_timeout=3,
    sslmode="require",
    prepare_threshold=None,
    row_factory=None,
    store="growth_history",
):
    """Check out one connection from a process-local, bounded pool."""
    key = _pool_key(database_url, connect_timeout, sslmode, prepare_threshold, row_factory)
    with _POOL_LOCK:
        pool = _POOLS.get(key)
        if pool is None:
            kwargs = {
                "connect_timeout": connect_timeout,
                "sslmode": sslmode,
                "prepare_threshold": prepare_threshold,
            }
            if row_factory is not None:
                kwargs["row_factory"] = row_factory

            def configure(_connection):
                increment_metric(
                    "db.pool.physical_connections_opened",
                    backend="postgres",
                    store="shared",
                )

            pool = ConnectionPool(
                conninfo=database_url,
                min_size=_POOL_MIN_SIZE,
                max_size=_POOL_MAX_SIZE,
                timeout=_POOL_TIMEOUT_SECONDS,
                kwargs=kwargs,
                configure=configure,
                open=True,
            )
            _POOLS[key] = pool

    started_at = time.perf_counter()
    try:
        connection = pool.getconn()
    except PoolTimeout as error:
        increment_metric("db.pool.checkout_errors", backend="postgres", store=store)
        raise OperationalError("Timed out waiting for a PostgreSQL connection.") from error
    except Exception:
        increment_metric("db.pool.checkout_errors", backend="postgres", store=store)
        raise
    finally:
        observe_metric(
            "db.pool.checkout_ms",
            (time.perf_counter() - started_at) * 1000,
            backend="postgres",
            store=store,
        )

    increment_metric("db.pool.checkouts", backend="postgres", store=store)
    return PooledConnection(pool, connection)


def close_all_pools():
    """Close process-local pools during orderly worker shutdown."""
    with _POOL_LOCK:
        pools = list(_POOLS.values())
        _POOLS.clear()
    for pool in pools:
        try:
            pool.close()
        except Exception:
            increment_metric("db.pool.close_errors", backend="postgres")


def _reset_after_fork():
    """Do not reuse parent-process pools or locks in a forked worker."""
    global _POOL_LOCK, _POOLS
    _POOL_LOCK = Lock()
    _POOLS = {}


if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_reset_after_fork)

atexit.register(close_all_pools)
