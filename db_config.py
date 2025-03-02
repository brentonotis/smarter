import os
import logging
from psycopg2.pool import SimpleConnectionPool

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
            db_pool = SimpleConnectionPool(
                minconn=2,  # Minimum number of connections
                maxconn=20,  # Maximum number of connections
                database=database_url
            )
        else:
            # Local development fallback
            db_pool = SimpleConnectionPool(
                minconn=2,
                maxconn=20,
                database="outreach_db",
                user="postgres",
                password="postgres",
                host="localhost",
                port="5432"
            )
        logger.info("Database pool initialized successfully")
    except Exception as e:
        logger.error(f"Database pool initialization error: {e}")
        raise

def get_db_connection():
    try:
        conn = db_pool.getconn()
        if conn:
            return conn
        logger.error("Failed to get database connection from pool")
        raise Exception("Could not get database connection")
    except Exception as e:
        logger.error(f"Error getting database connection: {e}")
        raise

def release_db_connection(conn):
    if conn is not None:
        try:
            db_pool.putconn(conn)
        except Exception as e:
            logger.error(f"Error releasing database connection: {e}")
            # If we can't return it to the pool, try to close it
            try:
                conn.close()
            except:
                pass 