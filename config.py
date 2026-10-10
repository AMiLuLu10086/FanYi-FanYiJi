"""
config.py — 所有可调参数集中在这一个文件里
==========================================
想换模型、改默认轮数、改端口，只改这里，其它文件不用动。

【重要】HF_ENDPOINT 必须在 import transformers 之前设进环境变量才生效，
所以本项目所有入口脚本（server.py / smoke_test.py）都先 `import config` 再
import transformers。别把顺序写反了，否则下载模型会卡住或直接失败。
"""
from pathlib import Path
import os

# ── 目录 ──
BASE_DIR = Path(__file__).resolve().parent
MODELS_DIR = BASE_DIR / "models"        # HuggingFace 模型缓存（约 624MB，删掉即干净）
RUNS_DIR = BASE_DIR / "runs"            # 每次运行的过程记录
WEB_DIR = BASE_DIR / "web"              # 前端静态文件

# ── 模型下载源 ──
# 国内直连 huggingface.co 不通，实测 hf-mirror.com 可用。
# 把它设进环境变量，transformers / huggingface_hub 会自动走镜像。
HF_ENDPOINT = "https://hf-mirror.com"
os.environ.setdefault("HF_ENDPOINT", HF_ENDPOINT)
os.environ.setdefault("HF_HOME", str(MODELS_DIR))
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

# ── 翻译模型（OPUS-MT，各约 312MB）──
MODEL_ZH2EN = "Helsinki-NLP/opus-mt-zh-en"   # 中文 → 英文
MODEL_EN2ZH = "Helsinki-NLP/opus-mt-en-zh"   # 英文 → 中文

# ── 解码方式：决定「同样的输入是否得到同样的输出」 ──
#
# "greedy"（默认）= 贪心解码：每一步都挑概率最高的词 → 完全确定，
#     同一句话翻一百遍结果逐字相同。这样你看到的每一处变化都只可能是
#     文本被反复翻出来的，不会掺进"这次随机抽到的"这种噪音。
#
# "sample" = 采样解码：按概率分布随机抽词 → 每次结果都不一样。
#     想看"漂移"更热闹就换成这个。实测的甜点参数见下面两个值：
#       temperature=0.8、top_p=0.95 → 有变化，前几轮还保留句子结构
#       temperature 提到 1.5 以上 → 变化更多，但很快翻出明显错误
#     注意 1：OPUS-MT 这类机翻模型原本就是按"每步取最优"训练的，
#             采样属于非常规用法，质量必然比贪心差一些。
#     注意 2：采样会让"错误累积"变快——实测往复几轮后就可能翻成完全无关的句子。
#             这不是 bug，正是"20 遍往复"这个实验最直观的看点。
#
# 想换成每次都不一样：把下面这行改成 DECODE_MODE = "sample"
DECODE_MODE = "sample"

# --- 下面两项只在 DECODE_MODE = "sample" 时生效 ---
TEMPERATURE = 0.5     # 越大越随机。0.8 左右：有变化，且前几轮还保留句子结构
TOP_P = 0.95          # 只从累计概率前 95% 的词里抽（防止抽到离谱的词）

# --- 可选：固定随机种子（设成整数则采样也可复现；设成 None 则每次都不同）---
# 想让「每次都不一样」就保持 None；想复现某次结果就填一个整数。
RANDOM_SEED = None

MAX_INPUT_TOKENS = 512        # OPUS-MT 的位置编码上限，超过会被截断
MAX_INPUT_CHARS = 2000        # 网页输入框的字数上限（中文字数）
OUTPUT_TOKEN_FACTOR = 4       # 输出上限 = 输入 token 数 × 4，防止模型跑飞

# ── 轮数 ──
# 一轮 = 中文→英文 + 英文→中文（两次模型调用）。
# 默认 10 轮（20 次翻译）；想严格跑 20 轮就填 20。
DEFAULT_ROUNDS = 10
MAX_ROUNDS = 50

# ── 服务 ──
HOST = "127.0.0.1"
PORT = 8000
