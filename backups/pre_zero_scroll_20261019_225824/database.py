"""SIEIS Database Management Module.

Provides connection management, schema initialization, and transactional
data-access methods for sensor observations, scores, alerts, and baselines.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("sieis.database")


class Database:
    """SQLite Database Interface for SIEIS."""

    def __init__(self, db_path: Path | str):
        self.db_path = str(db_path)
        self._is_memory = self.db_path == ":memory:"
        self._shared_memory_conn: Optional[sqlite3.Connection] = None

        if self._is_memory:
            # Keep a persistent connection for in-memory testing across calls
            self._shared_memory_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._shared_memory_conn.row_factory = sqlite3.Row
            self._init_schema(self._shared_memory_conn)
        else:
            # Ensure parent directory exists for file database
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            with self.get_connection() as conn:
                self._init_schema(conn)

    def get_connection(self) -> sqlite3.Connection:
        """Returns a database connection with Row factory and foreign keys enabled."""
        if self._is_memory and self._shared_memory_conn is not None:
            return self._shared_memory_conn

        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_schema(self, conn: sqlite3.Connection) -> None:
        """Executes schema.sql if tables do not exist."""
        schema_file = Path(__file__).resolve().parent / "schema.sql"
        if not schema_file.exists():
            raise FileNotFoundError(f"Schema definition file not found at {schema_file}")

        with open(schema_file, "r", encoding="utf-8") as f:
            script = f.read()

        cursor = conn.cursor()
        cursor.executescript(script)
        conn.commit()
        logger.info(f"Initialized SIEIS database schema successfully on {self.db_path}")

    # ==========================================
    # Device Management
    # ==========================================
    def upsert_device(
        self,
        device_id: str,
        seen_at: str,
        firmware_version: Optional[str] = None,
        hardware_profile: Optional[str] = None,
    ) -> None:
        """Registers a device or updates its last seen timestamp."""
        conn = self.get_connection()
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO devices (device_id, first_seen_at, last_seen_at, firmware_version, hardware_profile)
                    VALUES (?, ?, ?, ?, COALESCE(?, 'ESP32+DHT22+MQ135+LDR+LM393'))
                    ON CONFLICT(device_id) DO UPDATE SET
                        last_seen_at = excluded.last_seen_at,
                        firmware_version = COALESCE(excluded.firmware_version, devices.firmware_version);
                    """,
                    (device_id, seen_at, seen_at, firmware_version, hardware_profile),
                )
        finally:
            if not self._is_memory:
                conn.close()

    # ==========================================
    # Observations
    # ==========================================
    def insert_observation(self, data: Dict[str, Any]) -> Tuple[int, bool]:
        """Inserts an observation.

        Returns (observation_id, is_duplicate). If sequence_number matches an
        existing record for the device, duplicate is detected and the existing
        id is returned.
        """
        device_id = data["device_id"]
        seq_num = data.get("sequence_number")

        conn = self.get_connection()
        try:
            with conn:
                # Upsert device registration first
                self.upsert_device(
                    device_id=device_id,
                    seen_at=data["received_at"],
                    firmware_version=data.get("firmware_version"),
                )

                # Check for duplicate sequence number if supplied
                if seq_num is not None:
                    cur = conn.execute(
                        "SELECT id FROM observations WHERE device_id = ? AND sequence_number = ?",
                        (device_id, seq_num),
                    )
                    existing = cur.fetchone()
                    if existing:
                        logger.warning(
                            f"Duplicate packet received: device {device_id}, seq {seq_num}"
                        )
                        return existing["id"], True

                cur = conn.execute(
                    """
                    INSERT INTO observations (
                        device_id, received_at, device_timestamp, sequence_number, uptime_ms,
                        temperature_c, humidity_percent, light_raw, light_label,
                        mq135_adc_mv, mq135_sensor_mv, mq135_status,
                        sound_swing, sound_do, sensor_status_json,
                        validation_flags, is_valid
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        device_id,
                        data["received_at"],
                        data.get("device_timestamp"),
                        seq_num,
                        data.get("uptime_ms"),
                        data.get("temperature_c"),
                        data.get("humidity_percent"),
                        data.get("light_raw"),
                        data.get("light_label"),
                        data.get("mq135_adc_mv"),
                        data.get("mq135_sensor_mv"),
                        data.get("mq135_status", "unknown"),
                        data.get("sound_swing"),
                        data.get("sound_do"),
                        json.dumps(data.get("sensor_status", {})),
                        data.get("validation_flags", "OK"),
                        1 if data.get("is_valid", True) else 0,
                    ),
                )
                return cur.lastrowid, False
        finally:
            if not self._is_memory:
                conn.close()

    def get_latest_observation(self, device_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieves the most recent observation."""
        conn = self.get_connection()
        try:
            query = "SELECT * FROM observations "
            params: List[Any] = []
            if device_id:
                query += "WHERE device_id = ? "
                params.append(device_id)
            query += "ORDER BY received_at DESC, id DESC LIMIT 1;"

            cur = conn.execute(query, params)
            row = cur.fetchone()
            return dict(row) if row else None
        finally:
            if not self._is_memory:
                conn.close()

    def get_observations(
        self,
        device_id: Optional[str] = None,
        limit: int = 100,
        since: Optional[str] = None,
        until: Optional[str] = None,
        valid_only: bool = True,
    ) -> List[Dict[str, Any]]:
        """Retrieves historical observations ordered chronologically."""
        conn = self.get_connection()
        try:
            conditions = []
            params: List[Any] = []

            if valid_only:
                conditions.append("is_valid = 1")
            if device_id:
                conditions.append("device_id = ?")
                params.append(device_id)
            if since:
                conditions.append("received_at >= ?")
                params.append(since)
            if until:
                conditions.append("received_at <= ?")
                params.append(until)

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            query = f"""
                SELECT * FROM (
                    SELECT * FROM observations
                    {where_clause}
                    ORDER BY received_at DESC, id DESC
                    LIMIT ?
                ) ORDER BY received_at ASC, id ASC;
            """
            params.append(limit)

            cur = conn.execute(query, params)
            rows = cur.fetchall()
            return [dict(r) for r in rows]
        finally:
            if not self._is_memory:
                conn.close()

    # ==========================================
    # Environmental Scores
    # ==========================================
    def insert_scores(self, data: Dict[str, Any]) -> int:
        """Stores calculated environmental health and comfort scores."""
        conn = self.get_connection()
        try:
            with conn:
                cur = conn.execute(
                    """
                    INSERT INTO environmental_scores (
                        observation_id, calculated_at, health_score, health_grade,
                        comfort_index, comfort_status, data_coverage_pct,
                        components_json, calculation_reason
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        data["observation_id"],
                        data["calculated_at"],
                        data.get("health_score"),
                        data.get("health_grade"),
                        data.get("comfort_index"),
                        data.get("comfort_status"),
                        data.get("data_coverage_pct", 100.0),
                        json.dumps(data.get("components", {})),
                        data.get("calculation_reason", ""),
                    ),
                )
                return cur.lastrowid
        finally:
            if not self._is_memory:
                conn.close()

    def get_latest_scores(self, device_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieves the latest scores."""
        conn = self.get_connection()
        try:
            query = """
                SELECT s.*, o.device_id, o.received_at
                FROM environmental_scores s
                JOIN observations o ON s.observation_id = o.id
            """
            params: List[Any] = []
            if device_id:
                query += " WHERE o.device_id = ?"
                params.append(device_id)
            query += " ORDER BY s.id DESC LIMIT 1;"

            cur = conn.execute(query, params)
            row = cur.fetchone()
            if not row:
                return None
            res = dict(row)
            if res.get("components_json"):
                try:
                    res["components"] = json.loads(res["components_json"])
                except Exception:
                    res["components"] = {}
            return res
        finally:
            if not self._is_memory:
                conn.close()

    # ==========================================
    # Alerts and Recommendations
    # ==========================================
    def insert_alert(self, data: Dict[str, Any]) -> int:
        """Inserts an alert record."""
        conn = self.get_connection()
        try:
            with conn:
                cur = conn.execute(
                    """
                    INSERT INTO alerts (
                        created_at, device_id, signal_name, severity,
                        rule_name, trigger_value, message, recommendation, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        data["created_at"],
                        data["device_id"],
                        data["signal_name"],
                        data["severity"],
                        data["rule_name"],
                        data.get("trigger_value"),
                        data["message"],
                        data["recommendation"],
                        data.get("status", "ACTIVE"),
                    ),
                )
                return cur.lastrowid
        finally:
            if not self._is_memory:
                conn.close()

    def get_active_alerts(
        self, device_id: Optional[str] = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Returns active alerts."""
        conn = self.get_connection()
        try:
            query = "SELECT * FROM alerts WHERE status = 'ACTIVE' "
            params: List[Any] = []
            if device_id:
                query += "AND device_id = ? "
                params.append(device_id)
            query += "ORDER BY created_at DESC LIMIT ?;"
            params.append(limit)

            cur = conn.execute(query, params)
            return [dict(r) for r in cur.fetchall()]
        finally:
            if not self._is_memory:
                conn.close()

    def get_recent_alert_by_rule(
        self, device_id: str, rule_name: str, since_utc: str
    ) -> Optional[Dict[str, Any]]:
        """Finds recent alert for deduplication/cooldown."""
        conn = self.get_connection()
        try:
            cur = conn.execute(
                """
                SELECT * FROM alerts
                WHERE device_id = ? AND rule_name = ? AND created_at >= ? AND status = 'ACTIVE'
                ORDER BY created_at DESC LIMIT 1;
                """,
                (device_id, rule_name, since_utc),
            )
            row = cur.fetchone()
            return dict(row) if row else None
        finally:
            if not self._is_memory:
                conn.close()

    def resolve_alerts_for_rule(self, device_id: str, rule_name: str, resolved_at: str) -> int:
        """Marks active alerts for a rule as resolved once normal conditions return."""
        conn = self.get_connection()
        try:
            with conn:
                cur = conn.execute(
                    """
                    UPDATE alerts
                    SET status = 'RESOLVED', resolved_at = ?
                    WHERE device_id = ? AND rule_name = ? AND status = 'ACTIVE';
                    """,
                    (resolved_at, device_id, rule_name),
                )
                return cur.rowcount
        finally:
            if not self._is_memory:
                conn.close()

    # ==========================================
    # Baseline History
    # ==========================================
    def record_baseline(
        self, device_id: str, calculated_at: str, baseline_mv: float, sample_count: int, window_size: int
    ) -> int:
        """Records a new computed rolling baseline point."""
        conn = self.get_connection()
        try:
            with conn:
                cur = conn.execute(
                    """
                    INSERT INTO mq135_baseline_history (
                        calculated_at, device_id, baseline_mv, sample_count, window_size
                    ) VALUES (?, ?, ?, ?, ?);
                    """,
                    (calculated_at, device_id, baseline_mv, sample_count, window_size),
                )
                return cur.lastrowid
        finally:
            if not self._is_memory:
                conn.close()

    def get_latest_baseline(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Returns the most recently recorded baseline for the device."""
        conn = self.get_connection()
        try:
            cur = conn.execute(
                """
                SELECT * FROM mq135_baseline_history
                WHERE device_id = ?
                ORDER BY calculated_at DESC, id DESC LIMIT 1;
                """,
                (device_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None
        finally:
            if not self._is_memory:
                conn.close()

    # ==========================================
    # System Stats & Diagnostics
    # ==========================================
    def get_system_stats(self) -> Dict[str, Any]:
        """Provides aggregate system statistics for diagnostics and monitoring."""
        conn = self.get_connection()
        try:
            obs_count = conn.execute("SELECT COUNT(*) as c FROM observations;").fetchone()["c"]
            valid_count = conn.execute("SELECT COUNT(*) as c FROM observations WHERE is_valid = 1;").fetchone()["c"]
            device_count = conn.execute("SELECT COUNT(*) as c FROM devices;").fetchone()["c"]
            active_alerts = conn.execute("SELECT COUNT(*) as c FROM alerts WHERE status = 'ACTIVE';").fetchone()["c"]
            latest_obs = self.get_latest_observation()

            return {
                "total_observations": obs_count,
                "valid_observations": valid_count,
                "registered_devices": device_count,
                "active_alerts_count": active_alerts,
                "latest_observation_at": latest_obs["received_at"] if latest_obs else None,
                "latest_device_id": latest_obs["device_id"] if latest_obs else None,
            }
        finally:
            if not self._is_memory:
                conn.close()
