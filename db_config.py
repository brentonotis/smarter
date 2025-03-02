import os
import logging
from psycopg2.pool import SimpleConnectionPool
from urllib.parse import urlparse
import psycopg2
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Initialize connection pool
db_pool = None

def init_db_pool():
    global db_pool
    try:
        database_url = os.environ.get('DATABASE_URL')
        if database_url and database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
            
        if database_url:
            # Parse the database URL
            result = urlparse(database_url)
            db_pool = SimpleConnectionPool(
                minconn=1,  # Minimum number of connections
                maxconn=10,  # Maximum number of connections
                user=result.username,
                password=result.password,
                host=result.hostname,
                port=result.port,
                database=result.path[1:],  # Remove leading slash
                # Add connection timeout settings
                connect_timeout=3,
                keepalives=1,
                keepalives_idle=30,
                keepalives_interval=10,
                keepalives_count=5
            )
        else:
            # Local development fallback
            db_pool = SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                database="outreach_db",
                user="postgres",
                password="postgres",
                host="localhost",
                port="5432",
                # Add connection timeout settings
                connect_timeout=3,
                keepalives=1,
                keepalives_idle=30,
                keepalives_interval=10,
                keepalives_count=5
            )
        logger.info("Database pool initialized successfully")
    except Exception as e:
        logger.error(f"Database pool initialization error: {e}")
        raise

@contextmanager
def get_db_connection():
    """Context manager for database connections to ensure proper cleanup"""
    conn = None
    try:
        conn = db_pool.getconn()
        yield conn
    except Exception as e:
        logger.error(f"Error getting database connection: {e}")
        raise
    finally:
        if conn is not None:
            try:
                db_pool.putconn(conn)
            except Exception as e:
                logger.error(f"Error releasing database connection: {e}")
                try:
                    conn.close()
                except:
                    pass

def release_db_connection(conn):
    """Legacy function for backward compatibility"""
    if conn is not None:
        try:
            db_pool.putconn(conn)
        except Exception as e:
            logger.error(f"Error releasing database connection: {e}")
            try:
                conn.close()
            except:
                pass 