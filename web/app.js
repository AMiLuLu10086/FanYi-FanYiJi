/* app.js — 页面逻辑：发起任务、每秒轮询进度、渲染每轮结果
 *
 * 只做展示：把服务端给的原样显示出来，不算相似度、不判断收敛。
 */
(() => {
  const $ = (id) => document.getElementById(id);

  const el = {
    input: $('input'),
    rounds: $('rounds'),
    start: $('start'),
    stop: $('stop'),
    engine: $('engine'),
    alert: $('alert'),
    progressPanel: $('progressPanel'),
    progressText: $('progressText'),
    progressTime: $('progressTime'),
    bar: $('bar'),
    finalPanel: $('finalPanel'),
    finalText: $('finalText'),
    copyFinal: $('copyFinal'),
    startPanel: $('startPanel'),
    startText: $('startText'),
    copyStart: $('copyStart'),
    roundsHead: $('roundsHead'),
    copyAll: $('copyAll'),
    roundsBox: $('rounds'),
    history: $('history'),
    loadHistory: $('loadHistory'),
    exportMd: $('exportMd'),
  };

  let currentRunId = null;
  let timer = null;
  let startedAt = 0;
  let currentData = null;            // 最近一次拿到的运行数据（复制全部过程要用）
  const renderedSteps = new Set();   // 已经画到页面上的步骤，避免重复渲染
  const roundEls = new Map();        // round number -> section

  // ─────────── 通用小工具 ───────────

  function showAlert(message, kind = 'error') {
    el.alert.textContent = message;
    el.alert.hidden = false;
    el.alert.classList.toggle('info', kind === 'info');
  }

  function clearAlert() {
    el.alert.hidden = true;
    el.alert.textContent = '';
  }

  async function copyText(text, button) {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const ta = document.createElement('textarea');
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      ta.remove();
    }
    const old = button.textContent;
    button.textContent = '它已经被复制了';
    setTimeout(() => { button.textContent = old; }, 1200);
  }

  // ─────────── 渲染 ───────────

  function resetResults() {
    el.roundsBox.innerHTML = '';
    roundEls.clear();
    renderedSteps.clear();
    el.finalPanel.hidden = true;
    el.finalText.textContent = '';
    el.startPanel.hidden = true;
    el.startText.textContent = '';
    el.roundsHead.hidden = true;
    currentData = null;
  }

  // 把整轮过程拼成一段纯文本（用于「复制全部过程」）
  function buildPlainText(data) {
    const lines = [];
    lines.push(`作为输入的中文：${data.input}`);
    lines.push(`进行翻译的次数：${data.rounds} 轮（共 ${data.rounds * 2} 次翻译）`);
    if (data.final_zh) lines.push(`最终的中文结果：${data.final_zh}`);
    lines.push('');
    for (const step of data.steps || []) {
      lines.push(`【第 ${step.round} 轮的翻译 · ${step.direction_label}】`);
      lines.push(`在其中，原文：${step.src}`);
      lines.push(`而译文：${step.out}`);
      lines.push('');
    }
    return lines.join('\n').trimEnd();
  }

  function makeSide(key, value, sourceText, extraTag) {
    const wrap = document.createElement('div');
    wrap.className = 'side-value';

    const k = document.createElement('div');
    k.className = 'k';
    k.textContent = key;
    if (extraTag) {
      const tag = document.createElement('span');
      tag.className = 'tag';
      tag.textContent = extraTag;
      k.appendChild(tag);
    }
    const btn = document.createElement('button');
    btn.className = 'copy';
    btn.textContent = '复制';
    btn.addEventListener('click', () => copyText(value, btn));
    k.appendChild(btn);

    const v = document.createElement('div');
    v.className = 'v';
    v.textContent = value;

    wrap.appendChild(k);
    wrap.appendChild(v);
    return wrap;
  }

  // 轮次的"情绪状态"：前两轮还在挣扎，中间开始走样，最后两轮已经躺平
  function roundMood(roundNo, rounds) {
    if (rounds >= 4) {
      if (roundNo <= 2) return '尚在挣扎之中';
      if (roundNo >= rounds - 1) return '已经放弃抵抗';
      return '开始发生走样';
    }
    if (roundNo <= 1) return '尚在挣扎之中';
    return '已经开始发生走样';
  }

  function ensureRound(roundNo, rounds) {
    if (roundEls.has(roundNo)) return roundEls.get(roundNo);

    const section = document.createElement('article');
    section.className = 'round';

    const head = document.createElement('div');
    head.className = 'round-head';
    const strong = document.createElement('strong');
    strong.textContent = `第 ${roundNo} 轮（${roundMood(roundNo, rounds)}）`;
    const meta = document.createElement('span');
    meta.className = 'muted';
    meta.dataset.role = 'meta';
    meta.textContent = `共 ${rounds} 轮`;
    head.appendChild(strong);
    head.appendChild(meta);

    const body = document.createElement('div');
    body.dataset.role = 'body';

    section.appendChild(head);
    section.appendChild(body);
    el.roundsBox.appendChild(section);

    const entry = { section, body, meta };
    roundEls.set(roundNo, entry);
    return entry;
  }

  function renderStep(step, rounds) {
    const entry = ensureRound(step.round, rounds);

    const dir = document.createElement('div');
    dir.className = 'dir';
    dir.dataset.stepKey = `${step.round}-${step.direction}`;

    const leftKey = step.direction === 'zh2en' ? '原文（中文）' : '原文（英文）';
    const rightKey = step.direction === 'zh2en' ? '译文（英文）' : '译文（中文）';
    dir.appendChild(makeSide(leftKey, step.src));
    dir.appendChild(makeSide(rightKey, step.out, step.src,
      step.degenerate ? '疑似发生了整段的重复' : null));

    entry.body.appendChild(dir);

    // 更新这一轮的小结信息（两个半轮的耗时合计）
    const times = entry.times || (entry.times = []);
    times.push(step.ms);
    entry.meta.textContent =
      `共 ${rounds} 轮 · 其中 ${times.reduce((a, b) => a + b, 0)} ms 被消耗`;
  }

  function updateProgress(data) {
    const total = data.progress.total_steps || 1;
    const done = data.progress.done_steps || 0;
    el.bar.style.width = `${Math.min(100, (done / total) * 100)}%`;

    if (data.status === 'running') {
      // 半轮（中→英）时 done 是奇数，正在进行的轮次要用向上取整
      const currentRound = Math.min(data.rounds, Math.floor(done / 2) + 1);
      el.progressText.textContent =
        `第 ${currentRound} 轮的翻译正在被进行，其中 ${done}/${total} 次已经被完成`;
    } else if (data.status === 'done') {
      el.progressText.textContent = `${data.rounds} 轮已经被完成（总共 ${total} 次的翻译）`;
    } else if (data.status === 'stopped') {
      el.progressText.textContent = `它已经被停止：在其中，${done}/${total} 次翻译被完成`;
    } else if (data.status === 'error') {
      el.progressText.textContent = '一个错误已经发生了';
    }

    if (startedAt) {
      const sec = ((Date.now() - startedAt) / 1000).toFixed(0);
      el.progressTime.textContent = `已经被消耗的时间：${sec} 秒`;
    }
  }

  function renderRun(data, { fresh }) {
    currentData = data;
    el.roundsBox.classList.add('rounds');

    // 起始中文
    if (data.input) {
      el.startText.textContent = data.input;
      el.startPanel.hidden = false;
    }

    for (const step of data.steps) {
      const key = `${step.round}-${step.direction}`;
      if (renderedSteps.has(key)) continue;
      renderedSteps.add(key);
      renderStep(step, data.rounds);
    }
    el.roundsHead.hidden = renderedSteps.size === 0;

    if (data.final_zh) {
      el.finalText.textContent = data.final_zh;
      el.finalPanel.hidden = false;
    }

    updateProgress(data);
    el.exportMd.disabled = !currentRunId;

    if (data.status === 'done' || data.status === 'stopped') {
      stopPolling();
      el.start.disabled = false;
      el.stop.disabled = true;
      if (fresh) loadHistory();
    }
    if (data.status === 'error') {
      stopPolling();
      el.start.disabled = false;
      el.stop.disabled = true;
      showAlert(data.error || '运行出错');
      if (fresh) loadHistory();
    }
  }

  // ─────────── 轮询 ───────────

  function startPolling(runId, fresh) {
    currentRunId = runId;
    startedAt = Date.now();
    el.progressPanel.hidden = false;
    el.bar.style.width = '0%';

    const tick = async () => {
      try {
        const res = await fetch(`/api/runs/${runId}`, { cache: 'no-store' });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        renderRun(data, { fresh });
      } catch (err) {
        stopPolling();
        showAlert(`读取进度失败：${err.message}`);
        el.start.disabled = false;
        el.stop.disabled = true;
      }
    };

    clearInterval(timer);
    timer = setInterval(tick, 1000);
    tick();
  }

  function stopPolling() {
    if (timer) clearInterval(timer);
    timer = null;
  }

  // ─────────── 操作 ───────────

  async function startRun() {
    clearAlert();
    const text = el.input.value.trim();
    if (!text) {
      showAlert('请先输入要翻译的中文');
      el.input.focus();
      return;
    }

    const rounds = parseInt(el.rounds.value, 10) || 10;

    el.start.disabled = true;
    resetResults();

    try {
      const res = await fetch('/api/runs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, rounds }),
      });
      const data = await res.json();
      if (!res.ok) {
        showAlert(data.error || `请求失败（HTTP ${res.status}）`);
        el.start.disabled = false;
        return;
      }
      el.stop.disabled = false;
      if (data.id) startPolling(data.id, true);
    } catch (err) {
      showAlert(`连接不上服务：${err.message}`);
      el.start.disabled = false;
    }
  }

  async function stopRun() {
    if (!currentRunId) return;
    el.stop.disabled = true;
    try {
      await fetch(`/api/runs/${currentRunId}/stop`, { method: 'POST' });
    } catch (err) {
      showAlert(`停止请求失败：${err.message}`);
    }
  }

  async function refreshEngineStatus() {
    try {
      const res = await fetch('/api/status', { cache: 'no-store' });
      const data = await res.json();
      const st = data.engine || {};
      el.engine.className = `engine ${st.status || ''}`;
      const map = {
        idle: '模型状态：它还没有被启动',
        loading: '模型状态：一个大约 624MB 的下载正在被进行',
        ready: '模型状态：它已经被准备好了',
        error: '模型状态：它罢工了',
      };
      let text = map[st.status] || `模型状态：${st.status}`;
      if (st.status === 'error' && st.detail) text += '（点「开始翻译」会重试）';
      el.engine.textContent = text;

      if (!el.rounds.dataset.initialized) {
        el.rounds.value = data.default_rounds;
        el.rounds.max = data.max_rounds;
        el.rounds.dataset.initialized = '1';
      }
    } catch {
      el.engine.className = 'engine error';
      el.engine.textContent = '模型状态：连本地服务都找不到';
    }
  }

  async function loadHistory() {
    try {
      const res = await fetch('/api/runs', { cache: 'no-store' });
      const data = await res.json();
      const runs = data.runs || [];
      el.history.innerHTML = '';
      if (!runs.length) {
        const opt = document.createElement('option');
        opt.value = '';
        opt.textContent = '（还没有任何记录被找到）';
        el.history.appendChild(opt);
        return;
      }
      for (const run of runs) {
        const opt = document.createElement('option');
        opt.value = run.id;
        const when = run.created_at
          ? new Date(run.created_at * 1000).toLocaleString('zh-CN')
          : '';
        const preview = (run.input || '').slice(0, 18);
        opt.textContent = `${when} · ${run.rounds} 轮 · ${preview}`;
        el.history.appendChild(opt);
      }
    } catch {
      /* 历史读不到不影响主功能 */
    }
  }

  async function viewHistory() {
    const id = el.history.value;
    if (!id) return;
    clearAlert();
    resetResults();
    currentRunId = id;
    el.progressPanel.hidden = false;
    try {
      const res = await fetch(`/api/runs/${id}`, { cache: 'no-store' });
      const data = await res.json();
      if (!res.ok) {
        showAlert(data.error || '读取失败');
        return;
      }
      el.input.value = data.input || '';
      el.rounds.value = data.rounds || '';
      renderRun(data, { fresh: false });
      el.exportMd.disabled = false;
    } catch (err) {
      showAlert(`读取失败：${err.message}`);
    }
  }

  function exportMarkdown() {
    if (!currentRunId) return;
    window.location.href = `/api/runs/${currentRunId}?fmt=md`;
  }

  // ─────────── 绑定 ───────────

  el.start.addEventListener('click', startRun);
  el.stop.addEventListener('click', stopRun);
  el.loadHistory.addEventListener('click', viewHistory);
  el.exportMd.addEventListener('click', exportMarkdown);
  el.copyFinal.addEventListener('click', () => copyText(el.finalText.textContent, el.copyFinal));
  el.copyStart.addEventListener('click', () => copyText(el.startText.textContent, el.copyStart));
  el.copyAll.addEventListener('click', () => {
    if (!currentData) return;
    copyText(buildPlainText(currentData), el.copyAll);
  });
  el.input.addEventListener('keydown', (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') startRun();
  });

  refreshEngineStatus();
  loadHistory();
  setInterval(refreshEngineStatus, 3000);
})();
