"""
spm_path_fix.py — 中文路径兼容补丁（Windows 必需）
==================================================
【问题】

本项目所在路径含中文（`D:\\AAA Codex Study\\13. 20遍翻译机`），
而 `sentencepiece` 的原生库在 Windows 上无法打开**绝对路径含非 ASCII 字符**的文件：

    RuntimeError: NOT_FOUND: "...\\13. 20遍翻译机\\...\\source.spm": No such file or directory

文件明明存在、Python 自己也能读取（实测 `open()`/`GetShortPathNameW` 都正常），
只有 sentencepiece 打不开。短路径、目录联接（junction）都试过，均无效。

【绕法】

实测：把工作目录切到该文件所在目录，再用**相对文件名**调用 `Load()`，就正常了。

由于 OPUS-MT 模型（MarianTokenizer）恰好就是在模型目录里加载
`source.spm` / `target.spm` 这两个文件，所以只要把 Marian 内部的
`load_spm` 包一层：切目录 → 用相对名加载 → 切回来，就能绕开。
加载完的处理器不依赖当前目录，之后没有任何副作用。

在 `import transformers` 之前 `import spm_path_fix` 即可。
"""
from __future__ import annotations

import os
import threading
from contextlib import contextmanager

_lock = threading.RLock()


@contextmanager
def _chdir(path: str):
    """临时切换工作目录（带锁：进程内工作目录是全局状态）。"""
    with _lock:
        previous = os.getcwd()
        os.chdir(path)
        try:
            yield
        finally:
            os.chdir(previous)


def install() -> bool:
    """给 MarianTokenizer 打上面说的补丁。返回是否已生效。"""
    try:
        from transformers.models.marian import tokenization_marian as marian
    except ImportError:  # 万一 transformers 内部结构调整
        return False

    if getattr(marian.load_spm, "_spm_path_fixed", False):
        return True

    original_load_spm = marian.load_spm

    def load_spm(path: str, sp_model_kwargs: dict):
        directory, filename = os.path.split(path)
        if not directory:
            return original_load_spm(path, sp_model_kwargs)
        # 切到文件所在目录，用纯文件名加载：绕开 sentencepiece 的中文绝对路径问题
        with _chdir(directory):
            return original_load_spm(filename, sp_model_kwargs)

    load_spm._spm_path_fixed = True  # type: ignore[attr-defined]
    marian.load_spm = load_spm  # type: ignore[assignment]
    return True


installed = install()
