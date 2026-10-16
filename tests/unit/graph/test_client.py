"""Client failure-path tests with a stub driver (A1.3, service-free)."""

from __future__ import annotations

from typing import Any

import pytest

from tracefix.graph.client import (
    FalkorDBClient,
    GraphConnectionError,
    GraphQueryError,
    GraphTimeoutError,
)


class FakeGraph:
    def __init__(self, error: Exception | None = None, rows: list[dict[str, Any]] | None = None):
        self.error = error
        self.rows = rows or []
        self.last_query: tuple[str, dict] | None = None

    def query(self, cypher: str, params: dict | None = None) -> list[dict[str, Any]]:
        self.last_query = (cypher, params or {})
        if self.error is not None:
            raise self.error
        return self.rows


class FakeDriver:
    def __init__(self, graph: FakeGraph):
        self.graph = graph
        self.selected: list[str] = []

    def select_graph(self, name: str) -> FakeGraph:
        self.selected.append(name)
        return self.graph


def test_invalid_graph_name_rejected() -> None:
    with pytest.raises(ValueError, match="invalid graph name"):
        FalkorDBClient(graph_name="bad name!")


def test_execute_before_connect_raises() -> None:
    client = FalkorDBClient(graph_name="tenant_acme", driver_factory=lambda h, p: None)
    with pytest.raises(GraphConnectionError, match="not connected"):
        client.execute("RETURN 1")


def test_connection_failure_maps_to_typed_error() -> None:
    def factory(host: str, port: int) -> Any:
        raise ConnectionError("socket refused")

    client = FalkorDBClient(graph_name="tenant_acme", driver_factory=factory)
    with pytest.raises(GraphConnectionError, match="cannot connect"):
        client.connect()


def test_timeout_maps_to_typed_error() -> None:
    graph = FakeGraph(error=TimeoutError("operation timed out after 1000ms"))
    client = FalkorDBClient(graph_name="tenant_acme", driver_factory=lambda h, p: FakeDriver(graph))
    client.connect()
    with pytest.raises(GraphTimeoutError, match="timed out"):
        client.execute("RETURN 1", timeout_ms=1000)


def test_generic_failure_maps_to_query_error() -> None:
    graph = FakeGraph(error=ValueError("Cypher syntax error"))
    client = FalkorDBClient(graph_name="tenant_acme", driver_factory=lambda h, p: FakeDriver(graph))
    client.connect()
    with pytest.raises(GraphQueryError, match="query failed"):
        client.execute("NOT CYPHER")


def test_successful_execute_returns_rows_and_uses_bound_graph() -> None:
    graph = FakeGraph(rows=[{"n": 1}])
    driver = FakeDriver(graph)
    client = FalkorDBClient(graph_name="tenant_acme", driver_factory=lambda h, p: driver)
    client.connect()
    rows = client.execute("RETURN $n AS n", params={"n": 1})
    assert rows == [{"n": 1}]
    assert driver.selected == ["tenant_acme"]
    assert graph.last_query == ("RETURN $n AS n", {"n": 1})
    client.close()
    assert client.connected is False
