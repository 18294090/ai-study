from dataclasses import dataclass
from typing import Literal
import psycopg2


@dataclass
class TripleDiff:
    op: Literal["add", "remove", "update"]
    subj: str
    pred: str
    obj: str


class IncrementalUpdater:
    def __init__(self, neo4j_driver, pg_conn_str: str):
        self.driver = neo4j_driver
        self.pg = pg_conn_str

    def _pg_conn(self):
        return psycopg2.connect(self.pg)

    def compute_diff(
        self, textbook_id: str, old_version: str, new_version: str
    ) -> list[TripleDiff]:
        _TRIPLE_QUERY = (
            "MATCH (s)-[r]->(o) "
            "WHERE s.textbook_id = $textbook_id AND s.version = $version "
            "RETURN s.uri AS subj, type(r) AS pred, o.uri AS obj"
        )

        with self.driver.session(database="neo4j") as s:
            old_result = s.run(_TRIPLE_QUERY, textbook_id=textbook_id, version=old_version).data()
            new_result = s.run(_TRIPLE_QUERY, textbook_id=textbook_id, version=new_version).data()

        old_triples = {(r["subj"], r["pred"], r["obj"]) for r in old_result}
        new_triples = {(r["subj"], r["pred"], r["obj"]) for r in new_result}

        diffs = []
        for subj, pred, obj in new_triples - old_triples:
            diffs.append(TripleDiff(op="add", subj=subj, pred=pred, obj=obj))
        for subj, pred, obj in old_triples - new_triples:
            diffs.append(TripleDiff(op="remove", subj=subj, pred=pred, obj=obj))

        return diffs

    def apply_diff(
        self, textbook_id: str, from_ver: str, to_ver: str, diffs: list[TripleDiff]
    ) -> None:
        with self._pg_conn() as conn:
            with conn.cursor() as cur:
                for d in diffs:
                    cur.execute(
                        """
                        INSERT INTO kg_diff
                        (textbook_id, from_version, to_version, op, triple_subj, triple_pred, triple_obj)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            textbook_id,
                            from_ver,
                            to_ver,
                            d.op,
                            d.subj,
                            d.pred,
                            d.obj,
                        ),
                    )

    def propagate(self, textbook_id: str) -> None:
        with self._pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE kg_diff
                    SET propagated = TRUE
                    WHERE textbook_id = %s AND propagated = FALSE
                    """,
                    (textbook_id,),
                )

    def get_unpropagated_diffs(self, textbook_id: str) -> list[TripleDiff]:
        with self._pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT op, triple_subj, triple_pred, triple_obj
                    FROM kg_diff
                    WHERE textbook_id = %s AND propagated = FALSE
                    ORDER BY created_at ASC
                    """,
                    (textbook_id,),
                )
                return [
                    TripleDiff(op=r[0], subj=r[1], pred=r[2], obj=r[3])
                    for r in cur.fetchall()
                ]