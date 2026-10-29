"""tests/test_b1_data_dir_and_cache.py - Stage B1 tests for URBANFLOW_DATA_DIR, offline & cache modes."""
from __future__ import annotations

import os
from pathlib import Path
import pytest

from urbanflow_data.config import get_data_dir
from urbanflow_data.network_bundle import load_network
from urbanflow_data.dashboard_cache import (
    is_offline_mode,
    set_offline_mode,
    is_cache_mode,
    set_cache_mode,
    get_cache_dir,
    get_cached_simulation,
    clear_cache,
    get_offline_map_theme,
)


def test_get_data_dir_default(monkeypatch):
    monkeypatch.delenv("URBANFLOW_DATA_DIR", raising=False)
    p = get_data_dir()
    assert isinstance(p, Path)
    assert p.name == "processed"


def test_get_data_dir_env_var(tmp_path, monkeypatch):
    custom_dir = tmp_path / "custom_data"
    custom_dir.mkdir()
    monkeypatch.setenv("URBANFLOW_DATA_DIR", str(custom_dir))

    p = get_data_dir()
    assert p == custom_dir.resolve()

    # Even if someone passes default "data/processed", env var takes priority
    p_def = get_data_dir("data/processed")
    assert p_def == custom_dir.resolve()


def test_get_data_dir_explicit_override(tmp_path, monkeypatch):
    custom_dir1 = tmp_path / "dir1"
    custom_dir2 = tmp_path / "dir2"
    custom_dir1.mkdir()
    custom_dir2.mkdir()
    monkeypatch.setenv("URBANFLOW_DATA_DIR", str(custom_dir1))

    # Explicit non-default path takes priority
    p = get_data_dir(custom_dir2)
    assert p == custom_dir2.resolve()


def test_load_network_reads_data_dir(tmp_path, monkeypatch):
    # Verify load_network accepts None and resolves via get_data_dir
    monkeypatch.delenv("URBANFLOW_DATA_DIR", raising=False)
    processed = Path("data/processed").resolve()
    if (processed / "network.graphml").exists():
        net = load_network()
        assert net.graph.number_of_nodes() > 0


def test_offline_mode_env_and_toggle(monkeypatch):
    set_offline_mode(None)
    monkeypatch.delenv("URBANFLOW_OFFLINE", raising=False)
    assert is_offline_mode() is False

    monkeypatch.setenv("URBANFLOW_OFFLINE", "1")
    assert is_offline_mode() is True

    monkeypatch.setenv("URBANFLOW_OFFLINE", "true")
    assert is_offline_mode() is True

    set_offline_mode(False)
    assert is_offline_mode() is False

    set_offline_mode(True)
    assert is_offline_mode() is True
    set_offline_mode(None)


def test_cache_mode_env_and_toggle(monkeypatch):
    set_cache_mode(None)
    monkeypatch.delenv("URBANFLOW_CACHE_MODE", raising=False)
    assert is_cache_mode() is True  # default True

    monkeypatch.setenv("URBANFLOW_CACHE_MODE", "0")
    assert is_cache_mode() is False

    set_cache_mode(True)
    assert is_cache_mode() is True
    set_cache_mode(None)


def test_cached_simulation_roundtrip(tmp_path, monkeypatch):
    custom_data = tmp_path / "data_env"
    custom_data.mkdir()
    monkeypatch.setenv("URBANFLOW_DATA_DIR", str(custom_data))
    set_cache_mode(True)

    calls = {"count": 0}

    def compute():
        calls["count"] += 1
        return {"status": "ok", "value": 42}

    res1 = get_cached_simulation("test_scenario_1", compute)
    assert res1["value"] == 42
    assert calls["count"] == 1

    # Second call should load from disk cache, compute() not called
    res2 = get_cached_simulation("test_scenario_1", compute)
    assert res2["value"] == 42
    assert calls["count"] == 1

    # Force recompute
    res3 = get_cached_simulation("test_scenario_1", compute, force_recompute=True)
    assert res3["value"] == 42
    assert calls["count"] == 2

    # Clear cache
    deleted = clear_cache()
    assert deleted >= 1

    # Next call computes again
    res4 = get_cached_simulation("test_scenario_1", compute)
    assert res4["value"] == 42
    assert calls["count"] == 3


def test_get_offline_map_theme():
    theme = get_offline_map_theme()
    assert "plot_bgcolor" in theme
    assert "tile_provider" in theme
    assert theme["plot_bgcolor"] == "#0d0f1a"
