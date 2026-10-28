"""Tests for the paired attribution analysis."""

from __future__ import annotations

import importlib.util
import random
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "experiments" / "analyze_attribution.py"
SPEC = importlib.util.spec_from_file_location("analyze_attribution", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def record(mode: str, **updates):
    base = {
        "status": "ok",
        "mode": mode,
        "variant_id": "v",
        "image_id": "1",
        "sigma": 2.0,
        "replicate": 0,
        "stability_ari": 0.8 if mode == "fixed_clean" else 0.5,
        "stability_vi_total": 0.2 if mode == "fixed_clean" else 0.7,
        "stability_boundary_f1_t1": 0.9 if mode == "fixed_clean" else 0.6,
        "seed_count": 10 if mode == "fixed_clean" else 30,
    }
    base.update(updates)
    return base


def test_pair_effect_directions():
    pairs = MODULE.build_pairs([record("fixed_clean"), record("recomputed")])
    assert len(pairs) == 1
    pair = pairs[0]
    assert pair["delta_stability_ari"] == pytest.approx(0.3)
    assert pair["fixed_advantage_stability_vi_total"] == pytest.approx(0.5)
    assert pair["delta_stability_boundary_f1_t1"] == pytest.approx(0.3)
    assert pair["recomputed_minus_fixed_seed_count"] == 20


def test_incomplete_pair_fails():
    with pytest.raises(RuntimeError, match="incomplete pair"):
        MODULE.build_pairs([record("fixed_clean")])


def test_exact_sign_flip_two_equal_effects():
    p_value, method = MODULE.sign_flip_p([1.0, 1.0], 100, random.Random(1))
    assert method == "exact"
    assert p_value == pytest.approx(0.5)


def test_holm_adjustment_is_monotone_in_rank():
    rows = [{"sign_flip_p": 0.01}, {"sign_flip_p": 0.04}, {"sign_flip_p": 0.03}]
    MODULE.holm_adjust(rows)
    assert rows[0]["holm_p"] == pytest.approx(0.03)
    assert rows[2]["holm_p"] == pytest.approx(0.06)
    assert rows[1]["holm_p"] == pytest.approx(0.06)
