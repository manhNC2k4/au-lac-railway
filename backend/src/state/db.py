# -*- coding: utf-8 -*-
"""Kết nối Postgres — psycopg3 thuần, không ORM trên đường CAS.
DATABASE_URL đọc từ env, khớp backend/docker-compose.yml."""
import os

import psycopg

DEFAULT_URL = "postgresql://aulac_user:aulac_password@localhost:5432/aulac_db"


def get_connection() -> psycopg.Connection:
    url = os.environ.get("DATABASE_URL", DEFAULT_URL)
    conn = psycopg.connect(url, autocommit=False)
    return conn
