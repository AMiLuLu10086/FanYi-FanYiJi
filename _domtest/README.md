# 前端渲染测试（可选）

这里放的是**真实 DOM 环境**下的渲染测试：用 jsdom 加载 `web/index.html` 和
`web/app.js`，连上正在运行的本地服务，实际触发一次翻译，然后检查页面上
是否出现了每一轮的「原文/译文」。

它能抓到纯 Python 测不到的问题——比如"后端数据没问题，但卡片没渲染出来"。

## 怎么跑

1. 先启动服务（另开一个窗口）：`run.bat`

2. 装测试依赖（只需一次，约 40MB，走国内镜像）：

```bat
cd _domtest
"C:\Users\amxl\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\node\bin\node.exe" ^
  "C:\Users\amxl\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\pnpm\bin\pnpm.mjs" ^
  add jsdom --registry=https://registry.npmmirror.com --config.node-linker=hoisted
cd ..
```

> `--config.node-linker=hoisted` 是必须的：pnpm 默认的严格依赖隔离会让 jsdom
> 找不到自己的传递依赖（报 `Cannot find module 'tough-cookie'`）。

3. 跑测试：

```bat
"C:\Users\amxl\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\node\bin\node.exe" _domtest\render_test2.js
```

## 两个脚本的区别

| 脚本 | 说明 |
|---|---|
| `render_test2.js` | **推荐**。捕获应用自己的轮询函数手动驱动到运行结束，检查轮次卡片数、每个方向的原文与译文、最终中文卡片；这是验证渲染的可靠方式 |
| `render_test.js` | 让应用自己按 1 秒间隔轮询。在 jsdom 里定时器只触发一次（环境限制），所以只能看到第一次轮询的内容，仅作排查用 |

## 已知环境限制

- **真浏览器（Edge/Chrome）在本沙箱下跑不起来**：Chromium 的多进程架构需要命名管道，
  沙箱禁止。实测报 `FATAL: mojo platform_channel.cc Check failed: 拒绝访问`。
  所以这里用 jsdom 代替，没法测真实视觉样式和点击手感，那部分需要人工看。
