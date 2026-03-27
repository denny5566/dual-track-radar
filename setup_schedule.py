"""
設定 Windows 工作排程器，週一至週五自動執行管線。

用法：
  python setup_schedule.py              # 建立排程（週一至週五 10:00）
  python setup_schedule.py --time 08:30 # 自訂時間
  python setup_schedule.py --delete     # 刪除排程
  python setup_schedule.py --status     # 查看排程狀態
"""

import argparse
import subprocess
import sys
from pathlib import Path

TASK_NAME = "雙軌財經情報雷達"
PROJECT_DIR = Path(__file__).parent.resolve()
PYTHON = sys.executable
MAIN_SCRIPT = str(PROJECT_DIR / "main.py")
WORK_DIR = str(PROJECT_DIR)


def _run_ps(script: str) -> str:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    return (result.stdout + result.stderr).strip()


def create_task(run_time: str = "10:00") -> None:
    script = f"""
$action  = New-ScheduledTaskAction -Execute '{PYTHON}' -Argument '{MAIN_SCRIPT}' -WorkingDirectory '{WORK_DIR}'
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At '{run_time}'
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 2) -StartWhenAvailable $true
Register-ScheduledTask -TaskName '{TASK_NAME}' -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Write-Host "排程建立成功：週一至週五 {run_time} 自動執行"
"""
    print(_run_ps(script))


def delete_task() -> None:
    script = f"Unregister-ScheduledTask -TaskName '{TASK_NAME}' -Confirm:$false; Write-Host '排程已刪除'"
    print(_run_ps(script))


def show_task() -> None:
    script = f"Get-ScheduledTask -TaskName '{TASK_NAME}' | Select TaskName, State, @{{n='NextRun';e={{($_ | Get-ScheduledTaskInfo).NextRunTime}}}} | Format-List"
    print(_run_ps(script))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--time",   default="10:00", help="執行時間 HH:MM（預設 10:00）")
    parser.add_argument("--delete", action="store_true", help="刪除排程")
    parser.add_argument("--status", action="store_true", help="查看排程狀態")
    args = parser.parse_args()

    if args.delete:
        delete_task()
    elif args.status:
        show_task()
    else:
        create_task(args.time)
