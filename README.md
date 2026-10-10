# 20 遍翻译机

输入一段中文 → 机翻成英文 → 再机翻回中文 → 再翻成英文……**往复 N 遍**，页面展示每一轮的中间结果。

它**只负责翻译，不做任何分析**：没有相似度计算、没有"收敛判定"、没有结论。每一处变化是不是有意义，由你自己看。

> **TL;DR (English)** — A local web tool that round-trips a Chinese sentence through
> open-source NMT models (OPUS-MT) for N rounds and shows every intermediate result.
> Fully offline after the first model download, CPU-only, no API keys, no web framework.
> Greedy decoding gives bit-identical repeatability; optional sampling makes every run
> differ. UI is in Chinese.

---

## 这是什么

把一个句子在中英文之间反复机翻，观察它如何逐轮漂移——这就是全部功能。它是观察"机翻误差如何在往复中累积"的实验工具，不是翻译生产工具。

核心设计立场：

- **用真正的开源机翻模型，不用大模型**。本项目使用赫尔辛基大学出品的 OPUS-MT（经典的神经网络机器翻译模型），原因有三：
  1. **可复现**：贪心解码下同一句话翻一百遍结果逐字相同，"第 3 轮和第 7 轮的差别"只能来自文本本身，不掺模型随机发挥；
  2. **离线**：模型下载一次（约 620MB）后完全本地运行，断网可用，不需要任何 API Key；
  3. **机翻的"病"更明显**：机翻模型在成语、长句、省略主语上更容易出错，翻来翻去更容易看出问题——这正是想观察的东西。
- **展示，不评判**：每步只记录「第几轮 / 方向 / 原文 / 译文 / 耗时」。输出疑似"卡带"（整段重复）时只挂个标签，不拦截、不改写。

## 特性

- 🌐 本地 Web 界面，启动即用，无构建、无 CDN、无外部依赖
- 🔁 往复轮数可调（1–50 轮，一轮 = 中→英 + 英→中两次翻译）
- ⏱️ 实时进度显示，可随时停止，已完成的轮次保留
- 🎲 两种解码模式：`greedy`（完全确定）或 `sample`（每次不同）
- 📜 每次运行自动存盘（`runs/*.json`），刷新页面不丢，可回看历史
- 📄 一键导出 Markdown 全过程；一键复制全部过程
- 🐍 后端纯 Python 标准库（`http.server`），除模型外零运行时依赖

## 快速开始

需要 Python 3.11+。依赖只有 torch + transformers + sentencepiece（约 1GB 磁盘）。

### 方式一：一键脚本（推荐，Windows）

双击 `run.bat`。它会自动创建虚拟环境、安装依赖、启动服务并打开浏览器。

### 方式二：手动

```bat
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe server.py
```

浏览器打开 **http://127.0.0.1:8000**。

> pip 直连 pypi.org 慢或失败时加国内镜像：
> `pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple`

**首次运行**需要下载两个模型（共约 620MB，默认走 [hf-mirror.com](https://hf-mirror.com) 镜像，约 10 分钟，视网络而定）。服务启动时会后台预热，页面右上角显示模型状态；下载完成后就都是本地秒开。

想先不启网页验证一下：

```bat
.venv\Scripts\python.exe smoke_test.py "要翻译的话" 3
```

它会打印全过程，并再跑一遍对比两次结果是否一致。

## 页面用法

1. 输入中文，选轮数（默认 10 轮 = 20 次翻译），点「开始翻译」。
2. 页面每秒刷新进度；可随时「停止」，已完成的轮次保留。
3. 结果分三块：**起始中文**（绿色卡片）、**最终中文结果**（蓝色卡片）、**逐轮过程**（每轮一张卡片，两栏展示中→英和英→中的原文/译文，每段可单独复制）。
4. 「复制全部过程」把整次运行拼成纯文本一次复制走；「导出 Markdown」下载成文件。
5. 底部「历史运行」可回看任意一次过去的记录。

## 确定性 vs 随机（核心设计）

「同样的输入是否得到同样的输出」由 [config.py](config.py) 里的 `DECODE_MODE` 决定：

| 模式 | 行为 | 适合观察 |
|---|---|---|
| `greedy` | 每步取概率最高的词，同输入必得同输出 | 文本**自身**会漂到哪、几轮后稳定 |
| `sample` | 按概率分布随机抽词（受 `TEMPERATURE` / `TOP_P` 控制），每次不同 | 误差如何被逐轮**放大**，每次运行都不同 |

随机性会毁掉"第 6 轮之后不再变化"这类观察信号——变化可能只是碰巧抽到同一句。所以想要严肃观察漂移，用 `greedy`；想看错误累积得更热闹，用 `sample`（可用 `RANDOM_SEED` 固定种子，让随机也可复现）。

> 仓库当前默认配置是 `sample`（temperature 0.5）。改 `config.py` 后重启服务生效。

## 配置

全部参数集中在 [config.py](config.py)：

| 想改什么 | 改哪个 |
|---|---|
| 解码方式 / 随机程度 / 随机种子 | `DECODE_MODE` / `TEMPERATURE` / `TOP_P` / `RANDOM_SEED` |
| 默认轮数 / 上限 | `DEFAULT_ROUNDS`（默认 10）/ `MAX_ROUNDS`（上限 50） |
| 模型 | `MODEL_ZH2EN` / `MODEL_EN2ZH`（可换成本地路径） |
| 端口 / 监听地址 | `PORT` / `HOST` |
| 输入字数上限 | `MAX_INPUT_CHARS`（默认 2000） |
| 模型下载源 | `HF_ENDPOINT`（默认 `https://hf-mirror.com`） |

## 项目结构

```
config.py          所有可调参数
translator.py      模型加载 + 单次翻译
pipeline.py        N 轮往复主循环（含中止支持）
store.py           运行记录：内存 + runs/*.json + Markdown 导出
server.py          本地 HTTP 服务（标准库，无 Web 框架）
smoke_test.py      命令行最小验证
web/               前端页面（手写 HTML/JS/CSS，无构建）
setup_env.bat/.py  一键建环境（建 venv → 装 pip → 装依赖）
bootstrap_pip.py   给 venv 安装 pip 的引导脚本
run.bat            一键启动 + 打开浏览器
spm_path_fix.py    Windows 中文路径兼容补丁（sentencepiece 打不开非 ASCII 路径）
ws_tmp.py          受限环境临时目录补丁（正常环境无副作用）
models/            模型缓存（约 620MB，删除后会自动重新下载）
runs/              每次运行的过程记录
_domtest/          前端渲染测试（jsdom，可选）
```

## 常见问题

**为什么输入上限是 2000 字？**
OPUS-MT 的位置编码上限是 512 token，超长输入会被硬截断并产生乱码，所以直接拦住。

**为什么同时只能跑一个任务？**
两个任务会各自把模型读进内存（312MB×2），纯属互相拖慢。第二个请求会返回提示。

**为什么有时英译中会显示「疑似整段重复」？**
机翻模型偶尔会"卡带"把同一句重复几遍。页面只标记、不拦截，是否算坏由你判断。

**最终结果怎么是英文的？**
最终输出一定是中文（第 N 轮的「英→中」结果）。如果「停止」时恰好停在中→英那一步，最终中文会是空的——再跑一次即可。

**Windows 上克隆到含中文的目录会报错？**
`sentencepiece` 的原生库在 Windows 上打不开绝对路径含非 ASCII 字符的文件（报 `NOT_FOUND: ...source.spm`）。本项目自带补丁 [spm_path_fix.py](spm_path_fix.py) 已处理此问题，无需手动操作。

## 模型与许可证

| 方向 | 模型 | 许可证 |
|---|---|---|
| 中 → 英 | [Helsinki-NLP/opus-mt-zh-en](https://huggingface.co/Helsinki-NLP/opus-mt-zh-en) | CC-BY-4.0 |
| 英 → 中 | [Helsinki-NLP/opus-mt-en-zh](https://huggingface.co/Helsinki-NLP/opus-mt-en-zh) | Apache-2.0 |

模型版权归原作者所有，本项目仅做本地加载与调用。
