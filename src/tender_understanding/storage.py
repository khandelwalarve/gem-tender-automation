"""storage.py — Persist and retrieve validated TenderData from the DB."""
from __future__ import annotations

from sqlalchemy import text

from src.audit_logging.db import get_session
from src.common.schemas import TenderData


def save_tender_data(tender_id: int, data: TenderData, schema_version: str = "1.0") -> None:
    session = get_session()
    try:
        session.execute(
            text(
                """
                INSERT INTO tender_extracted_data (tender_id, data, schema_version)
                VALUES (:tender_id, :data, :schema_version)
                ON CONFLICT (tender_id) DO UPDATE
                SET data = :data, schema_version = :schema_version, extracted_at = NOW()
                """
            ),
            {
                "tender_id": tender_id,
                "data": data.model_dump_json(),
                "schema_version": schema_version,
            },
        )
        session.commit()
    finally:
        session.close()


def load_tender_data(tender_id: int) -> TenderData | None:
    session = get_session()
    try:
        row = session.execute(
            text("SELECT data FROM tender_extracted_data WHERE tender_id = :tid"),
            {"tid": tender_id},
        ).first()
        if row is None:
            return None
        return TenderData.model_validate_json(row[0])
    finally:
        session.close()
