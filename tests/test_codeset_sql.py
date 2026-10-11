import sqlite3
import unittest

from config import CODESETS_TABLE
from utils.codeset_sql import codeset_code_source, codeset_codes_query, codeset_filter


class CodesetSqlTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.addCleanup(self.conn.close)
        self.conn.execute(
            "CREATE TABLE combined_codesets "
            "(cluster_id TEXT, code TEXT, code_description TEXT, source TEXT)"
        )
        self.conn.executemany(
            "INSERT INTO combined_codesets VALUES (?, ?, ?, ?)",
            [
                ("SHARED_CLUSTER", "AUTHORED_CODE", "Authored description", "ECL_CACHE"),
                ("SHARED_CLUSTER", "IMPORTED_CODE", "Imported description", "PCD"),
                ("OTHER_CLUSTER", "OTHER_CODE", "Other description", "ECL_CACHE"),
                ("CLUSTER'S_NAME", "QUOTED_CODE", "Quoted description", "SOURCE'S_NAME"),
            ],
        )

    def member_codes(self, cluster_id, source=None):
        query = codeset_codes_query(cluster_id, source)
        return self.conn.execute(query.replace(CODESETS_TABLE, "combined_codesets")).fetchall()

    def test_authored_defaults_do_not_include_another_source_or_cluster(self):
        for source in (None, "", "ECL_CACHE"):
            with self.subTest(source=source):
                self.assertEqual(
                    self.member_codes("SHARED_CLUSTER", source),
                    [("AUTHORED_CODE", "Authored description", "ECL_CACHE")],
                )

    def test_imported_codeset_keeps_its_source(self):
        self.assertEqual(
            self.member_codes("SHARED_CLUSTER", "PCD"),
            [("IMPORTED_CODE", "Imported description", "PCD")],
        )

    def test_quoted_identifiers_are_preserved(self):
        self.assertEqual(
            self.member_codes("CLUSTER'S_NAME", "SOURCE'S_NAME"),
            [("QUOTED_CODE", "Quoted description", "SOURCE'S_NAME")],
        )

    def test_template_join_counts_only_the_selected_membership(self):
        self.conn.execute("CREATE TABLE synthetic_events (code TEXT)")
        self.conn.executemany(
            "INSERT INTO synthetic_events VALUES (?)",
            [("AUTHORED_CODE",), ("AUTHORED_CODE",), ("IMPORTED_CODE",), ("OTHER_CODE",)],
        )
        query = (
            "SELECT COUNT(*) FROM combined_codesets ec "
            "JOIN synthetic_events e ON ec.code = e.code "
            f"WHERE {codeset_filter('SHARED_CLUSTER', alias='ec')}"
        )
        self.assertEqual(self.conn.execute(query).fetchone()[0], 2)

    def test_unpublished_codeset_has_no_members(self):
        self.assertEqual(self.member_codes("UNPUBLISHED_CLUSTER"), [])

    def test_analytics_membership_matches_the_copied_query(self):
        for source in (None, "", "ECL_CACHE", "PCD", "SOURCE'S_NAME"):
            with self.subTest(source=source):
                cluster = "CLUSTER'S_NAME" if source == "SOURCE'S_NAME" else "SHARED_CLUSTER"
                source_query = codeset_code_source(source).replace(
                    CODESETS_TABLE, "combined_codesets"
                )
                safe_cluster = cluster.replace("'", "''")
                query = (
                    f"SELECT code, display FROM {source_query} ec "
                    f"WHERE cluster_id = '{safe_cluster}' ORDER BY code"
                )
                expected = [(code, description) for code, description, _ in self.member_codes(cluster, source)]
                self.assertEqual(self.conn.execute(query).fetchall(), expected)


if __name__ == "__main__":
    unittest.main()
