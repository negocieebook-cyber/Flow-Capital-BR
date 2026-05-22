import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd

from app.processing.aggregation import aggregate_sectors
from app.processing.individual_readings import classify_individual_reading
from app.processing.momentum import rs_momentum, rs_ratio
from app.processing.quadrants import classify_quadrant
from app.processing.relative_strength import relative_strength
from app.processing.returns import benchmark_return, relative_return, weekly_return
from app.processing.scoring import score_individual
from app.processing.volume_flow import financial_volume, volume_relative


def test_weekly_return():
    assert math.isclose(weekly_return(110, 100), 0.10)


def test_benchmark_return():
    assert math.isclose(benchmark_return(210, 200), 0.05)


def test_relative_return():
    assert math.isclose(relative_return(0.08, 0.03), 0.05)


def test_relative_strength():
    assert relative_strength(50, 100) == 0.5


def test_rs_ratio():
    assert math.isclose(rs_ratio(1.1, 1.0), 110)


def test_rs_momentum():
    assert rs_momentum(105, 100) == 105


def test_financial_volume():
    assert financial_volume(20, 1000) == 20000


def test_volume_relative():
    assert volume_relative(30000, 20000) == 1.5


def test_quadrant_classification():
    assert classify_quadrant(101, 102) == "Leading"
    assert classify_quadrant(101, 99) == "Weakening"
    assert classify_quadrant(99, 99) == "Lagging"
    assert classify_quadrant(99, 101) == "Improving"


def test_individual_reading_classification():
    assert classify_individual_reading(0.05, 0.03, 101, 65) == "Confirma o setor"
    assert classify_individual_reading(-0.05, -0.03, 98, 45) == "Diverge do setor"
    assert classify_individual_reading(0.01, 0.00, 100, 55) == "Neutra"


def test_internal_confirmation():
    df = pd.DataFrame(
        [
            {
                "week_date": "2026-05-15",
                "ticker": "AAA3",
                "sector": "Teste",
                "weekly_return": 0.05,
                "benchmark_return": 0.01,
                "relative_return": 0.04,
                "rs_ratio": 105,
                "rs_momentum": 103,
                "volume_relative": 1.4,
                "score": 70,
                "individual_reading": "Confirma o setor",
                "unusual_volume_label": "",
            },
            {
                "week_date": "2026-05-15",
                "ticker": "BBB3",
                "sector": "Teste",
                "weekly_return": -0.01,
                "benchmark_return": 0.01,
                "relative_return": -0.02,
                "rs_ratio": 98,
                "rs_momentum": 99,
                "volume_relative": 0.9,
                "score": 45,
                "individual_reading": "Diverge do setor",
                "unusual_volume_label": "",
            },
        ]
    )
    result = aggregate_sectors(df)
    assert math.isclose(result.iloc[0]["internal_confirmation"], 0.5)


def test_score_normalization():
    score = score_individual(120, 120, 3.0, 0.2)
    assert 0 <= score <= 100
