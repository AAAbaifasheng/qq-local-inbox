// ==UserScript==
// @name         QQ Local Inbox · 学习通作业只读同步
// @namespace    qqli.local.chaoxing
// @version      1.0.0
// @description  从学习通网页读取作业标题、课程、截止时间与状态，发送到本机 QQ Local Inbox。不读取账号密码，不自动提交。
// @match        *://*.chaoxing.com/*
// @grant        GM_xmlhttpRequest
// @connect      127.0.0.1
// @connect      chaoxing.com
// @connect      *.chaoxing.com
// @run-at       document-idle
// @noframes
// ==/UserScript==

(function () {
  'use strict';

  const BRIDGE_URL = 'http://127.0.0.1:__PORT__/api/chaoxing/assignments';
  const TOKEN = '__TOKEN__';
  const AUTO_KEY = 'qqli_chaoxing_auto_sync';
  const STATUS_WORDS = [
    '已批阅', '待批阅', '已提交', '已交', '未提交', '未交', '待完成', '已完成',
    '未开始', '进行中', '已截止', '已过期', '已结束'
  ];
  const GENERIC_TITLES = new Set([
    '查看', '查看详情', '详情', '进入作业', '作业详情', '去完成', '开始答题',
    '未开始', '进行中', '已结束', '作业', '考试', '进入课程', '开始学习', '继续学习'
  ]);
  let autoSynced = false;

  if (/passport|login|dowork/i.test(location.pathname) ||
      /\/exam|\/test\//i.test(location.pathname)) {
    return;
  }
  const pageHint = location.hostname + location.pathname;
  const looksRelevant = /mooc|course|work|space|base|mycourse/i.test(pageHint) ||
    !!document.querySelector(
      'a[href*="workId"], a[href*="workid"], [onclick*="workId"], [onclick*="workid"], [data-workid]'
    );
  if (!looksRelevant) return;

  function pad(value) {
    return String(value).padStart(2, '0');
  }

  function textOf(node) {
    if (!node) return '';
    const raw = (typeof node.innerText === 'string' && node.innerText) || node.textContent || '';
    return raw.replace(/\u00a0/g, ' ').replace(/[ \t]+/g, ' ').replace(/\s*\n\s*/g, ' ').trim();
  }

  function firstLine(node) {
    const raw = (typeof node.innerText === 'string' && node.innerText) || node.textContent || '';
    return raw.split(/\n+/).map(function (line) {
      return line.replace(/\s+/g, ' ').trim();
    }).filter(Boolean)[0] || '';
  }

  function cleanTitle(value) {
    let title = String(value || '').replace(/\s+/g, ' ').trim();
    title = title.replace(/^(作业|考试|任务|任务点)\s*[:：]?\s*/, '');
    title = title.split(/截止时间|截止日期|截止[:：]|结束时间/)[0].trim();
    title = title.replace(/^(未交|未提交|待做|待完成|进行中|未开始|已交|已提交|待批阅|已批阅|已完成)\s*/, '');
    title = title.replace(/\s*(已批阅|待批阅|已提交|已交|未提交|未交|待完成|已完成|未开始|进行中|已截止|已过期|已结束)\s*$/, '');
    title = title.replace(/\s*\d{4}\s*[-/年.]\s*\d{1,2}\s*[-/月.]\s*\d{1,2}.*$/, '');
    if (title.length > 200) title = title.slice(0, 200).trim();
    return GENERIC_TITLES.has(title) ? '' : title;
  }

  function extractStatus(text) {
    let best = '';
    let bestIndex = -1;
    STATUS_WORDS.forEach(function (word) {
      const index = text.lastIndexOf(word);
      if (index > bestIndex) {
        best = word;
        bestIndex = index;
      }
    });
    return best;
  }

  function normalizeDue(raw) {
    const source = String(raw || '').replace(/\u00a0/g, ' ').trim();
    if (!source) return '';
    const full = source.match(
      /(\d{4})\s*[-/年.]\s*(\d{1,2})\s*[-/月.]\s*(\d{1,2})\s*[日号]?(?:\s+(\d{1,2})[:：](\d{2}))?/
    );
    if (full) {
      let value = full[1] + '-' + pad(full[2]) + '-' + pad(full[3]);
      if (full[4] !== undefined) value += ' ' + pad(full[4]) + ':' + full[5];
      return value;
    }
    const monthDay = source.match(
      /(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]?(?:\s+(\d{1,2})[:：](\d{2}))?/
    );
    if (monthDay) {
      let value = monthDay[1] + '月' + monthDay[2] + '日';
      if (monthDay[3] !== undefined) value += ' ' + pad(monthDay[3]) + ':' + monthDay[4];
      return value;
    }
    return source;
  }

  function extractDue(text) {
    const patterns = [
      /(?:截止时间|截止日期|提交截止|最晚提交|结束时间|截止)\s*[:：]?\s*(\d{4}\s*[-/年.]\s*\d{1,2}\s*[-/月.]\s*\d{1,2}\s*[日号]?(?:\s+\d{1,2}[:：]\d{2})?)/,
      /(?:截止时间|截止日期|提交截止|最晚提交|结束时间|截止)\s*[:：]?\s*(\d{1,2}\s*月\s*\d{1,2}\s*[日号]?(?:\s+\d{1,2}[:：]\d{2})?)/,
      /(\d{4}\s*[-/年.]\s*\d{1,2}\s*[-/月.]\s*\d{1,2}\s*[日号]?\s+\d{1,2}[:：]\d{2})/,
      /(\d{1,2}\s*月\s*\d{1,2}\s*[日号]?\s+\d{1,2}[:：]\d{2})/,
      /(剩余\s*\d+\s*天(?:\s*\d+\s*小时)?)/
    ];
    for (let i = 0; i < patterns.length; i += 1) {
      const match = text.match(patterns[i]);
      if (match) return normalizeDue(match[1]);
    }
    return '';
  }

  function hashText(value) {
    let hash = 5381;
    const text = String(value || '');
    for (let i = 0; i < text.length; i += 1) {
      hash = ((hash << 5) + hash + text.charCodeAt(i)) >>> 0;
    }
    return hash.toString(16);
  }

  function param(url, names) {
    for (let i = 0; i < names.length; i += 1) {
      const value = url.searchParams.get(names[i]);
      if (value) return value;
    }
    return '';
  }

  function extractWorkId(element, row, href) {
    let url = null;
    try {
      url = new URL(href, location.href);
    } catch (error) {
      url = null;
    }
    if (url) {
      const fromUrl = param(url, ['workId', 'workid', 'work_id']);
      if (fromUrl) return fromUrl;
    }
    const dataId = (element && element.dataset && (element.dataset.workid || element.dataset.workId)) ||
      (row && row.dataset && (row.dataset.workid || row.dataset.workId));
    if (dataId) return String(dataId);
    const blob = [
      href || '',
      element ? element.getAttribute('onclick') || '' : '',
      row ? row.innerHTML || '' : ''
    ].join(' ');
    const match = blob.match(/workId["']?\s*[:=]\s*["']?(\d{3,})/i) ||
      blob.match(/workid=(\d{3,})/i);
    return match ? match[1] : '';
  }

  function titleFrom(element, row) {
    const direct = cleanTitle(textOf(element));
    if (direct) return direct;
    const node = row && row.querySelector(
      '.work-title, .workTitle, .title, .name, .task-title, h3, h4, strong'
    );
    const nested = cleanTitle(textOf(node));
    if (nested) return nested;
    return cleanTitle(firstLine(row));
  }

  function courseInfo(doc, pageUrl) {
    let url = null;
    try {
      url = new URL(pageUrl);
    } catch (error) {
      url = null;
    }
    const courseId = url ? param(url, ['courseId', 'courseid', 'course_id']) : '';
    const classId = url ? param(url, ['classId', 'classid', 'clazzid', 'clazzId']) : '';
    const cpi = url ? param(url, ['cpi']) : '';
    const enc = url ? param(url, ['enc']) : '';
    const nodes = doc.querySelectorAll(
      '.courseName, .course-name, .courseTitle, .course-title, .course_title, .course_name'
    );
    let name = '';
    for (let i = 0; i < nodes.length; i += 1) {
      name = cleanTitle(textOf(nodes[i]));
      if (name) break;
    }
    if (!name) {
      const title = String(doc.title || '')
        .replace(/[-_|—].*$/, '')
        .replace(/超星学习通|学习通|作业列表|作业详情|作业|章节|任务点/g, '')
        .replace(/\s+/g, ' ')
        .trim();
      name = cleanTitle(title);
    }
    return {
      courseId: courseId,
      classId: classId,
      cpi: cpi,
      enc: enc,
      courseName: name || '学习通课程'
    };
  }

  function collectFromDocument(doc, pageUrl, courseOverride, limit) {
    const maxItems = limit || 500;
    const baseCourse = courseOverride || courseInfo(doc, pageUrl);
    const results = [];
    const seen = new Set();
    const candidates = doc.querySelectorAll('a[href], [onclick], [data-workid], [data-workId]');

    for (let i = 0; i < candidates.length && results.length < maxItems; i += 1) {
      const element = candidates[i];
      const href = (element.tagName === 'A' && element.href)
        ? element.href : (element.getAttribute('href') || '');
      const onclick = element.getAttribute('onclick') || '';
      const dataId = (element.dataset && (element.dataset.workid || element.dataset.workId)) || '';
      const blob = [href, onclick, dataId].join(' ');
      if (!blob || (!/workid|work\/view|work\/detail|workDetail|studentWork/i.test(blob))) continue;
      if (/\/work\/list/i.test(href) && !/workid=/i.test(href)) continue;

      const row = element.closest(
        'tr, li, .work-item, .work-list-item, .workItem, .work_item, .list-item, ' +
        '.task-item, .content-item, .item'
      ) || element.parentElement;
      if (!row) continue;
      const rowText = textOf(row);
      if (rowText.length < 3 || rowText.length > 1600) continue;

      const title = titleFrom(element, row);
      if (!title) continue;
      const due = extractDue(rowText);
      const workId = extractWorkId(element, row, href);
      const assignmentId = workId || hashText(
        baseCourse.courseName + '|' + title + '|' + due
      );
      const dedupe = baseCourse.courseId + '|' + assignmentId;
      if (seen.has(dedupe)) continue;
      seen.add(dedupe);

      let detailUrl = pageUrl;
      try {
        const resolved = new URL(href, pageUrl).href;
        if (/^https?:\/\/[^/]*chaoxing\.com/i.test(resolved)) detailUrl = resolved;
      } catch (error) {
        detailUrl = pageUrl;
      }
      results.push({
        source: 'chaoxing',
        course_id: baseCourse.courseId || hashText(baseCourse.courseName),
        course_name: baseCourse.courseName,
        assignment_id: assignmentId,
        title: title,
        due_at: due,
        status: extractStatus(rowText),
        url: detailUrl
      });
    }

    if (!results.length) {
      const rows = doc.querySelectorAll(
        'tr, li, .work-item, .work-list-item, .workItem, .work_item, .list-item, .item'
      );
      for (let i = 0; i < rows.length && results.length < maxItems; i += 1) {
        const row = rows[i];
        const rowText = textOf(row);
        if (rowText.length < 6 || rowText.length > 800) continue;
        if (!/(作业|实验|报告|习题|任务|提交|截止)/.test(rowText)) continue;
        const due = extractDue(rowText);
        if (!due) continue;
        const title = cleanTitle(textOf(row.querySelector(
          'a, .title, .work-title, h3, h4, strong'
        ))) || cleanTitle(firstLine(row));
        if (!title) continue;
        const assignmentId = hashText(baseCourse.courseName + '|' + title + '|' + due);
        const dedupe = baseCourse.courseId + '|' + assignmentId;
        if (seen.has(dedupe)) continue;
        seen.add(dedupe);
        results.push({
          source: 'chaoxing',
          course_id: baseCourse.courseId || hashText(baseCourse.courseName),
          course_name: baseCourse.courseName,
          assignment_id: assignmentId,
          title: title,
          due_at: due,
          status: extractStatus(rowText),
          url: pageUrl
        });
      }
    }
    return results;
  }

  function collectCurrent() {
    return collectFromDocument(document, location.href, null, 500);
  }

  function discoverCourses() {
    const found = new Map();
    const anchors = document.querySelectorAll('a[href]');
    for (let i = 0; i < anchors.length; i += 1) {
      const anchor = anchors[i];
      let url = null;
      try {
        url = new URL(anchor.href || anchor.getAttribute('href'), location.href);
      } catch (error) {
        continue;
      }
      if (!/(^|\.)chaoxing\.com$/i.test(url.hostname)) continue;
      const courseId = param(url, ['courseId', 'courseid', 'course_id']);
      const classId = param(url, ['classId', 'classid', 'clazzid', 'clazzId']);
      if (!courseId || !classId) continue;
      const name = cleanTitle(textOf(anchor)) || cleanTitle(String(document.title || '')) || '学习通课程';
      const key = courseId + ':' + classId;
      if (!found.has(key)) {
        found.set(key, {
          courseId: courseId,
          classId: classId,
          cpi: param(url, ['cpi']),
          enc: param(url, ['enc']),
          courseName: name
        });
      }
    }
    return Array.from(found.values()).slice(0, 20);
  }

  function workListUrl(course) {
    const url = new URL('https://mooc2-ans.chaoxing.com/mooc2/work/list');
    url.searchParams.set('courseId', course.courseId);
    url.searchParams.set('classId', course.classId);
    if (course.cpi) url.searchParams.set('cpi', course.cpi);
    if (course.enc) url.searchParams.set('enc', course.enc);
    return url.href;
  }

  function httpGet(url, credentials) {
    return new Promise(function (resolve, reject) {
      if (typeof GM_xmlhttpRequest === 'function') {
        GM_xmlhttpRequest({
          method: 'GET',
          url: url,
          timeout: 15000,
          withCredentials: true,
          onload: function (response) {
            if (response.status >= 200 && response.status < 400) resolve(response.responseText);
            else reject(new Error('HTTP ' + response.status));
          },
          onerror: function () { reject(new Error('网络错误')); },
          ontimeout: function () { reject(new Error('超时')); }
        });
        return;
      }
      fetch(url, { credentials: credentials === false ? 'omit' : 'include' })
        .then(function (response) {
          if (!response.ok) throw new Error('HTTP ' + response.status);
          return response.text();
        })
        .then(resolve, reject);
    });
  }

  function send(items, label) {
    if (!items.length) {
      setStatus('没有识别到作业。请打开课程作业列表页后再试。');
      return;
    }
    setStatus('正在发送 ' + items.length + ' 条' + (label ? '（' + label + '）' : '') + '…');
    const body = JSON.stringify({
      version: 1,
      source: 'chaoxing',
      assignments: items.slice(0, 1000)
    });
    const onDone = function (status, responseText) {
      let data = null;
      try { data = JSON.parse(responseText || '{}'); } catch (error) { data = null; }
      if (status === 200 && data && data.ok) {
        setStatus(
          '已同步：新增 ' + (data.inserted || 0) +
          '，更新 ' + (data.updated || 0) +
          '，跳过 ' + (data.skipped || 0)
        );
      } else {
        setStatus('同步失败：' + ((data && data.error) || ('HTTP ' + status)));
      }
    };
    if (typeof GM_xmlhttpRequest === 'function') {
      GM_xmlhttpRequest({
        method: 'POST',
        url: BRIDGE_URL,
        headers: {
          'Content-Type': 'application/json',
          'X-QQLI-Token': TOKEN
        },
        data: body,
        timeout: 15000,
        onload: function (response) { onDone(response.status, response.responseText); },
        onerror: function () { setStatus('无法连接本机程序，请确认 QQ Local Inbox 正在运行'); },
        ontimeout: function () { setStatus('连接本机程序超时'); }
      });
      return;
    }
    fetch(BRIDGE_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-QQLI-Token': TOKEN
      },
      body: body
    }).then(function (response) {
      return response.text().then(function (text) { onDone(response.status, text); });
    }).catch(function () {
      setStatus('无法连接本机程序，请确认 QQ Local Inbox 正在运行');
    });
  }

  function preview(items) {
    if (!items.length) {
      setStatus('没有识别到作业。请打开课程作业列表页后再试。');
      return;
    }
    const sample = items.slice(0, 3).map(function (item) {
      return '· ' + item.course_name + '｜' + item.title + '｜' + (item.due_at || '无截止');
    }).join('\n');
    setStatus('识别到 ' + items.length + ' 条：\n' + sample);
    if (typeof console !== 'undefined' && console.table) console.table(items);
  }

  async function syncAllCourses() {
    const courses = discoverCourses();
    if (!courses.length) {
      setStatus('当前页没有找到课程入口。请在学习通“我学的课”页面使用，或逐门课程打开作业页后同步。');
      return;
    }
    const collected = [];
    const seen = new Set();
    let failed = 0;
    for (let i = 0; i < courses.length; i += 1) {
      const course = courses[i];
      setStatus('正在读取课程 ' + (i + 1) + '/' + courses.length + '：' + course.courseName);
      try {
        const html = await httpGet(workListUrl(course), true);
        const doc = new DOMParser().parseFromString(html, 'text/html');
        const items = collectFromDocument(doc, workListUrl(course), course, 300);
        items.forEach(function (item) {
          const key = item.course_id + '|' + item.assignment_id;
          if (!seen.has(key)) {
            seen.add(key);
            collected.push(item);
          }
        });
        if (!items.length) failed += 1;
      } catch (error) {
        failed += 1;
      }
      await new Promise(function (resolve) { setTimeout(resolve, 350); });
    }
    if (!collected.length) {
      setStatus('未能读取作业。请确认已登录、课程仍可访问；也可以逐门课程打开作业页后用“同步当前页”。');
      return;
    }
    send(collected, failed ? failed + ' 门课程读取失败' : '全部课程');
  }

  let statusNode = null;

  function setStatus(text) {
    if (statusNode) statusNode.textContent = text;
  }

  function buildPanel() {
    if (document.getElementById('qqli-chaoxing-host')) return;
    const host = document.createElement('div');
    host.id = 'qqli-chaoxing-host';
    const shadow = host.attachShadow({ mode: 'open' });
    shadow.innerHTML = [
      '<style>',
      ':host{all:initial}',
      '.panel{position:fixed;right:18px;bottom:18px;z-index:2147483647;width:268px;',
      'background:#fff;border:1px solid #e5e7eb;border-radius:14px;',
      'box-shadow:0 10px 30px rgba(15,23,42,.18);font:13px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif;',
      'color:#1f2937;padding:13px 14px}',
      '.head{display:flex;align-items:center;justify-content:space-between;margin-bottom:6px}',
      '.title{font-weight:700;font-size:13px}',
      '.chip{font-size:10px;color:#00a1d6;background:#e9f8fe;border-radius:999px;padding:2px 7px}',
      '.hint{font-size:11px;color:#6b7280;margin:0 0 9px}',
      '.row{display:flex;gap:6px;margin-bottom:7px}',
      'button{border:0;border-radius:8px;padding:7px 9px;font-size:12px;cursor:pointer;font-family:inherit}',
      '.primary{background:#00aeec;color:#fff;font-weight:600;flex:1}',
      '.soft{background:#eef6ff;color:#0369a1;flex:1}',
      '.ghost{background:#f3f4f6;color:#4b5563}',
      'button:disabled{opacity:.55;cursor:default}',
      '.status{white-space:pre-wrap;word-break:break-word;font-size:11px;color:#4b5563;',
      'background:#f8fafc;border-radius:8px;padding:7px 8px;min-height:30px}',
      '.foot{display:flex;align-items:center;gap:5px;margin-top:7px;font-size:11px;color:#6b7280}',
      '.foot input{margin:0}',
      '.foot a{margin-left:auto;color:#9ca3af;text-decoration:none;cursor:pointer}',
      '</style>',
      '<div class="panel">',
      '  <div class="head"><span class="title">QQ Local Inbox</span><span class="chip">只读</span></div>',
      '  <p class="hint">读取作业标题/课程/截止时间，同步到本机；不读取密码，不自动提交。</p>',
      '  <div class="row">',
      '    <button class="primary" id="syncCurrent">同步当前页</button>',
      '    <button class="soft" id="syncAll">全部课程</button>',
      '  </div>',
      '  <div class="row"><button class="ghost" id="preview" style="flex:1">预览识别结果</button></div>',
      '  <div class="status" id="status">打开课程作业页后点“同步当前页”。</div>',
      '  <div class="foot">',
      '    <label><input type="checkbox" id="auto"> 打开作业页时自动同步</label>',
      '    <a id="collapse">收起</a>',
      '  </div>',
      '</div>'
    ].join('');
    document.documentElement.appendChild(host);

    statusNode = shadow.getElementById('status');
    const autoBox = shadow.getElementById('auto');
    let autoOn = true;
    try {
      autoOn = localStorage.getItem(AUTO_KEY) !== '0';
    } catch (error) { /* ignore */ }
    autoBox.checked = autoOn;
    autoBox.addEventListener('change', function () {
      try {
        localStorage.setItem(AUTO_KEY, autoBox.checked ? '1' : '0');
      } catch (error) { /* ignore */ }
    });
    shadow.getElementById('syncCurrent').addEventListener('click', function () {
      send(collectCurrent(), '当前页');
    });
    shadow.getElementById('syncAll').addEventListener('click', function () {
      syncAllCourses();
    });
    shadow.getElementById('preview').addEventListener('click', function () {
      preview(collectCurrent());
    });
    shadow.getElementById('collapse').addEventListener('click', function () {
      host.style.display = 'none';
    });
  }

  function autoSync() {
    if (autoSynced) return;
    try {
      if (localStorage.getItem(AUTO_KEY) === '0') return;
    } catch (error) { /* ignore */ }
    const items = collectCurrent();
    if (!items.length) return;
    autoSynced = true;
    send(items, '自动');
  }

  buildPanel();
  setTimeout(autoSync, 2500);
  setTimeout(autoSync, 7000);
})();
