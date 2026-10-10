"""
pipeline.py — 往复翻译主循环
=============================
一轮 = 中文→英文，再英文→中文（两次模型调用）。
N 轮下来就是 2N 次翻译，最终输出的是中文。

这个模块只做"翻"，不做任何对比分析：每步的记录里只有
「第几轮 / 方向 / 原文 / 译文 / 耗时」，没有相似度、没有收敛判定。

支持中止：传入 abort 事件（threading.Event），收到后停在当前步，
已完成的轮次照常返回。
"""
from __future__ import annotations

import threading
import time
from typing import Callable

import translator

StepCallback = Callable[[dict], None]


def run(text: str, rounds: int, on_step: StepCallback | None = None,
        abort: threading.Event | None = None) -> dict:
    """跑 N 轮往复翻译。

    参数：
        text    起始中文文本
        rounds  轮数
        on_step 每完成一次翻译（半轮）就回调一次，用于网页实时显示
        abort   中止信号

    返回：{input, rounds, steps, final_zh, total_ms, stopped}
    """
    started = time.perf_counter()
    current = (text or "").strip()
    steps: list[dict] = []
    stopped = False

    for round_no in range(1, rounds + 1):
        if abort is not None and abort.is_set():
            stopped = True
            break

        # ── 半轮 1：中文 → 英文 ──
        result = translator.translate(current, "zh2en")
        step = {
            "round": round_no,
            "direction": "zh2en",
            "direction_label": translator.DIRECTION_LABEL["zh2en"],
            "src": current,
            "out": result.text,
            "ms": result.ms,
            "degenerate": result.degenerate,
        }
        steps.append(step)
        if on_step is not None:
            on_step(step)
        current_en = result.text

        if abort is not None and abort.is_set():
            stopped = True
            break

        # ── 半轮 2：英文 → 中文 ──
        back = translator.translate(current_en, "en2zh")
        step = {
            "round": round_no,
            "direction": "en2zh",
            "direction_label": translator.DIRECTION_LABEL["en2zh"],
            "src": current_en,
            "out": back.text,
            "ms": back.ms,
            "degenerate": back.degenerate,
        }
        steps.append(step)
        if on_step is not None:
            on_step(step)
        current = back.text

    total_ms = int((time.perf_counter() - started) * 1000)
    return {
        "input": (text or "").strip(),
        "rounds": rounds,
        "steps": steps,
        "final_zh": current,
        "total_ms": total_ms,
        "stopped": stopped,
    }
