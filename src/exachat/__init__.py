"""ExasolChat — safe text-to-SQL for ExasolDB and DuckDB with local LLMs."""

from exachat.core import ExasolChat, QueryResult
from exachat.connection import ConnectionConfig
from exachat.builder import QueryBuilder
from exachat.metrics import MetricsCatalog
from exachat.safety import RiskLevel, SafetyVerdict, validate_sql
from exachat.schema import get_join_map

__all__ = [
    "ExasolChat",
    "QueryResult",
    "ConnectionConfig",
    "QueryBuilder",
    "MetricsCatalog",
    "RiskLevel",
    "SafetyVerdict",
    "validate_sql",
]
