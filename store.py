"""
store.py — 运行记录
====================
内存里保存进行中的任务状态（网页轮询要读），完成后落盘成
`runs/<时间戳>-<id>.json`，刷新页面或第二天再来还能翻出历史。

只存原始数据（原文、译文、耗时），不存任何分析结论。
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path

import config


class Run:
    """一次运行（N 轮往复翻译）。"""

    def __init__(self, text: str, rounds: int) -> None:
        self.id = uuid.uuid4().hex[:12]
        self.text = text
        self.rounds = rounds
        self.status = "running"          # running / done / stopped / error
        self.steps: list[dict] = []
        self.final_zh = ""
        self.total_ms = 0
        self.error = ""
        self.created_at = time.time()
        self.finished_at = 0.0
        self.stop_event = threading.Event()   # 网页点「停止」时置位

    # ── 快照：给网页轮询用 ──
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "input": self.text,
            "rounds": self.rounds,
            "status": self.status,
            "steps": self.steps,
            "final_zh": self.final_zh,
            "total_ms": self.total_ms,
            "error": self.error,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
            "progress": {
                "done_steps": len(self.steps),
                "total_steps": self.rounds * 2,
                "done_rounds": len(self.steps) // 2,
            },
        }


_lock = threading.Lock()
_runs: dict[str, Run] = {}
_MAX_IN_MEMORY = 50


def create(text: str, rounds: int) -> Run:
    run = Run(text=text, rounds=rounds)
    with _lock:
        _runs[run.id] = run
        # 内存里只留最近若干条，旧的从 runs/ 里读
        if len(_runs) > _MAX_IN_MEMORY:
            oldest = sorted(_runs.values(), key=lambda r: r.created_at)[0]
            if oldest.status != "running":
                _runs.pop(oldest.id, None)
    return run


def get(run_id: str) -> Run | None:
    with _lock:
        run = _runs.get(run_id)
    if run is not None:
        return run
    return _load_from_disk(run_id)


def recent(limit: int = 20) -> list[dict]:
    """历史运行列表（内存里的 + 磁盘上的），新的在前。"""
    merged: dict[str, dict] = {}
    with _lock:
        for run in _runs.values():
            merged[run.id] = _summary(run.to_dict())
    for data in _load_all_from_disk():
        merged.setdefault(data["id"], _summary(data))
    items = sorted(merged.values(), key=lambda d: d["created_at"], reverse=True)
    return items[:limit]


def save(run: Run) -> Path:
    """把完成的运行写到 runs/*.json。"""
    config.RUNS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(run.created_at))
    path = config.RUNS_DIR / f"{stamp}-{run.id}.json"
    payload = run.to_dict()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def to_markdown(data: dict) -> str:
    """把一次运行导出成 Markdown 全过程。"""
    lines: list[str] = []
    lines.append(f"# 关于往复翻译的记录（{data.get('rounds', 0)} 轮）\n")
    lines.append(f"- 作为输入的中文：{data.get('input', '')}")
    lines.append(f"- 最终的中文结果：{data.get('final_zh', '')}")
    lines.append(f"- 它现在的状态：{data.get('status', '')}")
    lines.append(f"- 总共被消耗的时间：{data.get('total_ms', 0)} ms\n")

    for step in data.get("steps", []):
        lines.append(f"## 第 {step['round']} 轮的翻译 · {step['direction_label']}")
        lines.append(f"- 在其中，原文：{step['src']}")
        lines.append(f"- 而译文：{step['out']}")
        lines.append(f"- 其中被消耗：{step['ms']} ms")
        if step.get("degenerate"):
            lines.append("- 注意：一个整段的重复已经被发生了")
        lines.append("")
    return "\n".join(lines)


# ── 内部工具 ──

def _summary(data: dict) -> dict:
    return {
        "id": data["id"],
        "input": data.get("input", ""),
        "rounds": data.get("rounds", 0),
        "status": data.get("status", ""),
        "final_zh": data.get("final_zh", ""),
        "created_at": data.get("created_at", 0),
    }


def _load_from_disk(run_id: str) -> Run | None:
    if not config.RUNS_DIR.exists():
        return None
    for path in config.RUNS_DIR.glob(f"*-{run_id}.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        run = Run(data.get("input", ""), int(data.get("rounds", 0)))
        run.id = data.get("id", run_id)
        run.status = data.get("status", "done")
        run.steps = data.get("steps", [])
        run.final_zh = data.get("final_zh", "")
        run.total_ms = data.get("total_ms", 0)
        run.error = data.get("error", "")
        run.created_at = data.get("created_at", 0.0)
        run.finished_at = data.get("finished_at", 0.0)
        return run
    return None


def _load_all_from_disk() -> list[dict]:
    if not config.RUNS_DIR.exists():
        return []
    out: list[dict] = []
    for path in config.RUNS_DIR.glob("*.json"):
        try:
            out.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return out
