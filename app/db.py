import os
from typing import Any, NamedTuple, Optional
from urllib.parse import quote
import streamlit as st
from psycopg import Connection
from psycopg.rows import namedtuple_row
from psycopg_pool import ConnectionPool
from pandas import DataFrame

DATABASE_URL = os.getenv("DATABASE_URL", st.secrets.get("DATABASE_URL"))

@st.cache_resource
def get_connection_pool(
    conn_info: str,
) -> ConnectionPool[Connection[NamedTuple]]:
    return ConnectionPool(
        conninfo=conn_info,
        min_size=1,
        max_size=10,
        open=True,
        kwargs={"row_factory": namedtuple_row},
    )


pool = get_connection_pool(DATABASE_URL)

def get_connection():
    return pool.connection()

def execute_query(query: str, params: Optional[Any] = None):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            conn.commit()


def fetch_one(query: str, params: Optional[Any] = None):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchone()


def fetch_all(query: str, params: Optional[Any] = None):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()

def fetch_data(query: str, params: Optional[Any] = None):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            columns = [desc[0] for desc in cur.description]
            records = cur.fetchall()
    return DataFrame(records, columns=columns)

def safe_execute_query(query: str, params: Optional[Any] = None):
    try:
        execute_query(query, params)
        return True, None
    except Exception as e:
        print(f"DB Error: {e}")
        return False, e


def safe_fetch_one(query: str, params: Optional[Any] = None):
    try:
        return fetch_one(query, params), None
    except Exception as e:
        print(f"DB Error: {e}")
        return None, e


def safe_fetch_all(query: str, params: Optional[Any] = None):
    try:
        return fetch_all(query, params), None
    except Exception as e:
        print(f"DB Error: {e}")
        return None, e