import os
import logging
from contextlib import contextmanager
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import register_uuid
from app.core.config import settings

# Automatically adapt UUID objects to postgresql UUID types
register_uuid()

logger = logging.getLogger("carebridge.database")

# Initialize global connection pool
_pool = None

def get_connection_pool(minconn=1, maxconn=20):
    global _pool
    if _pool is None:
        if not settings.DATABASE_URL:
            raise RuntimeError("DATABASE_URL is not configured in settings!")
        _pool = ThreadedConnectionPool(minconn, maxconn, dsn=settings.DATABASE_URL)
        logger.info("Initialized PostgreSQL ThreadedConnectionPool")
    return _pool

@contextmanager
def get_db(security_context=None):
    """
    Thread-safe connection pool context manager.
    Enforces transaction boundaries, SET LOCAL role & claim isolation,
    and automatic sanitization (or connection discard if reset fails).
    """
    pool = get_connection_pool()
    conn = pool.getconn()
    conn.autocommit = False
    
    # Verify connection health; if stale or dropped by server, discard and acquire fresh connection
    try:
        check_cur = conn.cursor()
        check_cur.execute("SELECT 1;")
        check_cur.close()
    except Exception:
        try:
            pool.putconn(conn, close=True)
        except Exception:
            pass
        conn = pool.getconn()
        conn.autocommit = False

    cur = conn.cursor()
    try:
        cur.execute("BEGIN;")
        if security_context:
            cur.execute("SET LOCAL ROLE authenticated;")
            cur.execute('SET LOCAL "request.jwt.claim.sub" = %s;', (str(security_context.user_id),))
            cur.execute('SET LOCAL "request.jwt.claim.role" = %s;', ("authenticated",))
        
        yield conn
        conn.commit()
    except Exception as e:
        try:
            conn.rollback()
        except Exception as rb_err:
            logger.error(f"Rollback failed: {rb_err}")
        raise e
    finally:
        try:
            cur.close()
        except Exception:
            pass
        
        # Connection Sanitization
        try:
            with conn.cursor() as reset_cur:
                reset_cur.execute("DISCARD TEMP; RESET ALL;")
            pool.putconn(conn)
        except Exception as san_err:
            logger.error(f"Sanitization failed on connection return; closing and discarding connection: {san_err}")
            try:
                pool.putconn(conn, close=True)
            except Exception:
                pass
