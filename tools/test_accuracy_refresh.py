from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MAIN_JS = ROOT / "web" / "js" / "main.js"


def main() -> None:
    source = MAIN_JS.read_text(encoding="utf-8")

    assert "loadAccuracy({ bustCache: true })" in source, (
        "AI accuracy widget should periodically refresh with a cache-busting request"
    )
    assert "setInterval(() => loadAccuracy({ bustCache: true })" in source, (
        "AI accuracy widget should refresh on an interval after initial page load"
    )
    assert "renderAccuracyRow('技術面'" in source, (
        "AI accuracy widget should render a separate technical sentiment row"
    )
    assert "renderAccuracyRow('總經面'" in source, (
        "AI accuracy widget should render a separate macro sentiment row"
    )


if __name__ == "__main__":
    main()
