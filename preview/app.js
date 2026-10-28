(() => {
  'use strict';
  const motions = [
    ['idle', '待机', [280,110,110,140,140,320]],
    ['running-right', '向右移动', [120,120,120,120,120,120,120,220]],
    ['running-left', '向左移动', [120,120,120,120,120,120,120,220]],
    ['waving', '挥手', [140,140,140,280]],
    ['jumping', '跳跃', [140,140,140,140,280]],
    ['failed', '失败反应', [140,140,140,140,140,140,140,240]],
    ['waiting', '等待', [150,150,150,150,150,260]],
    ['running', '任务处理', [120,120,120,120,120,220]],
    ['review', '审阅', [150,150,150,150,150,280]],
  ];
  const labels = ['Blue Whale Maid · 蓝鲸女仆', 'Orange Scholar · 橙花书灵', 'Silver Dragon · 银白龙姬'];
  const $ = id => document.getElementById(id);
  const canvas = $('canvas'), ctx = canvas.getContext('2d'), pet = $('pet');
  const menu = $('action-menu'), usage = $('usage-card');
  const configured = document.getElementById('initial-pets');
  let initial = [];
  if (configured) {
    try { initial = JSON.parse(configured.textContent); } catch (_) { initial = []; }
  }
  const pets = labels.map((label, i) => ({label, image: null, url: null, initial: initial[i] || null}));
  let selected = 0, state = 0, frame = 0, playing = !matchMedia('(prefers-reduced-motion: reduce)').matches;
  let timer = null, began = 0, remaining = motions[0][2][0], menuTrigger = pet;
  let snapshot = null;

  function updateTabs() {
    $('pet-tabs').querySelectorAll('button').forEach((button, i) => {
      button.classList.toggle('active', i === selected);
      button.setAttribute('aria-pressed', String(i === selected));
      button.querySelector('small').textContent = pets[i].image ? '已载入' : '未载入';
    });
    $('missing').hidden = !!pets[selected].image;
    pet.dataset.pet = String(selected);
  }
  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (pets[selected].image) ctx.drawImage(pets[selected].image, frame * 192, state * 208, 192, 208, 0, 0, 192, 208);
    pet.dataset.state = motions[state][0];
    pet.dataset.frame = String(frame);
    $('current-action').textContent = motions[state][1];
    $('play-toggle').textContent = playing ? '暂停' : '继续';
    menu.querySelectorAll('button').forEach((button, i) => button.setAttribute('aria-checked', String(i === state)));
  }
  function clearTimer() { if (timer !== null) clearTimeout(timer); timer = null; }
  function schedule() {
    clearTimer();
    if (!playing) return;
    began = performance.now();
    timer = setTimeout(() => {
      timer = null;
      if (frame + 1 >= motions[state][2].length) {
        if (!$('loop').checked) { playing = false; draw(); return; }
        frame = 0;
      } else frame++;
      remaining = motions[state][2][frame];
      draw(); schedule();
    }, remaining);
  }
  function selectMotion(index) {
    state = index; frame = 0; remaining = motions[state][2][0];
    playing = true;
    draw(); schedule();
  }
  function loadImage(index, src) {
    const img = new Image();
    img.onload = () => {
      if (img.naturalWidth !== 1536 || img.naturalHeight !== 1872) {
        pets[index].image = null; updateTabs(); draw();
        $('missing').textContent = '图集尺寸须为 1536 × 1872';
        return;
      }
      pets[index].image = img; $('missing').textContent = '请先为角色选择图集';
      updateTabs(); draw();
    };
    img.onerror = () => { pets[index].image = null; updateTabs(); draw(); $('missing').textContent = '图集读取失败，请重新选择'; };
    img.src = src;
  }
  labels.forEach((label, index) => {
    const button = document.createElement('button'); button.type = 'button';
    const title = document.createElement('span'); title.textContent = label;
    const status = document.createElement('small');
    button.append(title, status);
    button.addEventListener('click', () => { selected = index; updateTabs(); selectMotion(0); closeMenu(); });
    $('pet-tabs').append(button);
    const wrapper = document.createElement('label'); wrapper.textContent = `选择 ${label} 图集`;
    const input = document.createElement('input'); input.type = 'file'; input.accept = 'image/webp,image/png';
    input.addEventListener('change', () => {
      if (!input.files[0]) return;
      if (pets[index].url) URL.revokeObjectURL(pets[index].url);
      pets[index].url = URL.createObjectURL(input.files[0]); loadImage(index, pets[index].url);
    });
    wrapper.append(input); $('pet-inputs').append(wrapper);
    if (pets[index].initial && typeof pets[index].initial.src === 'string') loadImage(index, pets[index].initial.src);
  });
  motions.forEach((motion, index) => {
    const button = document.createElement('button'); button.type = 'button'; button.role = 'menuitemradio';
    button.textContent = motion[1]; button.addEventListener('click', () => { selectMotion(index); closeMenu(); pet.focus(); });
    menu.append(button);
  });
  function openMenu(x, y, trigger) {
    menuTrigger = trigger; menu.hidden = false;
    const rect = menu.getBoundingClientRect();
    menu.style.left = `${Math.max(8, Math.min(x, innerWidth - rect.width - 8))}px`;
    menu.style.top = `${Math.max(8, Math.min(y, innerHeight - rect.height - 8))}px`;
    menu.querySelectorAll('button')[state].focus();
  }
  function closeMenu(restore = false) { if (!menu.hidden) { menu.hidden = true; if (restore) menuTrigger.focus(); } }
  pet.addEventListener('contextmenu', event => { event.preventDefault(); openMenu(event.clientX, event.clientY, pet); });
  pet.addEventListener('keydown', event => {
    if (event.key === 'ContextMenu' || (event.shiftKey && event.key === 'F10')) {
      event.preventDefault(); const rect = pet.getBoundingClientRect(); openMenu(rect.left, rect.bottom, pet);
    }
  });
  $('menu-open').addEventListener('click', event => { const rect = event.currentTarget.getBoundingClientRect(); openMenu(rect.left, rect.bottom, event.currentTarget); });
  menu.addEventListener('keydown', event => {
    const buttons = [...menu.querySelectorAll('button')], current = buttons.indexOf(document.activeElement);
    let next = null;
    if (event.key === 'ArrowDown') next = (current + 1) % buttons.length;
    if (event.key === 'ArrowUp') next = (current - 1 + buttons.length) % buttons.length;
    if (event.key === 'Home') next = 0;
    if (event.key === 'End') next = buttons.length - 1;
    if (next !== null) { event.preventDefault(); buttons[next].focus(); }
  });
  document.addEventListener('pointerdown', event => { if (!menu.hidden && !menu.contains(event.target) && event.target !== $('menu-open')) closeMenu(); });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      if (!menu.hidden) closeMenu(true);
      else if (!usage.hidden) { usage.hidden = true; $('usage-open').focus(); }
    }
  });
  $('play-toggle').addEventListener('click', () => {
    if (playing) { remaining = Math.max(0, remaining - (performance.now() - began)); playing = false; clearTimer(); }
    else { playing = true; schedule(); }
    draw();
  });
  $('replay').addEventListener('click', () => selectMotion(state));
  $('idle').addEventListener('click', () => selectMotion(0));
  $('scale').addEventListener('input', event => pet.style.setProperty('--pet-scale', event.target.value / 100));
  pet.style.setProperty('--pet-scale', '1.2');
  document.querySelectorAll('.bg-button').forEach(button => button.addEventListener('click', () => {
    $('stage').dataset.background = button.dataset.bg;
    document.querySelectorAll('.bg-button').forEach(item => { const active = item === button; item.classList.toggle('active', active); item.setAttribute('aria-pressed', String(active)); });
  }));

  const text = (tag, value, className) => { const el = document.createElement(tag); if (className) el.className = className; el.textContent = value; return el; };
  const dateText = value => {
    const date = new Date(value);
    return Number.isFinite(date.getTime()) ? date.toLocaleString(undefined, {dateStyle:'medium', timeStyle:'long'}) : '未提供';
  };
  const durationText = value => {
    if (!Number.isFinite(value) || value <= 0) return '窗口时长未提供';
    if (value === 10080) return '每周';
    if (value % 1440 === 0) return `${value / 1440} 天`;
    if (value % 60 === 0) return `${value / 60} 小时`;
    return `${value} 分钟`;
  };
  function renderUsage() {
    const content = $('usage-content'); content.replaceChildren();
    if (!snapshot) { content.append(text('p', '尚未读取额度。请先在终端生成快照，再选择文件。', 'empty')); return; }
    if (snapshot.status !== 'ok') {
      content.append(text('p', snapshot.message || '未获取额度，请检查 CLI 登录状态。', 'empty'));
      content.append(text('p', `尝试时间：${dateText(snapshot.fetchedAt)}\n来源：Codex App Server account/rateLimits/read`, 'usage-meta'));
      return;
    }
    const fetched = Date.parse(snapshot.fetchedAt);
    const stale = !Number.isFinite(fetched) || Date.now() - fetched > 3600000 || fetched > Date.now() + 300000;
    content.append(text('p', stale ? '快照已过期，请重新生成并选择。' : '本地快照', 'usage-extra'));
    for (const bucket of snapshot.buckets) {
      content.append(text('p', bucket.name || bucket.id || '额度桶', 'usage-bucket'));
      for (const window of bucket.windows) {
        const item = document.createElement('div'); item.className = 'usage-window';
        const line = document.createElement('div'); line.className = 'line';
        const used = window.usedPercent;
        const valid = typeof used === 'number' && Number.isFinite(used) && used >= 0;
        const remaining = valid ? Math.max(0, Math.min(100, 100 - used)) : null;
        line.append(text('span', durationText(window.durationMins)), text('strong', remaining === null ? '未提供' : `剩余 ${Number(remaining.toFixed(1))}%`));
        item.append(line);
        if (remaining !== null) { const bar = document.createElement('div'); bar.className = 'progress'; bar.setAttribute('role','progressbar'); bar.setAttribute('aria-label','剩余额度'); bar.setAttribute('aria-valuemin','0'); bar.setAttribute('aria-valuemax','100'); bar.setAttribute('aria-valuenow',String(remaining)); const fill = document.createElement('i'); fill.style.width = `${remaining}%`; bar.append(fill); item.append(bar); }
        const reset = typeof window.resetsAt === 'number' && Number.isFinite(window.resetsAt) && window.resetsAt >= 0 ? dateText(window.resetsAt * 1000) : '未提供';
        item.append(text('small', `已用 ${valid ? `${Number(used.toFixed(1))}%` : '未提供'} · 重置 ${reset}`));
        if (typeof window.resetsAt === 'number' && window.resetsAt * 1000 < Date.now()) item.append(text('small', '该窗口的重置时间已过，请刷新。'));
        content.append(item);
      }
      if (bucket.credits) {
        const credit = bucket.credits;
        const parts = [];
        if (credit.balance !== undefined) parts.push(`余额 ${credit.balance}`);
        if (credit.hasCredits !== undefined) parts.push(`有积分：${credit.hasCredits ? '是' : '否'}`);
        if (credit.unlimited !== undefined) parts.push(`无限：${credit.unlimited ? '是' : '否'}`);
        if (parts.length) content.append(text('p', `额外积分：${parts.join(' · ')}`, 'usage-extra'));
      }
    }
    if (snapshot.resetCreditsAvailable !== null && snapshot.resetCreditsAvailable !== undefined) content.append(text('p', `可用额度重置次数：${snapshot.resetCreditsAvailable}`, 'usage-extra'));
    content.append(text('p', `更新时间：${dateText(snapshot.fetchedAt)}\n来源：Codex App Server account/rateLimits/read`, 'usage-meta'));
  }
  function openUsage() { closeMenu(); renderUsage(); usage.hidden = false; usage.focus(); }
  pet.addEventListener('dblclick', openUsage);
  $('usage-open').addEventListener('click', openUsage);
  $('usage-close').addEventListener('click', () => { usage.hidden = true; $('usage-open').focus(); });
  $('usage-import').addEventListener('click', () => $('usage-file').click());
  $('usage-file').addEventListener('change', async event => {
    const file = event.target.files[0]; if (!file) return;
    try {
      if (file.size > 1048576) throw new Error();
      const value = JSON.parse(await file.text());
      if (!value || value.source !== 'Codex App Server account/rateLimits/read' || !Array.isArray(value.buckets) || !value.buckets.every(b => b && Array.isArray(b.windows))) throw new Error();
      snapshot = value; renderUsage();
    } catch (_) { snapshot = null; $('usage-content').replaceChildren(text('p', '快照格式无效，请重新生成并选择。', 'empty')); }
    event.target.value = '';
  });
  updateTabs(); draw(); schedule();
})();
