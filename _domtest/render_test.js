// 真实 DOM 渲染测试：加载 index.html + app.js，连真实服务，检查页面显示了什么。
const fs = require('fs');
const path = require('path');
const { JSDOM, VirtualConsole } = require('jsdom');

const WS = path.resolve(__dirname, '..');
const BASE = 'http://127.0.0.1:8000';

const virtualConsole = new VirtualConsole();
const consoleErrors = [];
virtualConsole.on('jsdomError', (e) => consoleErrors.push('jsdomError: ' + (e.stack || e.message)));
virtualConsole.on('error', (...args) => consoleErrors.push('console.error: ' + args.join(' ')));
virtualConsole.on('log', (...args) => console.log('[page]', ...args));

async function main() {
  const html = fs.readFileSync(path.join(WS, 'web', 'index.html'), 'utf8');

  const dom = new JSDOM(html, {
    url: BASE + '/',
    runScripts: 'outside-only',
    pretendToBeVisual: true,
    virtualConsole,
  });
  const { window } = dom;

  // jsdom 没有 fetch，用 node 的 fetch 并记录所有请求
  const requests = [];
  window.fetch = async (url, opts) => {
    const full = String(url).startsWith('http') ? String(url) : BASE + String(url);
    requests.push((opts && opts.method ? opts.method + ' ' : 'GET ') + full);
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 15000);
    try {
      return await fetch(full, { ...(opts || {}), signal: controller.signal });
    } finally {
      clearTimeout(timer);
    }
  };
  window.navigator.clipboard = { writeText: async () => {} };

  // 执行 app.js
  const appJs = fs.readFileSync(path.join(WS, 'web', 'app.js'), 'utf8');

  // 记录定时器调用，看清轮询是否还在排下一次
  const timerLog = [];
  const realSetInterval = window.setInterval.bind(window);
  const realClearInterval = window.clearInterval.bind(window);
  window.setInterval = (fn, ms, ...rest) => {
    timerLog.push('setInterval(' + ms + 'ms)');
    if (ms === 1000) {
      let n = 0;
      const wrapped = () => {
        n += 1;
        timerLog.push('tick#' + n);
        try {
          return fn();
        } catch (e) {
          consoleErrors.push('tick 抛错: ' + (e.stack || e));
          throw e;
        }
      };
      return realSetInterval(wrapped, ms, ...rest);
    }
    return realSetInterval(fn, ms, ...rest);
  };
  window.clearInterval = (id) => {
    timerLog.push('clearInterval');
    return realClearInterval(id);
  };
  window.addEventListener('error', (e) => consoleErrors.push('window.onerror: ' + (e.error && e.error.stack || e.message)));
  window.addEventListener('unhandledrejection', (e) => consoleErrors.push('unhandledrejection: ' + (e.reason && e.reason.stack || e.reason)));

  // 插桩：记录 setAttribute / appendChild，找出为什么 #rounds 一直为空
  const nodeLog = [];
  const originalAppend = window.Node.prototype.appendChild;
  window.Node.prototype.appendChild = function (child) {
    const cls = child && child.className ? String(child.className) : '';
    const parentId = this && this.id ? '#' + this.id : (this && this.tagName ? this.tagName.toLowerCase() : '?');
    nodeLog.push('appendChild <' + (child.tagName || '?').toLowerCase() + '> class="' + cls + '" into ' + parentId);
    return originalAppend.call(this, child);
  };

  // 记录每次轮询拿到的数据
  const fetchLog = [];
  const originalFetch2 = window.fetch;
  window.fetch = async (url, opts) => {
    const res = await originalFetch2(url, opts);
    const urlStr = String(url);
    if (/\/api\/runs\/[a-f0-9]+$/.test(urlStr)) {
      try {
        const data = await res.clone().json();
        fetchLog.push(`轮询: status=${data.status} steps=${data.steps ? data.steps.length : 'null'} total=${data.progress ? data.progress.total_steps : '?'}`);
      } catch (e) {
        fetchLog.push('轮询: 解析失败 ' + e.message);
      }
    }
    return res;
  };

  try {
    window.eval(appJs);
  } catch (e) {
    consoleErrors.push('eval 失败: ' + e.stack);
  }

  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const $ = (sel) => window.document.querySelector(sel);
  const $$ = (sel) => Array.from(window.document.querySelectorAll(sel));

  await wait(1200); // 等第一次轮询 /api/status 和 /api/runs

  // 点「开始翻译」，跑 2 轮
  $('#input').value = '今天的天气很好，适合出去散步。';
  $('#rounds').value = '2';
  $('#start').dispatchEvent(new window.Event('click'));

  // 等完成（最多 60 秒）
  for (let i = 0; i < 60; i++) {
    await wait(1000);
    const progress = $('#progressText').textContent || '';
    if (progress.includes('已完成') || progress.includes('已停止') || progress.includes('出错')) break;
  }

  const rounds = $$('.round');
  console.log('=== 页面渲染结果 ===');
  console.log('轮次卡片数:', rounds.length);
  console.log('每个卡片里的方向块数:', rounds.map((r) => r.querySelectorAll('.dir').length).join(', '));
  console.log('页面上「原文」标签数:', $$('.side-value .k').length);
  console.log('最终中文卡片可见:', !$('#finalPanel').hidden);
  console.log('最终中文:', $('#finalText').textContent);
  console.log();
  console.log('=== 逐条内容 ===');
  for (const card of rounds) {
    console.log('[' + card.querySelector('.round-head strong').textContent + ']',
      card.querySelector('.round-head span').textContent);
    for (const dir of card.querySelectorAll('.dir')) {
      const sides = dir.querySelectorAll('.side-value');
      const keys = Array.from(dir.querySelectorAll('.k')).map((k) =>
        k.textContent.replace('复制', '').trim());
      const vals = Array.from(dir.querySelectorAll('.v')).map((v) => v.textContent);
      console.log('   ' + keys[0] + ': ' + vals[0]);
      console.log('   ' + keys[1] + ': ' + vals[1]);
    }
  }
  console.log();
  console.log('=== 请求记录 ===');
  console.log(requests.join('\n'));
  console.log();
  console.log('=== 定时器调用 ===');
  console.log(timerLog.join('\n') || '（无）');
  console.log();
  console.log('=== 轮询拿到的数据 ===');
  console.log(fetchLog.join('\n') || '（一次都没拿到）');
  console.log();
  console.log('=== appendChild 调用（前 25 条）===');
  console.log(nodeLog.length ? nodeLog.slice(0, 25).join('\n') : '（一次 appendChild 都没有）');
  console.log();
  console.log('=== 页面上的提示条 ===');
  console.log(alertBox.hidden ? '（无提示）' : alertBox.textContent);
  console.log();
  console.log('=== 进度文字 ===');
  console.log(JSON.stringify($('#progressText').textContent));
  console.log();
  console.log('=== 页面报错 ===');
  console.log(consoleErrors.length ? consoleErrors.join('\n') : '（无）');

  dom.window.close();
  process.exit(0);
}

main().catch((e) => {
  console.error('测试脚本本身出错:', e);
  process.exit(1);
});
setTimeout(() => {
  console.error('整体超时，强制结束');
  process.exit(2);
}, 150000);
