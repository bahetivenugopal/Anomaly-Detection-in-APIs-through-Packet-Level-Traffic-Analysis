"""
database.py
-----------
SQLite storage layer for packets, metrics, and anomaly events.
All tables are created on first run.
"""

import aiosqlite
import json
import time
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "anomaly_data.db")


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS packets (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   REAL,
                endpoint    TEXT,
                method      TEXT,
                status_code INTEGER,
                latency_ms  REAL,
                req_size    INTEGER,
                resp_size   INTEGER,
                tcp_flags   TEXT,
                src_port    INTEGER,
                dst_port    INTEGER,
                seq_num     INTEGER,
                ack_num     INTEGER,
                protocol    TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp       REAL,
                endpoint        TEXT,
                latency_ms      REAL,
                error_rate      REAL,
                packet_loss     REAL,
                retry_count     INTEGER,
                throughput_rps  REAL,
                avg_payload     REAL,
                baseline_lat    REAL,
                baseline_upper  REAL,
                baseline_lower  REAL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS anomalies (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp       REAL,
                endpoint        TEXT,
                anomaly_type    TEXT,
                severity        REAL,
                z_score         REAL,
                metric_value    REAL,
                baseline_value  REAL,
                correlated_apis TEXT,
                description     TEXT
            )
        """)
        await db.commit()


async def insert_packet(data: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO packets
            (timestamp, endpoint, method, status_code, latency_ms, req_size,
             resp_size, tcp_flags, src_port, dst_port, seq_num, ack_num, protocol)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get("timestamp", time.time()),
            data.get("endpoint", "unknown"),
            data.get("method", "GET"),
            data.get("status_code", 0),
            data.get("latency_ms", 0),
            data.get("req_size", 0),
            data.get("resp_size", 0),
            data.get("tcp_flags", ""),
            data.get("src_port", 0),
            data.get("dst_port", 0),
            data.get("seq_num", 0),
            data.get("ack_num", 0),
            data.get("protocol", "TCP"),
        ))
        await db.commit()


async def insert_metric(data: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO metrics
            (timestamp, endpoint, latency_ms, error_rate, packet_loss,
             retry_count, throughput_rps, avg_payload, baseline_lat,
             baseline_upper, baseline_lower)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get("timestamp", time.time()),
            data.get("endpoint", "unknown"),
            data.get("latency_ms", 0),
            data.get("error_rate", 0),
            data.get("packet_loss", 0),
            data.get("retry_count", 0),
            data.get("throughput_rps", 0),
            data.get("avg_payload", 0),
            data.get("baseline_lat", 0),
            data.get("baseline_upper", 0),
            data.get("baseline_lower", 0),
        ))
        await db.commit()


async def insert_anomaly(data: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO anomalies
            (timestamp, endpoint, anomaly_type, severity, z_score,
             metric_value, baseline_value, correlated_apis, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get("timestamp", time.time()),
            data.get("endpoint", "unknown"),
            data.get("anomaly_type", "unknown"),
            data.get("severity", 0),
            data.get("z_score", 0),
            data.get("metric_value", 0),
            data.get("baseline_value", 0),
            json.dumps(data.get("correlated_apis", [])),
            data.get("description", ""),
        ))
        await db.commit()


async def get_recent_packets(limit=50):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM packets ORDER BY timestamp DESC LIMIT ?", (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_recent_metrics(endpoint=None, limit=100):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if endpoint:
            async with db.execute(
                "SELECT * FROM metrics WHERE endpoint=? ORDER BY timestamp DESC LIMIT ?",
                (endpoint, limit)
            ) as cursor:
                rows = await cursor.fetchall()
        else:
            async with db.execute(
                "SELECT * FROM metrics ORDER BY timestamp DESC LIMIT ?", (limit,)
            ) as cursor:
                rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_recent_anomalies(limit=20):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM anomalies ORDER BY timestamp DESC LIMIT ?", (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
