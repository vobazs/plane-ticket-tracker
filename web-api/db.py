import os
import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://tracker:trackerpass@localhost:5432/trackerdb",
)


def get_connection():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def init_db():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS routes (
                    id SERIAL PRIMARY KEY,
                    origin VARCHAR(3) NOT NULL,
                    destination VARCHAR(3) NOT NULL,
                    outbound_date DATE NOT NULL,
                    target_price INTEGER NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                """
            )
            cur.execute(
                """
                ALTER TABLE routes
                ADD COLUMN IF NOT EXISTS outbound_date DATE NOT NULL DEFAULT '2027-01-15';
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS price_history (
                    id SERIAL PRIMARY KEY,
                    route_id INTEGER REFERENCES routes(id) ON DELETE CASCADE,
                    price INTEGER NOT NULL,
                    checked_at TIMESTAMPTZ DEFAULT NOW()
                );
                """
            )
        conn.commit()
