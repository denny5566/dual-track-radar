import importlib.util
import json
import sqlite3
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
BACKTEST_PATH = ROOT / "tools" / "backtest.py"


def load_backtest_module():
    spec = importlib.util.spec_from_file_location("backtest_under_test", BACKTEST_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main() -> None:
    backtest = load_backtest_module()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db_path = tmp_path / "radar.db"
        data_dir = tmp_path / "public_data"
        data_dir.mkdir()

        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE daily_reports (date TEXT, json_data TEXT)")
        conn.execute(
            "INSERT INTO daily_reports VALUES (?, ?)",
            (
                "2026-05-12",
                json.dumps(
                    {
                        "comparison": {
                            "capital_futures": {"sentiment": "偏多"},
                            "yu_ting_hao": {"sentiment": "樂觀"},
                        }
                    },
                    ensure_ascii=False,
                ),
            ),
        )
        conn.commit()
        conn.close()

        (data_dir / "20260525.json").write_text(
            json.dumps(
                {
                    "meta": {"date": "2026-05-25"},
                    "comparison": {
                        "capital_futures": {"sentiment": "偏空"},
                        "yu_ting_hao": {"sentiment": "樂觀但存在隱憂"},
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        backtest.DB_PATH = db_path
        backtest.PUBLIC_DATA_DIR = data_dir

        output = backtest.run()

        assert output["last_updated"] == "2026-05-25"
        assert output["record_count"] == 2
        assert output["neutral"] == 1


if __name__ == "__main__":
    main()
