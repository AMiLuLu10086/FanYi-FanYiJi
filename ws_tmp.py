"""
ws_tmp.py — 临时目录与目录权限修正（Windows 沙箱环境需要）
==========================================================
【为什么需要这个文件】

在 DSH 的 Windows 沙箱下，有一类很隐蔽的"权限被拒"问题，实测规律是：

    用 os.mkdir(path, 0o700) 建出来的目录 → 往里写文件会被拒绝（哪怕只是个 1KB 文件）
    用 os.mkdir(path, 0o777/0o755) 或直接 os.mkdir(path) 建的目录 → 正常读写

而 `tempfile.mkdtemp()` 恰好就是用 0o700 建目录的（POSIX 习惯），
于是 pip 安装、模型下载解压这类"先建临时目录再写大文件"的操作全部报：

    PermissionError: [Errno 13] Permission denied: '...\\pip-unpack-xxx\\torch-xxx.whl'

表现为 pip 反复失败、看起来像"卡住不动"。

【解决办法】

1. 把临时目录固定到项目内的 `.wtmp\\`（默认的 %TEMP% 在沙箱里根本不让写）；
2. 把 `os.mkdir` / `os.makedirs` / `tempfile.mkdtemp` 包一层，**丢掉限制性的权限参数**，
   让目录按 Windows 默认权限创建并正常继承父目录权限。

任何入口（server.py / smoke_test.py / bootstrap_pip.py / 装依赖）在用到
pip、下载、解压之前 `import ws_tmp` 即可。对正常环境无害：不限制权限只会让
目录更好访问，不会坏任何东西。
"""
from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
WS_TMP = BASE_DIR / ".wtmp"

_original_mkdir = os.mkdir
_original_makedirs = os.makedirs


def install() -> Path:
    """把临时目录指向项目内 .wtmp，并修掉限制性权限导致的写入被拒。"""
    WS_TMP.mkdir(parents=True, exist_ok=True)

    os.environ["TEMP"] = str(WS_TMP)
    os.environ["TMP"] = str(WS_TMP)
    os.environ["TMPDIR"] = str(WS_TMP)
    tempfile.tempdir = str(WS_TMP)

    if not getattr(os.mkdir, "_ws_tmp_patched", False):
        def mkdir(path, mode=None, *, dir_fd=None):  # type: ignore[no-untyped-def]
            # 丢掉 mode：0o700 这类限制性权限会让沙箱拒绝后续写入
            return _original_mkdir(path, dir_fd=dir_fd)

        mkdir._ws_tmp_patched = True  # type: ignore[attr-defined]
        os.mkdir = mkdir  # type: ignore[assignment]

    if not getattr(os.makedirs, "_ws_tmp_patched", False):
        def makedirs(name, mode=None, exist_ok=False):  # type: ignore[no-untyped-def]
            return _original_makedirs(name, exist_ok=exist_ok)

        makedirs._ws_tmp_patched = True  # type: ignore[attr-defined]
        os.makedirs = makedirs  # type: ignore[assignment]

    def _mkdtemp(suffix: str | None = None, prefix: str | None = None, dir: str | None = None) -> str:  # type: ignore[override]
        base = dir or tempfile.gettempdir()
        prefix = prefix or "tmp"
        suffix = suffix or ""
        for _ in range(100):
            candidate = os.path.join(base, f"{prefix}{uuid.uuid4().hex[:8]}{suffix}")
            try:
                os.makedirs(candidate)
            except FileExistsError:
                continue
            return candidate
        raise FileExistsError(f"在 {base} 下创建临时目录失败")

    tempfile.mkdtemp = _mkdtemp  # type: ignore[assignment]
    return WS_TMP


installed_dir = install()
