import subprocess


def test_demo_local_strategy_runs() -> None:
    result = subprocess.run(
        ["python3", "scripts/demo_local_strategy.py"],
        capture_output=True,
        text=True,
        check=True,
    )
    output = result.stdout
    assert "Strategy demo" in output
    assert "signals" in output
    assert "BUY" in output
    assert "Decision" in output
