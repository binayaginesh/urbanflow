"""tests/test_b8_pipeline_data.py - Stage B8 tests for Pipeline & Data page components."""
from __future__ import annotations

import py_compile
from pathlib import Path
import pandas as pd
import pytest

from urbanflow_data.config import get_data_dir, load_config
from urbanflow_data.network_bundle import load_network


def test_pipeline_tables_inspectable():
    net = load_network(get_data_dir())
    assert not net.edges.empty
    assert not net.nodes.empty
    assert isinstance(net.meta, dict)
    assert isinstance(net.bpr_params, dict)


def test_pipeline_data_dictionary_exists():
    root = Path(__file__).parent.parent
    dict_path = root / "docs" / "DATA_DICTIONARY.md"
    assert dict_path.exists()
    content = dict_path.read_text(encoding="utf-8")
    assert "edges.parquet" in content
    assert "edge_id" in content


def test_demo_app_compiles_b8():
    py_compile.compile(str(Path("demo/app.py").resolve()), doraise=True)
