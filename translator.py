"""
translator.py — 翻译引擎（模型加载 + 单次翻译）
================================================
职责很小：给一段文字和方向，返回译文。不关心轮次、不关心网页。

【为什么用 OPUS-MT 这种"机翻模型"而不是大模型】
大模型每次回答都带随机性，而且"20 遍之后的差别"里混着它自己发挥的成分，
没法判断差别到底来自哪里。OPUS-MT 是确定性的：同样的输入永远得到同样的输出，
所以第 3 轮和第 7 轮之间出现的任何变化，都是文本自身被翻来翻去翻出来的。
这就是本项目的实验前提，改解码参数会直接毁掉这个前提（见 config.py 注释）。
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass

import config  # 必须最先 import：它会先设好 HF_ENDPOINT / HF_HOME
import spm_path_fix  # 必须在 import transformers 之前：中文路径兼容补丁

import torch  # noqa: E402
from transformers import MarianMTModel, MarianTokenizer  # noqa: E402

# 方向名 → 用哪个模型。避免满代码里写字符串拼错。
DIRECTION_MODEL = {
    "zh2en": config.MODEL_ZH2EN,
    "en2zh": config.MODEL_EN2ZH,
}

DIRECTION_LABEL = {
    "zh2en": "中 → 英",
    "en2zh": "英 → 中",
}

DECODE_MODE_LABEL = {
    "greedy": "确定模式（同输入必得同输出）",
    "sample": "随机模式（每次翻译都可能不同）",
}


def is_sampling() -> bool:
    """当前是不是"每次结果都不一样"的采样模式（见 config.DECODE_MODE）。"""
    return str(getattr(config, "DECODE_MODE", "greedy")).lower() == "sample"


def decode_mode_name() -> str:
    """当前解码方式的代号：greedy / sample。"""
    return "sample" if is_sampling() else "greedy"


def decode_mode_label() -> str:
    """解码方式的中文说明。"""
    return DECODE_MODE_LABEL[decode_mode_name()]


class ModelUnavailable(RuntimeError):
    """模型下载或加载失败，通常是网络问题。给用户看的话写在 message 里。"""


@dataclass
class Translation:
    """一次翻译的结果。"""
    text: str
    ms: int
    degenerate: bool = False   # 输出是否出现整段重复（照实标记，不做结论）


class _Engine:
    """按方向懒加载模型，全局单例，线程安全。

    模型只在第一次用到时加载（约 312MB 读盘，几秒），之后常驻内存。
    """

    def __init__(self) -> None:
        self._cache: dict[str, tuple] = {}
        self._lock = threading.Lock()
        # 给网页显示状态用：idle / loading / ready / error
        self.status = "idle"
        self.status_detail = ""

    def _load(self, direction: str) -> tuple:
        model_name = DIRECTION_MODEL[direction]
        with self._lock:
            if direction in self._cache:
                return self._cache[direction]
            self.status = "loading"
            self.status_detail = f"正在加载模型 {model_name}（首次运行需要下载约 312MB）"
            try:
                tokenizer = MarianTokenizer.from_pretrained(model_name)
                model = MarianMTModel.from_pretrained(model_name)
                model.eval()
            except Exception as exc:  # 网络 / 磁盘 / 文件损坏都归到这里
                self.status = "error"
                self.status_detail = str(exc)
                raise ModelUnavailable(
                    f"加载模型 {model_name} 失败：{exc}\n"
                    f"请检查网络。本项目默认走镜像 {config.HF_ENDPOINT}；"
                    f"如果镜像也不通，可以手动把模型下载到 {config.MODELS_DIR}。"
                ) from exc
            self._cache[direction] = (tokenizer, model)
            self.status = "ready"
            self.status_detail = "模型已就绪"
            return self._cache[direction]

    def translate(self, text: str, direction: str) -> Translation:
        if direction not in DIRECTION_MODEL:
            raise ValueError(f"未知方向：{direction}")

        text = (text or "").strip()
        if not text:
            # 空白输入不交给模型：OPUS-MT 遇到空输入会输出奇怪的东西
            return Translation(text="", ms=0)

        tokenizer, model = self._load(direction)
        started = time.perf_counter()

        batch = tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=config.MAX_INPUT_TOKENS,
        )
        input_tokens = int(batch["input_ids"].shape[-1])
        max_new_tokens = min(
            max(16, input_tokens * config.OUTPUT_TOKEN_FACTOR),
            config.MAX_INPUT_TOKENS,
        )

        generation_kwargs = {
            "max_new_tokens": max_new_tokens,
            # 显式置空，避免和模型自带的 max_length 冲突产生提示
            "max_length": None,
        }
        if is_sampling():
            # 采样：每次结果都可能不同
            generation_kwargs.update(
                do_sample=True,
                temperature=config.TEMPERATURE,
                top_p=config.TOP_P,
                num_beams=1,
            )
        else:
            # 贪心：同样输入永远同样输出
            generation_kwargs.update(do_sample=False, num_beams=1)

        with self._lock:  # torch 模型不是线程安全的，串行调用
            if config.RANDOM_SEED is not None:
                # 固定种子：即使是采样模式也能复现
                torch.manual_seed(int(config.RANDOM_SEED))
            generated = model.generate(**batch, **generation_kwargs)

        out = tokenizer.batch_decode(generated, skip_special_tokens=True)
        result = (out[0] if out else "").strip()
        ms = int((time.perf_counter() - started) * 1000)

        return Translation(text=result, ms=ms, degenerate=_looks_degenerate(result))


_engine = _Engine()


def translate(text: str, direction: str) -> Translation:
    """翻译一段文字。direction 是 "zh2en" 或 "en2zh"。"""
    return _engine.translate(text, direction)


def warmup() -> None:
    """提前把两个模型加载进内存，避免第一次点「开始翻译」时干等。"""
    _engine.translate("测试", "zh2en")
    _engine.translate("test", "en2zh")


def engine_status() -> dict:
    return {"status": _engine.status, "detail": _engine.status_detail}


def _looks_degenerate(text: str) -> bool:
    """粗糙地判断输出是不是"卡带"了（整句重复好几遍）。

    只做标记，不拦截、不改写：结果照实给你看，是否算坏由你自己判断。
    """
    n = len(text)
    if n < 40:
        return False
    head = text[: n // 3].strip()
    if len(head) < 6:
        return False
    return text.count(head) >= 3
