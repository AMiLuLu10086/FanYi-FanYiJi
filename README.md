# 20 遍翻译机

输入一段中文 → 机翻成英文 → 再机翻回中文 → 再翻成英文…… **往复 N 遍** → 输出最终的中文。
每一轮的中间结果都保留在页面上，你自己逐轮看。

**它只负责翻译，不替你做任何对比分析**：没有相似度、没有"收敛判定"、没有结论。

> **English TL;DR** — A local web tool that runs a Chinese↔English round-trip through
> open-source NMT models (OPUS-MT) for N rounds and shows every intermediate result.
> Fully offline after the first model download, CPU-only, and deterministic by default
> (greedy decoding) so that every observed change comes from the text itself rather than
> from sampling noise. Optional sampling mode makes each run differ. UI is in Chinese.
> The docs below are in Chinese; `config.py` is the single place to change settings.

---

## 一、它用的是什么翻译？

用的是**真正的开源机器翻译模型** OPUS-MT（赫尔辛基大学出品），不是 AI 大模型：

| 方向 | 模型 | 体积 |
|---|---|---|
| 中 → 英 | `Helsinki-NLP/opus-mt-zh-en` | 312 MB |
| 英 → 中 | `Helsinki-NLP/opus-mt-en-zh` | 312 MB |

为什么不用大模型（ChatGPT / DeepSeek 之类）？

1. **可复现**。本项目用的是贪心解码（`num_beams=1`，不开采样），
   同一句话翻一百遍结果完全一样。这样"第 3 轮和第 7 轮之间的差别"才是
   文本被反复翻译**真实翻出来的**，而不是模型每次随机发挥出来的。
2. **离线**。模型下载完就完全本地运行，断网也能用。
3. **机翻的"病"更明显**。机翻模型在成语、长句、省略主语上更容易出错，
   翻来翻去更容易看出问题——这本来就是你想观察的东西。

许可证提醒：中→英那个模型是 **CC-BY-4.0**，英→中是 **Apache-2.0**。自己研究使用没问题。

---

## 二、跑起来

### 方式一：一键脚本（推荐）

双击 **`run.bat`**。它会自动建虚拟环境、装依赖、启动服务并打开浏览器。

### 方式二：手动四步

```bat
:: 1. 建虚拟环境（故意不加 pip，原因见下面「踩过的坑」）
::    开头的 python 换成你自己机器上的 Python 3.11+ 解释器路径
python -m venv --without-pip .venv

:: 2. 装 pip
.venv\Scripts\python.exe bootstrap_pip.py

:: 3. 装依赖（torch 约 124MB，装完占约 2.5GB）
.venv\Scripts\python.exe -m pip install -r requirements.txt

:: 4. 启动
.venv\Scripts\python.exe server.py
```

浏览器打开 **http://127.0.0.1:8000**。

> 如果 pip 直连 pypi.org 很慢或卡住，加上国内镜像：
> `-i https://pypi.tuna.tsinghua.edu.cn/simple`
> （`setup_env.py` 会自动写入 `.venv\pip.ini`，用脚本建环境就不用管）

### 先命令行验证一下（可选）

```bat
.venv\Scripts\python.exe smoke_test.py
```

它会翻 2 轮打印全过程，并且**再翻一遍对比**，确认"同样的输入得到同样的输出"。
想换文本和轮数：`smoke_test.py "要翻译的话" 3`

---

## 三、页面怎么用

1. 输入中文，选择**翻几遍**（默认 10 轮 = 20 次翻译）。
2. 点「开始翻译」。页面每秒刷新一次进度，显示「已完成 x/y 次翻译（正在第 N 轮）」，
   可以随时点「停止」，已完成的轮次会保留。
3. 页面上依次能看到三块结果：
   - **起始中文**（最上面，绿色卡片）——你最初输入的那段，可一键复制；
   - **最终中文结果**（蓝色卡片）——第 N 轮「英 → 中」的产物，可一键复制；
   - **逐轮过程**——每一轮一张卡片，卡片里是两栏：
     | 栏位 | 内容 |
     |---|---|
     | **中 → 英** | 原文（本轮中文）、译文（英文） |
     | **英 → 中** | 原文（英文）、译文（中文） |
     每段文字旁边都有「复制」小按钮；卡片右上角标了该轮两半的合计耗时。
     如果某次输出疑似整段重复，会挂一个「疑似整段重复」的小标签（只是标记，
     不改写、不拦截）。
4. 顶部还有一颗「**复制全部过程**」按钮：把起始中文 + 最终中文 + 全部轮次的
   原文/译文拼成一段纯文本一次性复制走，方便粘到别处。
5. 底部可以：
   - 从「历史运行」里翻回以前任意一次的过程；
   - 「导出 Markdown」把整轮过程下载成文件。

> 10 轮 = 20 次翻译，所以逐轮区一共 20 个「原文/译文」对。想看更长链条就把
> 「翻几遍」调大（上限 50 轮 = 100 次翻译）。

每次跑完的记录会自动存到项目的 `runs/` 目录（JSON 格式），刷新页面不会丢。

---

## 四、想改东西改哪里

全部参数集中在 **`config.py`**：

| 想改什么 | 改哪个 |
|---|---|
| **每次结果是否不一样** | `DECODE_MODE`：`"greedy"` 确定 / `"sample"` 随机（见第六节 6.5） |
| 随机程度 | `TEMPERATURE`（越大越随机）、`TOP_P` |
| 想让随机也可复现 | `RANDOM_SEED` 填一个整数；填 `None` 则每次都不同 |
| 默认翻几遍 | `DEFAULT_ROUNDS`（默认 10，上限 `MAX_ROUNDS` = 50） |
| 换模型 | `MODEL_ZH2EN` / `MODEL_EN2ZH` |
| 换端口 | `PORT`（默认 8000） |
| 输入字数上限 | `MAX_INPUT_CHARS`（默认 2000） |
| 模型下载源 | `HF_ENDPOINT`（默认国内镜像 `hf-mirror.com`） |

**改完要重启服务**才生效（`run.bat` 要先关掉旧窗口）。

当前用的哪种解码方式，页面上**不显示**（按使用者要求去掉了），想看有两个办法：

```bat
.venv\Scripts\python.exe smoke_test.py 你好 1
```

第一行就会打印「解码方式：随机模式（每次翻译都可能不同）」或「确定模式」；
或者直接看 `config.py` 里的 `DECODE_MODE`。

---

## 五、目录说明

```
config.py          所有可调参数
translator.py      模型加载 + 单次翻译
pipeline.py        N 轮往复主循环（含中止支持）
store.py           运行记录：内存 + runs/*.json + Markdown 导出
server.py          本地 HTTP 服务（标准库，无 Web 框架）
smoke_test.py      命令行最小验证
setup_env.bat      建环境（双击即可，中文提示由 setup_env.py 打印）
setup_env.py       建环境的实际逻辑：建 .venv → 装 pip → 装依赖
bootstrap_pip.py   给 .venv 装 pip（见下节）
run.bat            一键：检查环境 + 启动 + 打开浏览器
ws_tmp.py          临时目录修正（沙箱环境需要）
spm_path_fix.py    中文路径兼容补丁（Windows 需要）
web/               前端页面（纯手写，无 CDN、无构建）
_domtest/          前端渲染测试（jsdom，可选，见该目录 README）
models/            模型缓存（约 670MB，删掉会重新下载）
runs/              每次运行的过程记录
.wtmp/             运行期临时目录（可随时删）
```

---

## 六、踩过的坑（都是实测踩出来的，记下来省得再踩）

### 1. 为什么依赖要 2.5GB？

`torch`（PyTorch）是个"万能计算器"，要同时支持图像、语音、大模型、显卡等各种场景，
所以装到硬盘上会膨胀到约 2.5GB，而本项目实际只用到其中很小一部分。
**换更小的模型并不能减小它**——模型是"数字"，torch 才是"计算器"。
真想瘦身只能改用专用推理引擎（ONNX / CTranslate2，约 200MB），
代价是分词和解码要自己写。

### 2. 为什么建虚拟环境要分两步（`--without-pip` + `bootstrap_pip.py`）？

`python -m venv .venv` 内部会调用 `ensurepip`，而 `ensurepip` 要往
系统临时目录 `%TEMP%` 写文件。在受限环境下这一步会被拒绝：

```
PermissionError: [Errno 13] Permission denied: '...\Temp\...\pip-25.0.1-py3-none-any.whl'
```

`--without-pip` 不碰 `ensurepip`，所以能成功；pip 由 `bootstrap_pip.py` 另装。

### 3. 为什么会有 `ws_tmp.py` 和临时 `sitecustomize.py`？

受限环境里有个很隐蔽的规律（实测）：

| 建目录方式 | 能否往里写文件 |
|---|---|
| `os.mkdir(path, 0o700)` | **不能**（哪怕只写 1KB 也报 Permission denied） |
| `os.mkdir(path)` / `0o777` / `0o755` | 能 |

而 Python 的 `tempfile.mkdtemp()` 恰好用 0o700 建目录，pip 解包 wheel 也这么干。
于是安装 torch（124MB 的 wheel）时必失败，表现为 pip 反复报错、看起来像"卡死"。

`ws_tmp.py` 把 `os.mkdir`/`os.makedirs` 包一层、丢掉限制性权限参数，
并让入口脚本（`server.py` / `smoke_test.py` / `setup_env.py`）先 `import ws_tmp`。

pip 是独立进程，继承不到内存里的补丁，所以 `bootstrap_pip.py` 在装 pip 期间会
**临时写入**一个 `sitecustomize.py`（Python 启动时自动加载，pip 因此也带上补丁），
装完立即删除。这里有个先有鸡后有蛋的坑：这个临时文件不能预先放在
`.venv\Lib\site-packages` 里，否则 `python -m venv` 复制环境时会报
`[Errno 2] No such file or directory` 而无法创建环境。

> 正常环境（没开沙箱）下这套东西无害，只是把临时目录放在项目内的 `.wtmp\`。

### 3.5 为什么 `.bat` 文件里一个中文都没有？

cmd.exe 在中文 Windows 上按 **GBK** 解码批处理文件，而本项目文件是 UTF-8。
UTF-8 的中文被当 GBK 读会变成乱码字节，其中有些字节恰好是 `<` `>` `|` `&`
这类批处理语法符号，于是 cmd 把它们当命令去执行，刷出一屏：

```
'0' 不是内部或外部命令，也不是可运行的程序
'亾鍦ㄨ闀滃儚涓婃瀬鎱紝鍏虫帀' 不是内部或外部命令
```

**功能不受影响**，但很难看、也可能在某些机器上真的中断脚本。
所以两个 `.bat` 只保留纯英文（已用脚本校验过：0 个非 ASCII 字节），
所有中文提示都改由 Python 打印（Python 走 UTF-8，不受 cmd 解码影响）。

### 4. 中文路径 + sentencepiece：最坑的一个

项目路径里含中文（`13. 20遍翻译机`）时，`sentencepiece` 的原生库会打不开模型词表：

```
RuntimeError: NOT_FOUND: "...\13. 20遍翻译机\...\source.spm": No such file or directory
```

但文件明明存在、Python 自己能读（`open()` 正常、`GetShortPathNameW` 拿短路径也无效、
目录联接 junction 也无效）。**只有 sentencepiece 打不开。**

实测有效的绕法：**先切到该文件所在目录，再用相对文件名加载**。
`spm_path_fix.py` 就是把 Marian 分词器内部的 `load_spm` 包了一层：
切目录 → 用纯文件名加载 → 切回来。

### 5. 模型下载：为什么默认走 `hf-mirror.com`

本机直连 `huggingface.co` 不通，`hf-mirror.com` 通。另外 huggingface_hub 默认启用的
xet 传输通道在这个镜像上极慢（实测 0.08 MB/s，会把 670MB 拖成两小时），
所以：

```bat
set HF_HUB_DISABLE_XET=1
```

本项目在 `config.py` 里已经设好 `HF_ENDPOINT`，`server.py` 也建议带上
`HF_HUB_DISABLE_XET=1`（`run.bat` 已包含）。常规 HTTP 实测约 1.1 MB/s，
两个模型共约 10 分钟。

如果镜像也不通，可以手动下载这两个仓库里的文件（`config.json`、`tokenizer_config.json`、
`vocab.json`、`source.spm`、`target.spm`、`pytorch_model.bin`），
放进 `models/` 下对应目录，再改 `config.py` 里的模型名为本地路径。

### 6. 首次运行会慢

第一次点「开始翻译」要下载两个模型（约 670MB）。服务启动时会自动后台预热，
页面右上角能看到「模型状态」。之后就都是本地秒开。

### 6.5 「每次翻译结果都一样」是怎么回事 / 怎么让它不一样

**默认就是这样，而且是故意的。** 现在的解码方式是**贪心**（`DECODE_MODE = "greedy"`）：
每一步都挑概率最高的那个词，所以同一句话翻一百遍结果逐字相同。

商用翻译软件每次都不同，是因为它们用了带随机性的解码（采样 / 多引擎投票）、
或者服务端模型会更新。**但随机性会毁掉这个项目唯一值得观察的信号**：
如果每次翻都带随机波动，你就分不清"第 6 轮之后不再变化"到底是
**文本真的稳定了**，还是**随机碰巧抽到同一句**。

#### 想让它每次都不一样

改 `config.py` 一行：

```python
DECODE_MODE = "sample"      # 默认是 "greedy"
TEMPERATURE = 0.8           # 越大越随机
```

改完重启服务生效。（页面上不会显示当前是哪种模式；想知道就跑一次
`smoke_test.py`，它第一行会打印出来。）

原理：把"每步取最优"换成"按概率分布随机抽词"，于是同样的输入每次抽出来的
句子都可能不同。实测参数效果（同一句话连翻 4 次）：

| 参数 | 4 次里出现几种 | 译文质量 |
|---|---|---|
| 贪心（默认） | 1 种 | 稳定 |
| `temperature=0.8, top_p=0.95` | 2~4 种 | 前几轮仍保留句子结构 |
| `temperature=1.0, top_p=0.95` | 2 种 | 基本正常，多在缩写/同义词上变 |
| `temperature=1.5, top_p=1.0` | 4 种 | 开始出明显错误 |

#### 换成随机之后会看到什么（实测）

用 `temperature=0.8` 往复同一句话，4 轮的结果：

| 轮次 | 英 → 中 |
|---|---|
| 输入 | 下面这句话里有个成语：亡羊补牢，为时未晚 |
| 第 1 轮 | 该句强调指出:为死者补偿遗憾已经不晚了 |
| 第 2 轮 | 这一句强烈表示,死者遗体再补充已不晚 |
| 第 3 轮 | 这一句强烈表明,死尸再补充没有太晚 |
| 第 4 轮 | 这句强烈的论点指出,没有对死尸进行迟后或重新补充 |

可以看到「亡羊补牢」被机翻理解成"补偿死者"，然后这个误解被**逐轮放大**。
同一个输入再跑一次，最终中文完全又是另一句。

**这不是 bug，这正是"20 遍往复"最直观的看点**：随机性让错误累积得更快，
你能清楚看到一句话是怎么被翻着翻着翻没的。

#### 两种模式怎么选

| 你想干什么 | 用哪个模式 |
|---|---|
| 观察"文本自身"会让句子漂到哪、几轮稳定 | `greedy`（默认） |
| 看错误怎么被逐轮放大、每轮都不同更热闹 | `sample` |
| 想要随机但又要能复现某一次结果 | `sample` + `RANDOM_SEED = 12345` |

### 8. 为什么不能用真浏览器做自动化测试

Chromium 系浏览器（Edge / Chrome）的多进程架构依赖 Windows 命名管道做进程间通信，
而这个受限环境不允许，启动时会直接 FATAL：

```
FATAL:mojo\public\cpp\platform\platform_channel.cc:183 Check failed: . : 拒绝访问。 (0x5)
```

所以前端验证改用 **jsdom**（真实 DOM 实现，跑应用自己的渲染代码），
脚本放在 `_domtest/`，用法见 `_domtest/README.md`。
真实的视觉样式和鼠标手感 jsdom 测不了，那部分需要人眼确认。

### 9. 同一个端口上跑出多个服务（已修）

Windows 上 `allow_reuse_address`（对应 `SO_REUSEADDR`）会让**第二个进程也能绑上
同一个端口**，于是一个端口上同时有多个服务在监听、请求被最旧的那个接走，
表现为"改完代码重启却看不到任何变化"，非常难排查。

`server.py` 已经去掉这个设置，现在重复启动会直接报"端口被占用"，一眼就知道
该先关掉旧窗口。如果你确实遇到页面行为跟代码对不上，先检查是不是有多个实例：

```bat
netstat -ano | findstr ":8000" | findstr LISTENING
```

---

## 七、这些东西占了多少硬盘，放在哪

实测数据（单位 MB）：

| 位置 | 内容 | 体积 |
|---|---|---|
| `.venv\` | Python 依赖（torch 501、transformers 100、sympy 66、numpy 51…） | **819** |
| `models\hub\` | 两个翻译模型的权重 | **601** |
| 源码 + 网页 + 脚本 | 本项目自己写的代码 | 约 2.4 |
| `runs\` | 运行记录（JSON） | 约 0.1 |
| **项目合计** | | **约 1423** |

模型权重明细（每个模型约 300MB）：

```
models\hub\models--Helsinki-NLP--opus-mt-zh-en\
    snapshots\<哈希>\pytorch_model.bin   297.6 MB  ← 程序实际加载的就是它
    snapshots\<哈希>\source.spm / target.spm / vocab.json  ≈ 3 MB
```

**代码里没有任何地方引用 safetensors**，而这两个模型仓库的 `config.json` 里也没有
登记 safetensors 文件，所以加载器只会读 `pytorch_model.bin`。
如果你在 `models\` 里看到多余的 `model.safetensors`（各约 297MB），删掉不影响使用——
它们是早期下载遗留的，实测删掉后翻译完全正常。

### 可以放心删的

| 删什么 | 省多少 | 删了的影响 |
|---|---|---|
| `models\**\model.safetensors` | 595 MB | 无 |
| `_domtest\node_modules\` + `.pnpm-store\` | 约 60 MB | 无；重跑前端测试时按 `_domtest/README.md` 重装 |
| 整个 `models\` | 601 MB | 下次运行自动重新下载（约 10 分钟） |

### 别删的

| 别删 | 为什么 |
|---|---|
| `.venv\` | 删了要重装依赖（torch 要下 124MB） |
| `models\**\pytorch_model.bin` | 程序实际加载的权重 |
| `get-pip.py` | `bootstrap_pip.py` 重建环境时要用 |
| `.wtmp\` | 运行期临时目录，程序自己在用 |

> 另外还会在 **C 盘**留一份 pip 下载缓存（`%LOCALAPPDATA%\pip\Cache`，约 170MB），
> 那是所有 Python 项目共用的全局缓存，装完就没用但删不删都行。

---

## 八、怎么把它放到 GitHub 上

仓库已经初始化好了（`git init`，默认分支 `main`，`.gitignore` 也写好了），
**大文件都不会被上传**：实测待提交 23 个源文件、合计约 110 KB。

### 1. 先在 GitHub 网页上建一个空仓库

打开 <https://github.com/new>：

- **Repository name**：`translation-loop` 或 `20x-translation-machine`（名字随便）
- **Public / Private**：自选
- **不要**勾选 "Add a README file"、".gitignore"、"license"（本地已有文件，勾了会冲突）

### 2. 在项目目录里执行（把 URL 换成你自己的）

```bat
git commit -m "feat: 中文↔英文往复翻译机（OPUS-MT，本地运行）"
git remote add origin https://github.com/你的用户名/仓库名.git
git push -u origin main
```

推送时会弹窗要 GitHub 账号密码——**密码要填 Personal Access Token**，不是登录密码。
在 <https://github.com/settings/tokens> 生成一个，勾 `repo` 权限即可。

### 3. 之后每次改动

```bat
git add -A
git commit -m "说明这次改了什么"
git push
```

### 想换成 SSH（免输 token，推荐长期用）

```bat
git remote set-url origin git@github.com:你的用户名/仓库名.git
```

先把本机的 SSH 公钥（`C:\Users\你\.ssh\id_ed25519.pub`）加到
<https://github.com/settings/keys>。没有公钥就先跑 `ssh-keygen -t ed25519 -C "你的邮箱"`。

### 会用到的 git 命令速查

| 命令 | 作用 |
|---|---|
| `git status` | 看哪些文件被改了 |
| `git add -A` | 把所有改动加入待提交 |
| `git commit -m "..."` | 提交（形成一次历史记录） |
| `git push` | 推到 GitHub |
| `git log --oneline` | 看提交历史 |
| `git diff` | 看还没提交的改动内容 |

### 提交前请确认这几点

- **`.venv\`、`models\`、`runs\` 不会上传**（已在 `.gitignore` 里）。模型 601MB、
  虚拟环境 819MB，都被拦住，否则会超过 GitHub 的单文件 100MB 限制。
- **没有密钥泄漏**：本项目不需要任何 API Key（模型是本地离线跑的），已扫描确认。
- `get-pip.py` 也不上传（是安装脚本自动下载的引导文件）；`bootstrap_pip.py`
  在需要时会自动把它下载回来。
- 别人克隆后在**他们的机器上**跑，需要他们自己的 Python 环境；
  `setup_env.bat` 会自动找 Python（也支持用环境变量 `PYTHON_HOME` 指定）。

---

## 九、常见问题

**问：为什么输入不能超过 2000 字？**
OPUS-MT 的位置编码上限是 512 个 token，超了会被硬截断并产生乱码输出。
与其给你一段垃圾，不如直接拦住。

**问：为什么有时候英译中会显示「疑似整段重复」？**
机翻模型偶尔会"卡带"，把同一句重复好几遍。页面只做**标记**，不拦截、不改写，
是否算坏了由你自己判断。

**问：为什么同时只能跑一个任务？**
两个任务会各自把 312MB×2 的模型读进内存，纯属互相拖慢。第二个请求会返回提示。

**问：结果怎么是英文的？**
最终输出一定是中文（第 N 轮的「英 → 中」结果）。如果你点「停止」停在了
「中 → 英」那一步，最终中文会是空着的——再跑一次即可。
