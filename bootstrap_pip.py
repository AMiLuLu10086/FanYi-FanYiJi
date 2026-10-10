"""
bootstrap_pip.py — 给刚建好的 .venv 装上 pip
=============================================
一般不用手动跑，`setup_env.bat` 会调用它。

【为什么要单独装 pip】
`python -m venv .venv` 内部会调用 `ensurepip`，而 ensurepip 要往系统临时目录
`%TEMP%` 写文件。在受限环境（DSH 沙箱）下这一步会被拒绝：

    PermissionError: [Errno 13] Permission denied: '...\\Temp\\...\\pip-25.0.1-py3-none-any.whl'

用 `python -m venv --without-pip .venv` 建环境就绕开了 ensurepip，然后由本文件装 pip。

【为什么要临时写一个 sitecustomize.py】
本文件自己跑的时候，`ws_tmp.py` 的补丁是生效的；但 pip 是**独立进程**，
继承不到补丁。而 pip 内部会用 `os.mkdir(..., 0o700)` 建临时目录，
在沙箱里往这种目录写文件会被拒绝，导致安装 torch（124MB 的 wheel）必然失败：

    PermissionError: [Errno 13] Permission denied: '...\\pip-unpack-xxx\\torch-xxx.whl'

所以这里临时往 venv 的 site-packages 放一个 `sitecustomize.py`
（Python 启动时自动加载），让 pip 也带上补丁；装完立刻删掉，不留残留。
正常环境（没有沙箱）下这个补丁也没有副作用，只是不再用限制性权限建目录。
"""
from __future__ import annotations

import os
import runpy
import sys
import urllib.request
from pathlib import Path

import ws_tmp  # 必须最先 import：先修好临时目录

BASE_DIR = Path(__file__).resolve().parent
GET_PIP_URLS = [
    "https://bootstrap.pypa.io/get-pip.py",
    "https://bootstrap.pypa.io/pip/get-pip.py",
]
GET_PIP = BASE_DIR / "get-pip.py"

# 临时补丁：让 pip（独立进程）也不会用限制性权限建目录
SITECUSTOMIZE_BODY = '''"""临时补丁：由 bootstrap_pip.py 写入，用完即删。"""
import os

_original_mkdir = os.mkdir
_original_makedirs = os.makedirs

if not getattr(_original_mkdir, "_ws_patched", False):
    def _mkdir(path, mode=None, *, dir_fd=None):
        return _original_mkdir(path, dir_fd=dir_fd)

    _mkdir._ws_patched = True
    os.mkdir = _mkdir

    def _makedirs(name, mode=None, exist_ok=False):
        return _original_makedirs(name, exist_ok=exist_ok)

    _makedirs._ws_patched = True
    os.makedirs = _makedirs
'''


def _site_packages() -> Path:
    import site

    for path in site.getsitepackages():
        candidate = Path(path)
        if candidate.name == "site-packages" and candidate.is_dir():
            return candidate
    raise RuntimeError("找不到 site-packages 目录")


def _write_shim() -> Path:
    target = _site_packages() / "sitecustomize.py"
    target.write_text(SITECUSTOMIZE_BODY, encoding="utf-8")
    return target


def _remove_shim(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass


def ensure_get_pip() -> bool:
    if GET_PIP.exists() and GET_PIP.stat().st_size > 100_000:
        print(f"[1/3] get-pip.py 已存在（{GET_PIP.stat().st_size} 字节）")
        return True
    for url in GET_PIP_URLS:
        try:
            print(f"[1/3] 下载 {url} ...")
            urllib.request.urlretrieve(url, GET_PIP)  # noqa: S310
            print(f"      已保存 {GET_PIP.stat().st_size} 字节")
            return True
        except Exception as exc:
            print(f"      失败：{exc}")
    return False


def main() -> int:
    print(f"      临时目录：{ws_tmp.installed_dir}")

    if not ensure_get_pip():
        print("get-pip.py 下载失败，请检查网络。")
        return 1

    shim = _write_shim()
    print(f"[2/3] 已临时写入补丁 {shim.name}（装完会删除）")
    print("[2/3] 开始安装 pip ...")
    sys.argv = [str(GET_PIP), "--no-warn-script-location"]
    code = 0
    try:
        runpy.run_path(str(GET_PIP), run_name="__main__")
    except SystemExit as exc:
        code = int(exc.code or 0)
    except Exception as exc:
        print(f"pip 安装失败：{type(exc).__name__}: {exc}")
        code = 1
    finally:
        _remove_shim(shim)

    if code != 0:
        print(f"pip 安装失败，退出码 {code}")
        return code

    print("[3/3] 验证 pip ...")
    import subprocess

    check = subprocess.run([sys.executable, "-m", "pip", "--version"])
    return check.returncode


if __name__ == "__main__":
    raise SystemExit(main())
