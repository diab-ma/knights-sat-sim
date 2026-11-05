from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_progress(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "progress.db"))
