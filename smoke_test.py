"""
smoke_test.py — 最小验证脚本（不启网页也能跑）
==============================================
用途：确认模型能下载、能用，并且**同样的输入得到同样的输出**
      （这是本项目的前提，见 config.py 里 num_beams 的注释）。

跑法：
    .venv\\Scripts\\python.exe smoke_test.py            # 默认翻 2 轮
    .venv\\Scripts\\python.exe smoke_test.py 你好世界 3  # 指定文本和轮数
"""
from __future__ import annotations

import sys

import ws_tmp  # 先修临时目录（沙箱下必需）
import config  # noqa: F401  引入即设置 HF_ENDPOINT / HF_HOME
import spm_path_fix  # noqa: F401  中文路径兼容补丁（要在 transformers 之前）

import pipeline  # noqa: E402
import translator  # noqa: E402

DEFAULT_TEXT = "他称，他制作了一个 WiFi 门铃。"


def main() -> int:
    text = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TEXT
    rounds = int(sys.argv[2]) if len(sys.argv) > 2 else 2

    mode = translator.decode_mode_name()
    print(f"模型目录：{config.MODELS_DIR}")
    print(f"下载源：{config.HF_ENDPOINT}")
    print(f"解码方式：{translator.decode_mode_label()}")
    print(f"原文：{text}")
    print(f"轮数：{rounds}（共 {rounds * 2} 次翻译）")
    print("-" * 60)

    first = pipeline.run(text, rounds, on_step=_print_step)
    print("-" * 60)
    print(f"最终中文：{first['final_zh']}")
    print(f"总耗时：{first['total_ms']} ms")
    print("-" * 60)

    # 再跑一遍对比
    print("再跑一遍做对比 ...")
    second = pipeline.run(text, rounds)
    first_outs = [a["out"] for a in first["steps"]]
    second_outs = [b["out"] for b in second["steps"]]
    same_count = sum(1 for a, b in zip(first_outs, second_outs) if a == b)
    total = len(first_outs)

    if mode == "greedy":
        if first_outs == second_outs:
            print(f"确定性检查：通过（{total} 条译文全部逐字一致）")
            return 0
        print("确定性检查：不一致！config.py 里 DECODE_MODE 应该是 greedy 才对。")
        for a, b in zip(first["steps"], second["steps"]):
            if a["out"] != b["out"]:
                print(f"  第 {a['round']} 轮 {a['direction_label']}")
                print(f"    第一次：{a['out']}")
                print(f"    第二次：{b['out']}")
        return 1

    # 采样模式：本来就不该一致，这里只汇报差异程度
    print(f"随机模式检查：{total} 条译文里有 {total - same_count} 条两次不同"
          f"（{same_count} 条碰巧相同）")
    print("这是 DECODE_MODE = \"sample\" 的预期行为：每次结果都可能不同。")
    print(f"  第一次最终中文：{first['final_zh']}")
    print(f"  第二次最终中文：{second['final_zh']}")
    return 0


def _print_step(step: dict) -> None:
    flag = "  [疑似整段重复]" if step["degenerate"] else ""
    print(f"第 {step['round']} 轮 · {step['direction_label']}（{step['ms']} ms）{flag}")
    print(f"    原文：{step['src']}")
    print(f"    译文：{step['out']}")


if __name__ == "__main__":
    raise SystemExit(main())
