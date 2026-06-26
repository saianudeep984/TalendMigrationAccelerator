from typing import Dict, List


class SQLAssertionGenerator:
    def generate_for_table(self, table_name: str, key_columns=None, nullable_columns=None) -> List[Dict[str, str]]:
        table = table_name or "TARGET_TABLE"
        keys = key_columns or ["ID"]
        nullable = nullable_columns if nullable_columns is not None else keys
        assertions = [
            {"type": "COUNT", "sql": f"SELECT COUNT(*) AS row_count FROM {table};"},
            {"type": "MIN_MAX", "sql": f"SELECT MIN({keys[0]}) AS min_key, MAX({keys[0]}) AS max_key FROM {table};"},
            {"type": "HASH_VALIDATION", "sql": f"SELECT COUNT(*), SUM(ORA_HASH({keys[0]})) AS hash_value FROM {table};"},
        ]
        for column in nullable:
            assertions.append({"type": "NULL_CHECK", "sql": f"SELECT COUNT(*) AS null_count FROM {table} WHERE {column} IS NULL;"})
        if keys:
            joined = ", ".join(keys)
            assertions.append({"type": "DUPLICATE_CHECK", "sql": f"SELECT {joined}, COUNT(*) FROM {table} GROUP BY {joined} HAVING COUNT(*) > 1;"})
        return assertions
