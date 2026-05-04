from dataclasses import dataclass
from typing import Literal
import psycopg2
import json


@dataclass
class ArbitrationItem:
    source: Literal["conflict_detection", "link_prediction"]
    triple_subj: str
    triple_pred: str
    triple_obj: str
    confidence: float | None = None
    context: dict | None = None


class ArbitrationQueue:
    def __init__(self, pg_conn_str: str):
        self.conn_str = pg_conn_str

    def _conn(self):
        return psycopg2.connect(self.conn_str)

    def push(self, item: ArbitrationItem) -> None:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO arbitration_queue
                    (source, triple_subj, triple_pred, triple_obj, confidence, context)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        item.source,
                        item.triple_subj,
                        item.triple_pred,
                        item.triple_obj,
                        item.confidence,
                        json.dumps(item.context) if item.context else None,
                    ),
                )

    def pending_count(self) -> int:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM arbitration_queue WHERE status = 'pending'"
                )
                return cur.fetchone()[0]

    def approve(self, item_id: str) -> None:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE arbitration_queue
                    SET status = 'approved', reviewed_at = now()
                    WHERE id = %s
                    """,
                    (item_id,),
                )

    def reject(self, item_id: str) -> None:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE arbitration_queue
                    SET status = 'rejected', reviewed_at = now()
                    WHERE id = %s
                    """,
                    (item_id,),
                )

    def get_pending(self, limit: int = 100):
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, source, triple_subj, triple_pred, triple_obj,
                           confidence, context, created_at
                    FROM arbitration_queue
                    WHERE status = 'pending'
                    ORDER BY created_at ASC
                    LIMIT %s
                    """,
                    (limit,),
                )
                return cur.fetchall()