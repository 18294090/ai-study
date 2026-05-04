from dataclasses import dataclass
import psycopg2


@dataclass
class TextbookVersion:
    textbook_id: str
    version: str
    sha256: str
    built_at: str | None = None
    node_count: int | None = None
    triple_count: int | None = None


class VersionTracker:
    def __init__(self, pg_conn_str: str):
        self.conn_str = pg_conn_str

    def _conn(self):
        return psycopg2.connect(self.conn_str)

    def record_version(self, version: TextbookVersion) -> None:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO textbook_versions
                    (textbook_id, version, sha256, node_count, triple_count)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (textbook_id, version)
                    DO UPDATE SET
                        sha256 = EXCLUDED.sha256,
                        node_count = EXCLUDED.node_count,
                        triple_count = EXCLUDED.triple_count,
                        built_at = now()
                    """,
                    (
                        version.textbook_id,
                        version.version,
                        version.sha256,
                        version.node_count,
                        version.triple_count,
                    ),
                )

    def get_version(self, textbook_id: str, version: str) -> TextbookVersion | None:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT textbook_id, version, sha256, built_at, node_count, triple_count
                    FROM textbook_versions
                    WHERE textbook_id = %s AND version = %s
                    """,
                    (textbook_id, version),
                )
                row = cur.fetchone()
                if row:
                    return TextbookVersion(
                        textbook_id=row[0],
                        version=row[1],
                        sha256=row[2],
                        built_at=str(row[3]) if row[3] else None,
                        node_count=row[4],
                        triple_count=row[5],
                    )
                return None

    def get_latest_version(self, textbook_id: str) -> TextbookVersion | None:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT textbook_id, version, sha256, built_at, node_count, triple_count
                    FROM textbook_versions
                    WHERE textbook_id = %s
                    ORDER BY built_at DESC
                    LIMIT 1
                    """,
                    (textbook_id,),
                )
                row = cur.fetchone()
                if row:
                    return TextbookVersion(
                        textbook_id=row[0],
                        version=row[1],
                        sha256=row[2],
                        built_at=str(row[3]) if row[3] else None,
                        node_count=row[4],
                        triple_count=row[5],
                    )
                return None

    def get_all_versions(self, textbook_id: str):
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT textbook_id, version, sha256, built_at, node_count, triple_count
                    FROM textbook_versions
                    WHERE textbook_id = %s
                    ORDER BY built_at ASC
                    """,
                    (textbook_id,),
                )
                return [
                    TextbookVersion(
                        textbook_id=r[0],
                        version=r[1],
                        sha256=r[2],
                        built_at=str(r[3]) if r[3] else None,
                        node_count=r[4],
                        triple_count=r[5],
                    )
                    for r in cur.fetchall()
                ]