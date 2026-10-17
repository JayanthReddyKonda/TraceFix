"""Pure metric tests (A6a): defined/undefined handling, macro vs micro."""

from __future__ import annotations

import pytest

from tracefix.evaluation.metrics import (
    DEFAULT_K_VALUES,
    DEFAULT_PRIMARY_K,
    LatencyStats,
    MetricsConfig,
    count_duplicates,
    count_undefined,
    first_relevant_rank,
    hit_at_k,
    latency_stats,
    macro_average,
    mean,
    micro_recall,
    percentile,
    recall_at_k,
    reciprocal_rank,
    sum_tokens,
)


def test_hit_at_k_boundaries() -> None:
    assert hit_at_k([3], 3) is True
    assert hit_at_k([4], 3) is False
    assert hit_at_k([], 10) is False
    assert hit_at_k([1, 9], 5) is True


def test_recall_at_k_zero_denominator_is_undefined_not_zero() -> None:
    assert recall_at_k([1, 2], 10, 0) is None


def test_recall_at_k_values() -> None:
    assert recall_at_k([1, 5, 20], 10, 3) == pytest.approx(2 / 3)
    assert recall_at_k([100], 10, 1) == 0.0


def test_first_relevant_rank_and_reciprocal_rank() -> None:
    assert first_relevant_rank([7, 2, 9]) == 2
    assert first_relevant_rank([]) is None
    assert reciprocal_rank([4]) == 0.25
    assert reciprocal_rank([]) == 0.0


def test_mean_and_macro_average_undefined() -> None:
    assert mean([]) is None
    assert mean([1.0, 3.0]) == 2.0
    assert macro_average([]) is None
    assert macro_average([None, None]) is None
    assert macro_average([1.0, None, 0.0]) == 0.5


def test_micro_recall_pools_denominators() -> None:
    assert micro_recall([[1], [2, 3]], 5, [1, 2]) == 1.0
    assert micro_recall([[9], [9]], 5, [1, 1]) == 0.0
    assert micro_recall([[], []], 5, [0, 0]) is None


def test_micro_recall_validates_alignment() -> None:
    with pytest.raises(ValueError):
        micro_recall([[1]], 5, [1, 1])


def test_count_undefined() -> None:
    assert count_undefined([1.0, None, None]) == 2
    assert count_undefined([]) == 0


def test_sum_tokens_and_duplicates() -> None:
    assert sum_tokens([]) == 0
    assert sum_tokens([3, 4, 5]) == 12
    assert count_duplicates(["a", "b", "a", "a"]) == 2
    assert count_duplicates([]) == 0


def test_percentile_edges() -> None:
    assert percentile([], 50.0) is None
    assert percentile([5.0], 0.0) == 5.0
    assert percentile([5.0], 100.0) == 5.0
    assert percentile([1.0, 2.0, 3.0, 4.0], 50.0) == 2.0
    with pytest.raises(ValueError):
        percentile([1.0], 101.0)


def test_latency_stats_empty_is_all_none() -> None:
    stats = latency_stats([])
    assert stats == LatencyStats(
        count=0, total_ms=0.0, mean_ms=None, p50_ms=None, p95_ms=None, max_ms=None
    )


def test_latency_stats_values() -> None:
    stats = latency_stats([10.0, 20.0, 30.0])
    assert stats.count == 3
    assert stats.total_ms == 60.0
    assert stats.mean_ms == 20.0
    assert stats.max_ms == 30.0
    assert stats.p95_ms == 30.0


def test_metrics_config_provisional_defaults() -> None:
    config = MetricsConfig()
    assert config.k_values == DEFAULT_K_VALUES
    assert config.primary_k == DEFAULT_PRIMARY_K
    with pytest.raises(ValueError):
        MetricsConfig(k_values=(), primary_k=10)
    with pytest.raises(ValueError):
        MetricsConfig(k_values=(5, 10), primary_k=7)
