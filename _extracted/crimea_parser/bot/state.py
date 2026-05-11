"""Сбор состояния парсера для отображения боту."""
import csv
import glob
import os
import subprocess
from datetime import datetime
from typing import Optional

from utils import progress


def latest_csv() -> Optional[str]:
    """Возвращает самый свежий не-enriched CSV (или enriched если он позже)."""
    pattern_enriched = "/home/crimea_parser/output/result_enriched_*.csv"
    pattern_plain = "/home/crimea_parser/output/result_2*.csv"
    files = sorted(glob.glob(pattern_plain) + glob.glob(pattern_enriched),
                   key=os.path.getmtime, reverse=True)
    return files[0] if files else None


def parser_systemd_state() -> str:
    """active / inactive / failed / activating."""
    try:
        r = subprocess.run(
            ["systemctl", "is-active", "crimea_parser.service"],
            capture_output=True, text=True, timeout=5,
        )
        return r.stdout.strip() or r.stderr.strip()
    except Exception as e:
        return f"err: {e}"


def parser_uptime_seconds() -> Optional[int]:
    try:
        r = subprocess.run(
            ["systemctl", "show", "crimea_parser.service",
             "--property=ActiveEnterTimestamp"],
            capture_output=True, text=True, timeout=5,
        )
        line = r.stdout.strip()
        if "=" not in line:
            return None
        ts = line.split("=", 1)[1].strip()
        if not ts or ts == "n/a":
            return None
        # пример: Mon 2026-05-12 00:30:15 MSK
        parts = ts.split(" ")
        if len(parts) >= 3:
            d = datetime.strptime(" ".join(parts[1:3]), "%Y-%m-%d %H:%M:%S")
            return int((datetime.now() - d).total_seconds())
    except Exception:
        pass
    return None


def csv_stats(path: str) -> dict:
    if not path or not os.path.exists(path):
        return {"total": 0, "phone": 0, "email": 0, "address": 0, "website": 0, "sources": {}}
    rows = []
    for delim in (";", ","):
        try:
            with open(path, encoding="utf-8-sig") as f:
                sample = f.read(2048)
                f.seek(0)
                if delim in sample:
                    rows = list(csv.DictReader(f, delimiter=delim))
                    if rows and "name" in rows[0]:
                        break
        except Exception:
            continue
    total = len(rows)
    sources: dict[str, int] = {}
    for r in rows:
        s = r.get("source", "?") or "?"
        sources[s] = sources.get(s, 0) + 1
    return {
        "total": total,
        "phone":   sum(1 for r in rows if (r.get("phone") or "").strip()),
        "email":   sum(1 for r in rows if (r.get("email") or "").strip()),
        "address": sum(1 for r in rows if (r.get("address") or "").strip()),
        "website": sum(1 for r in rows if (r.get("website") or "").strip()),
        "sources": sources,
        "file": path,
        "mtime": datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M"),
    }


def progress_snapshot() -> dict:
    return progress.read()


def log_tail(n: int = 30) -> str:
    try:
        r = subprocess.run(
            ["tail", f"-n{n}", "/home/crimea_parser/parser.log"],
            capture_output=True, text=True, timeout=5,
        )
        return r.stdout or "(пусто)"
    except Exception as e:
        return f"err: {e}"


def systemctl(*args: str) -> tuple[int, str]:
    try:
        r = subprocess.run(
            ["systemctl"] + list(args),
            capture_output=True, text=True, timeout=20,
        )
        return r.returncode, (r.stdout + r.stderr).strip()
    except Exception as e:
        return -1, str(e)


def format_uptime(seconds: Optional[int]) -> str:
    if seconds is None:
        return "—"
    if seconds < 60:
        return f"{seconds} с"
    if seconds < 3600:
        return f"{seconds // 60} мин"
    return f"{seconds // 3600} ч {(seconds % 3600) // 60} мин"
