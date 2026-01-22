import numpy as np
import sys
sys.path.append( "calib" )
from scoring import compute_fit


def test_compute_fit_exact_match():
    actual = {"a": [1, 2, 3]}
    predicted = {"a": [1, 2, 3]}
    result = compute_fit(actual, predicted)
    assert result == 0.0


def test_compute_fit_basic_difference():
    actual = {"a": [1, 2, 3]}
    predicted = {"a": [2, 2, 2]}
    result = compute_fit(actual, predicted)
    expected = abs(1 - 2) + abs(2 - 2) + abs(3 - 2)
    assert result == expected


def test_compute_fit_squared_error():
    actual = {"a": [1, 2, 3]}
    predicted = {"a": [2, 2, 2]}
    result = compute_fit(actual, predicted, use_squared=True)
    expected = (1 - 2)**2 + (2 - 2)**2 + (3 - 2)**2
    assert result == expected


def test_compute_fit_normalized():
    actual = {"a": [1, 2, 4]}
    predicted = {"a": [0, 2, 2]}
    result = compute_fit(actual, predicted, normalize=True)
    expected = (1 / 4) + (0 / 4) + (2 / 4)
    assert np.isclose(result, expected)


def test_compute_fit_weighted():
    actual = {"x": [1, 2], "y": [1, 1]}
    predicted = {"x": [2, 1], "y": [0, 0]}
    weights = {"x": 2.0, "y": 0.5}
    result = compute_fit(actual, predicted, weights=weights)
    # x: |1-2| + |2-1| = 2 * 2.0 = 4
    # y: |1-0| + |1-0| = 2 * 0.5 = 1
    assert result == 5.0


def test_compute_fit_missing_predicted_key():
    actual = {"a": [1, 2], "b": [5, 5]}
    predicted = {"a": [2, 3]}  # 'b' is missing
    result = compute_fit(actual, predicted)
    expected = abs(1 - 2) + abs(2 - 3)  # Only compares 'a'
    assert result == expected
