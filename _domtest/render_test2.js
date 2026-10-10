// 用真实 app.js 的渲染代码验证：捕获应用自己的轮询函数，手动驱动到运行结束，
// 检查 DOM 里是否出现每一轮的原文与译文。
const fs = require('fs');
const path = require('path');
const { JSDOM, VirtualConsole } = require('jsdom');

const WS = path.resolve(__dirname, '..');
const BASE = 'http://127.0.0.1:8000';

const virtualConsole = new VirtualConsole();
const pageErrors = [];
virtualConsole.on('jsdomError', (e) => pageErrors.push('jsdomError: ' + (e.stack || e.message)));

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function main() {
  const html = fs.readFileSync(path.join(WS, 'web', 'index.html'), 'utf8');
  const dom = new JSDOM(html, {
    url: BASE + '/',
    runScripts: 'outside-only',
    pretendToBeVisual: true,
    virtualConsole,
  });
  const { window } = dom;
  const document = window.document;
  const $ = (s) => document.querySelector(s);
  const $$ = (s) => Array.from(document.querySelectorAll(s));

  const requests = [];
  window.fetch = async (url, opts) => {
    const full = String(url).startsWith('http') ? String(url) : BASE + String(url);
    requests.push((opts && opts.method ? opts.method + ' ' : 'GET ') + full.replace(BASE, ''));
    return fetch(full, opts);
  };
  window.navigator.clipboard = { writeText: async () => {} };
  window.addEventListener('error', (e) => pageErrors.push('onerror: ' + (e.error?.stack || e.message)));
  window.addEventListener('unhandledrejection', (e) => pageErrors.push('unhandledrejection: ' + (e.reason?.stack || e.reason)));

  // 捕获应用自己的轮询函数（app.js 里 setInterval(tick, 1000)）
  let appTick = null;
  const realSetInterval = window.setInterval.bind(window);
  window.setInterval = (fn, ms, ...rest) => {
    if (ms === 1000 && !appTick) appTick = fn;
    return realSetInterval(fn, 0x7fffffff); // 不让它自己跑，改由我们手动驱动
  };

  window.eval(fs.readFileSync(path.join(WS, 'web', 'app.js'), 'utf8'));
  await sleep(1500); // 等首次 /api/status 和 /api/runs

  console.log('捕获到应用的轮询函数:', typeof appTick === 'function' ? '是' : '否');

  // 触发一次运行
  $('#input').value = '今天的天气很好，适合出去散步。';
  $('#rounds').value = '3';
  $('#start').dispatchEvent(new window.Event('click'));
  await sleep(600);

  // 手动驱动轮询直到跑完（等价于浏览器里每秒轮询）
  let ticks = 0;
  for (let i = 0; i < 40; i++) {
    if (appTick) await appTick();
    ticks += 1;
    await sleep(400);
    const t = $('#progressText').textContent;
    if (/已完成|已停止|出错/.test(t)) break;
  }

  console.log('手动驱动的轮询次数:', ticks);
  console.log();
  console.log('=== 渲染结果 ===');
  const rounds = $$('.round');
  console.log('轮次卡片数:', rounds.length);
  console.log('方向块（原文+译文）数:', $$('.dir').length);
  console.log('最终中文卡片可见:', !$('#finalPanel').hidden);
  console.log('最终中文:', $('#finalText').textContent);
  console.log('进度文字:', $('#progressText').textContent);
  console.log('提示条:', $('#alert').hidden ? '（无）' : $('#alert').textContent);
  console.log();
  for (const card of rounds) {
    console.log('[' + card.querySelector('.round-head strong').textContent + '] ' +
      card.querySelector('.round-head span').textContent);
    for (const dir of card.querySelectorAll('.dir')) {
      const keys = Array.from(dir.querySelectorAll('.k')).map((k) => k.textContent.replace('复制', '').trim());
      const vals = Array.from(dir.querySelectorAll('.v')).map((v) => v.textContent);
      console.log('   ' + keys[0] + ': ' + vals[0]);
      console.log('   ' + keys[1] + ': ' + vals[1]);
    }
  }
  console.log();
  console.log('=== 页面报错 ===');
  console.log(pageErrors.length ? pageErrors.join('\n') : '（无）');
  console.log('=== 请求 ===');
  console.log(requests.join('\n'));

  dom.window.close();
  process.exit(0);
}

main().catch((e) => {
  console.error('测试脚本出错:', e);
  process.exit(1);
});
