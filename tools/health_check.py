"""
專案健康檢查工具（快速版）

用途：
1. Python 語法編譯檢查
2. JSON / YAML 格式檢查（以 git tracked 檔案為主）

說明：
- 這支腳本不會連網，不會改檔，只做檢查並回傳 non-zero on failure。
- 前端與 TypeScript 檢查請另外執行：
  - web:   npm run build
  - video: npx tsc --noEmit
"""

from __future__ import annotations

import compileall
import json
import subprocess
import sys
from pathlib import Path


def _tracked_files() -> list[Path]:
    out = subprocess.check_output(["git", "ls-files"], text=True)
    return [Path(line.strip()) for line in out.splitlines() if line.strip()]


def check_python_compile() -> bool:
    ok = compileall.compile_dir(".", maxlevels=3, quiet=1)
    print(f"[python] compile: {'OK' if ok else 'FAIL'}")
    return ok


def check_json(files: list[Path]) -> bool:
    ok = True
    for p in files:
        if p.suffix != ".json":
            continue
        try:
            json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:  # pragma: no cover - 檢查腳本用途
            print(f"[json] FAIL {p}: {e}")
            ok = False
    if ok:
        count = sum(1 for p in files if p.suffix == ".json")
        print(f"[json] OK ({count} files)")
    return ok


def check_yaml(files: list[Path]) -> bool:
    targets = [p for p in files if p.suffix in {".yml", ".yaml"}]
    if not targets:
        print("[yaml] SKIP (no yaml files)")
        return True
    try:
        import yaml  # type: ignore
    except Exception as e:  # pragma: no cover
        print(f"[yaml] SKIP (PyYAML not installed: {e})")
        return True

    ok = True
    for p in targets:
        try:
            yaml.safe_load(p.read_text(encoding="utf-8"))
        except Exception as e:  # pragma: no cover
            print(f"[yaml] FAIL {p}: {e}")
            ok = False
    if ok:
        print(f"[yaml] OK ({len(targets)} files)")
    return ok


def main() -> int:
    files = _tracked_files()
    results = [
        check_python_compile(),
        check_json(files),
        check_yaml(files),
    ]
    all_ok = all(results)
    print(f"\n[health-check] {'PASS' if all_ok else 'FAIL'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
