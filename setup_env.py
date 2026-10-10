"""
setup_env.py — 建环境（建 .venv → 装 pip → 装依赖）
===================================================
双击 `setup_env.bat` 即可。中文提示全部放在这里，批处理文件里不写中文
（原因见 README：cmd 在中文 Windows 上按 GBK 解读批处理里的 UTF-8 中文，
会把它当成乱码命令执行，刷一屏「'xx' 不是内部或外部命令」）。

已经装好会跳过，重复运行是安全的。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import ws_tmp  # 先修好临时目录（受限环境下必需）

BASE_DIR = Path(__file__).resolve().parent
VENV_DIR = BASE_DIR / ".venv"
VENV_PY = VENV_DIR / "Scripts" / "python.exe"

# 找一个能用来建虚拟环境的系统 Python。
# 顺序：环境变量 PYTHON_HOME → 当前解释器 → py 启动器 → 直接叫 python。
# （原先这里写死了 D:\Python 3.12\python.exe，换台机器就失效，已改掉）
CANDIDATE_PYTHONS = [
    Path(os.environ["PYTHON_HOME"]) / "python.exe" if os.environ.get("PYTHON_HOME") else None,
    Path(sys.executable),
    Path(r"D:\Python 3.12\python.exe"),   # 原作者机器上的路径，仅作兜底
]

# 国内镜像：直连 pypi.org 极慢甚至卡住，实测清华镜像能跑到 2MB/s
# 想用官方源就把下面这行改成 https://pypi.org/simple
PIP_INDEX = os.environ.get("PIP_INDEX_URL") or "https://pypi.tuna.tsinghua.edu.cn/simple"

PIP_INI = f"""[global]
index-url = {PIP_INDEX}
timeout = 60
disable-pip-version-check = true
"""


def find_system_python() -> Path | None:
    """找一个可用的系统 Python 解释器路径。"""
    for candidate in CANDIDATE_PYTHONS:
        if candidate is None:
            continue
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue

    # py 启动器（Windows 上随 Python 一起安装）
    for launcher in ("py", "python3", "python"):
        found = shutil.which(launcher)
        if found:
            return Path(found)
    return None


def run(cmd: list[str], **kwargs) -> int:
    print("  $", " ".join(str(c) for c in cmd))
    return subprocess.run(cmd, cwd=str(BASE_DIR), **kwargs).returncode


def can_import(module: str) -> bool:
    if not VENV_PY.is_file():
        return False
    try:
        return subprocess.run(
            [str(VENV_PY), "-c", f"import {module}"], capture_output=True
        ).returncode == 0
    except OSError:
        return False


def main() -> int:
    print("=" * 62)
    print("  20 遍翻译机 — 建环境")
    print("=" * 62)
    print(f"  项目目录：{BASE_DIR}")

    if can_import("torch") and can_import("transformers") and can_import("sentencepiece"):
        print("环境已经就绪，不需要重装。")
        return 0

    # ── 1. 建虚拟环境 ──
    if VENV_PY.is_file():
        print("[1/3] 虚拟环境已存在，跳过创建")
    else:
        system_python = find_system_python()
        if system_python is None:
            print("找不到 Python。请编辑本文件顶部的 CANDIDATE_PYTHONS 填上你的 python.exe 路径。")
            return 1
        print(f"[1/3] 用 {system_python} 创建虚拟环境 .venv ...")
        # 故意不加 pip：ensurepip 在受限环境下会失败，改由 bootstrap_pip.py 装
        if run([str(system_python), "-m", "venv", "--without-pip", ".venv"]) != 0:
            print("创建虚拟环境失败。")
            return 1

    # ── 2. 装 pip ──
    if can_import("pip"):
        print("[2/3] pip 已存在，跳过安装")
    else:
        print("[2/3] 安装 pip ...")
        if run([str(VENV_PY), "-u", str(BASE_DIR / "bootstrap_pip.py")]) != 0:
            print("安装 pip 失败。")
            return 1

    # 顺手给这个 venv 配上镜像，以后手工 pip install 也快
    pip_ini = VENV_DIR / "pip.ini"
    if not pip_ini.exists():
        pip_ini.write_text(PIP_INI, encoding="utf-8")
        print("      已写入镜像配置 pip.ini")

    # ── 3. 装依赖 ──
    print("[3/3] 安装依赖 ...")
    print("      torch 要下载约 124MB，装完约占 2.5GB，耐心等几分钟。")
    env = {**os.environ, "PIP_INDEX_URL": PIP_INDEX, "HF_HUB_DISABLE_XET": "1"}
    if run(
        [str(VENV_PY), "-u", "-m", "pip", "install", "-r", "requirements.txt"],
        env=env,
    ) != 0:
        print("依赖安装失败，请把上面的报错发出来看看。")
        return 1

    print()
    if can_import("torch") and can_import("transformers") and can_import("sentencepiece"):
        print("=" * 62)
        print("  环境就绪，可以用了")
        print("=" * 62)
        print("  想先在命令行看效果：")
        print('      .venv\\Scripts\\python.exe smoke_test.py')
        print("  想用网页版：双击 run.bat")
        return 0

    print("依赖装完了，但导入检查没通过，请把上面的报错发出来看看。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
