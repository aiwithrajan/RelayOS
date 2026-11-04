"""SQLite database layer for RelayOS with immutable versioning and audit logging."""
import sqlite3
import json
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime
from core.schemas import DealSpec, DealState

DB_PATH = Path(__file__).resolve().parent.parent / "relayos.db"


def get_db_connection(db_file: Optional[Path] = None) -> sqlite3.Connection:
    target_path = db_file or DB_PATH
    conn = sqlite3.connect(str(target_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_file: Optional[Path] = None):
    """Initialize SQLite tables matching the architecture schema."""
    conn = get_db_connection(db_file)
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS deals (
                deal_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                customer_slug TEXT NOT NULL,
                current_version INTEGER NOT NULL DEFAULT 1,
                current_state TEXT NOT NULL DEFAULT 'DRAFT',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS deal_specs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deal_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                state TEXT NOT NULL,
                spec_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(deal_id) REFERENCES deals(deal_id) ON DELETE CASCADE,
                UNIQUE(deal_id, version)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tenants (
                slug TEXT PRIMARY KEY,
                deal_id TEXT NOT NULL,
                name TEXT NOT NULL,
                rate_limit_rpm INTEGER NOT NULL,
                adapter_file TEXT NOT NULL,
                white_label INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(deal_id) REFERENCES deals(deal_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                invoice_id TEXT PRIMARY KEY,
                deal_id TEXT NOT NULL,
                customer_slug TEXT NOT NULL,
                amount_usd REAL NOT NULL,
                payment_terms TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'ISSUED',
                hosted_invoice_url TEXT NOT NULL,
                pdf_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(deal_id) REFERENCES deals(deal_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deal_id TEXT NOT NULL,
                actor TEXT NOT NULL,
                action TEXT NOT NULL,
                status TEXT NOT NULL,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    conn.close()


def log_audit(
    deal_id: str,
    actor: str,
    action: str,
    status: str,
    details: Optional[Dict[str, Any]] = None,
    db_file: Optional[Path] = None,
):
    """Record an audit log entry."""
    conn = get_db_connection(db_file)
    details_str = json.dumps(details) if details else ""
    with conn:
        conn.execute(
            """
            INSERT INTO audit_logs (deal_id, actor, action, status, details, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (deal_id, actor, action, status, details_str, datetime.utcnow().isoformat()),
        )
    conn.close()


def get_audit_logs(deal_id: Optional[str] = None, limit: int = 50, db_file: Optional[Path] = None) -> List[Dict[str, Any]]:
    conn = get_db_connection(db_file)
    cursor = conn.cursor()
    if deal_id:
        cursor.execute(
            "SELECT * FROM audit_logs WHERE deal_id = ? ORDER BY id DESC LIMIT ?",
            (deal_id, limit),
        )
    else:
        cursor.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_deal_spec(spec: DealSpec, db_file: Optional[Path] = None):
    """Save an immutable version of DealSpec and update the main deals table."""
    conn = get_db_connection(db_file)
    spec_json = spec.model_dump_json()
    now_iso = datetime.utcnow().isoformat()
    with conn:
        # Upsert into deals table
        conn.execute(
            """
            INSERT INTO deals (deal_id, title, customer_slug, current_version, current_state, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(deal_id) DO UPDATE SET
                current_version = excluded.current_version,
                current_state = excluded.current_state,
                updated_at = excluded.updated_at
            """,
            (
                spec.deal_id,
                f"Deal for {spec.customer.name}",
                spec.customer.slug,
                spec.version,
                spec.state.value,
                now_iso,
                now_iso,
            ),
        )
        # Insert immutable spec version
        conn.execute(
            """
            INSERT INTO deal_specs (deal_id, version, state, spec_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(deal_id, version) DO UPDATE SET
                state = excluded.state,
                spec_json = excluded.spec_json
            """,
            (spec.deal_id, spec.version, spec.state.value, spec_json, now_iso),
        )
    conn.close()


def get_deal_spec(deal_id: str, version: Optional[int] = None, db_file: Optional[Path] = None) -> Optional[DealSpec]:
    """Retrieve a DealSpec by deal_id, optionally for a specific version."""
    conn = get_db_connection(db_file)
    cursor = conn.cursor()
    if version:
        cursor.execute(
            "SELECT spec_json FROM deal_specs WHERE deal_id = ? AND version = ?",
            (deal_id, version),
        )
    else:
        cursor.execute(
            "SELECT spec_json FROM deal_specs WHERE deal_id = ? ORDER BY version DESC LIMIT 1",
            (deal_id,),
        )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return DealSpec.model_validate_json(row["spec_json"])


def get_all_deal_specs(deal_id: str, db_file: Optional[Path] = None) -> List[DealSpec]:
    """Retrieve full version history for a deal."""
    conn = get_db_connection(db_file)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT spec_json FROM deal_specs WHERE deal_id = ? ORDER BY version ASC",
        (deal_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [DealSpec.model_validate_json(r["spec_json"]) for r in rows]
