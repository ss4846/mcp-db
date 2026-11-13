import sqlite3
from contextlib import closing
import pytest

from server import (
    DB_PATH,
    MAX_ROWS,
    describe_table,
    get_conn,
    is_blocked,
    list_tables,
    run_query,
    validate_select,
)

needs_db = pytest.mark.skipif(not DB_PATH.exists(), reason="chinook.db not found")


# ---------- validator (no database needed) ----------

@pytest.mark.parametrize("sql", [
    "SELECT 1",
    "select * from Track",
    "SELECT 1;",
    "SELECT a FROM t UNION SELECT b FROM u",
    "WITH x AS (SELECT 1) SELECT * FROM x",
])
def test_validator_accepts_selects(sql):
    validate_select(sql)


@pytest.mark.parametrize("sql", [
    "DELETE FROM Customer",
    "DROP TABLE Customer",
    "INSERT INTO Customer (FirstName) VALUES ('x')",
    "UPDATE Customer SET FirstName = 'x'",
    "PRAGMA table_info(Customer)",
    "ATTACH DATABASE ':memory:' AS x",
    "WITH x AS (SELECT 1) DELETE FROM Customer",
])
def test_validator_rejects_non_selects(sql):
    with pytest.raises(ValueError, match="Only SELECT"):
        validate_select(sql)


@pytest.mark.parametrize("sql", ["SELECT 1; DROP TABLE Customer", "", "   "])
def test_validator_rejects_wrong_statement_count(sql):
    with pytest.raises(ValueError, match="single SQL statement"):
        validate_select(sql)


def test_validator_rejects_unparseable_sql():
    with pytest.raises(ValueError, match="parse"):
        validate_select("SELEC * FROM Customer")


# ---------- blocklist helper (no database needed) ----------

def test_is_blocked_is_case_insensitive():
    assert is_blocked("Customer", "Email")
    assert is_blocked("CUSTOMER", "email")
    assert not is_blocked("Customer", "FirstName")
    assert not is_blocked("Track", "Name")


# ---------- integration tests (need chinook.db) ----------

@needs_db
def test_list_tables_contains_core_tables():
    tables = list_tables()
    assert {"Customer", "Invoice", "Track"} <= set(tables)


@needs_db
def test_run_query_returns_rows_and_columns():
    result = run_query("SELECT FirstName, Country FROM Customer LIMIT 3")
    assert result["columns"] == ["FirstName", "Country"]
    assert result["row_count"] == 3
    assert result["truncated"] is False


@needs_db
def test_run_query_truncates_large_results():
    result = run_query("SELECT * FROM Track")
    assert result["row_count"] == MAX_ROWS
    assert result["truncated"] is True


@needs_db
@pytest.mark.parametrize("sql", [
    "DELETE FROM Customer",
    "DROP TABLE Customer",
    "SELECT 1; DROP TABLE Customer",
    "PRAGMA table_info(Customer)",
])
def test_run_query_rejects_dangerous_sql(sql):
    with pytest.raises(ValueError):
        run_query(sql)


@needs_db
def test_connection_is_read_only_even_without_validator():
    # Defense in depth: the database itself must refuse writes
    with closing(get_conn()) as conn:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("DELETE FROM Customer")


@needs_db
@pytest.mark.parametrize("sql, column", [
    ("SELECT Email FROM Customer", "Customer.Email"),
    ("SELECT c.Email FROM Customer c", "Customer.Email"),
    ("SELECT FirstName FROM Customer WHERE Email LIKE '%@%'", "Customer.Email"),
    ("SELECT * FROM Customer", "Customer.Address"),   # first blocked column in table order
])
def test_blocked_columns_cannot_be_read(sql, column):
    with pytest.raises(ValueError, match=rf"{column}.*prohibited"):
        run_query(sql)


@needs_db
def test_describe_table_hides_blocked_data():
    info = describe_table("Customer")
    restricted = {c["name"] for c in info["columns"] if c["restricted"]}
    assert {"Email", "Phone"} <= restricted
    for row in info["sample_rows"]:
        assert "Email" not in row and "Phone" not in row


@needs_db
def test_describe_table_rejects_unknown_table():
    with pytest.raises(ValueError, match="Unknown table"):
        describe_table("Customer; DROP TABLE Customer")


@needs_db
def test_runaway_query_is_interrupted():
    # Takes about TIMEOUT_S seconds by design
    with pytest.raises(ValueError, match="interrupt"):
        run_query("SELECT COUNT(*) FROM Track a, Track b, Track c")