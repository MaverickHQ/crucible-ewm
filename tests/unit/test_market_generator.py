from services.core.market import generate_market_path


def test_market_generator_determinism() -> None:
    path_one = generate_market_path(["AAPL", "MSFT"], n_steps=5, seed=42)
    path_two = generate_market_path(["AAPL", "MSFT"], n_steps=5, seed=42)

    assert path_one.symbols == path_two.symbols
    assert path_one.steps == path_two.steps


def test_market_generator_schema() -> None:
    path = generate_market_path(["AAPL", "MSFT"], n_steps=5, seed=7)

    assert path.symbols == ["AAPL", "MSFT"]
    assert len(path.steps) == 5
    for step in path.steps:
        assert set(step.keys()) == {"AAPL", "MSFT"}
        for value in step.values():
            assert value > 0


def test_market_generator_magnitude_sanity() -> None:
    path = generate_market_path(["AAPL", "MSFT"], n_steps=20, seed=42)

    aapl_final = path.steps[-1]["AAPL"]
    msft_final = path.steps[-1]["MSFT"]

    assert 70 <= aapl_final <= 130
    assert 140 <= msft_final <= 260
