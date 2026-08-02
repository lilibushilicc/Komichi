/* Komichi Web 端共享逻辑：配置 / 认证 / API 请求 / 工具函数 */
(function () {
  'use strict';

  var KEYS = { worker: 'komichi_worker_url', token: 'komichi_token', user: 'komichi_user' };

  var Komichi = {};

  /* ---------------- 配置 ---------------- */

  Komichi.getWorkerUrl = function () {
    return (localStorage.getItem(KEYS.worker) || '').replace(/\/+$/, '');
  };

  Komichi.setWorkerUrl = function (url) {
    localStorage.setItem(KEYS.worker, (url || '').trim().replace(/\/+$/, ''));
  };

  /* ---------------- 认证 ---------------- */

  Komichi.getToken = function () {
    return localStorage.getItem(KEYS.token) || '';
  };

  Komichi.getUser = function () {
    try { return JSON.parse(localStorage.getItem(KEYS.user)); } catch (e) { return null; }
  };

  Komichi.setAuth = function (token, user) {
    localStorage.setItem(KEYS.token, token);
    localStorage.setItem(KEYS.user, JSON.stringify(user));
  };

  Komichi.clearAuth = function () {
    localStorage.removeItem(KEYS.token);
    localStorage.removeItem(KEYS.user);
  };

  Komichi.requireAuth = function () {
    if (!Komichi.getToken()) {
      location.replace('login.html');
      return false;
    }
    return true;
  };

  /* ---------------- API 请求 ---------------- */

  async function request(path, opts) {
    opts = opts || {};
    var base = Komichi.getWorkerUrl();
    if (!base) throw new Error('未配置服务器地址，请先在设置或登录页填写');

    var headers = {};
    if (opts.json !== false) headers['Content-Type'] = 'application/json';
    if (opts.auth !== false && Komichi.getToken()) {
      headers['Authorization'] = 'Bearer ' + Komichi.getToken();
    }

    var resp;
    try {
      resp = await fetch(base + path, {
        method: opts.method || 'GET',
        headers: headers,
        body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
      });
    } catch (e) {
      throw new Error('网络错误，无法连接服务器');
    }

    var data = null;
    try { data = await resp.json(); } catch (e) { /* 非 JSON 响应 */ }

    if (!resp.ok || !data || (data.code !== 200 && data.code !== 0)) {
      var msg = (data && data.msg) || ('请求失败 (' + resp.status + ')');
      if (resp.status === 401 || (data && data.code === 401)) {
        Komichi.clearAuth();
        if (!/login\.html/.test(location.pathname)) {
          location.href = 'login.html';
          throw new Error('登录已过期');
        }
      }
      throw new Error(msg);
    }
    return data.data;
  }

  Komichi.api = {
    ping: function () { return request('/ping', { auth: false }); },
    login: function (username, password) {
      return request('/api/auth/login', { method: 'POST', body: { username: username, password: password }, auth: false });
    },
    listWorks: function (params) {
      return request('/api/work/list?' + new URLSearchParams(params || {}).toString());
    },
    getWork: function (id) { return request('/api/work/' + id); },
    checkWork: function (id) { return request('/api/work/check/' + id); },
    bookmarks: function () { return request('/api/bookmark/list'); },
    saveBookmark: function (work_id, chapter_num, note) {
      return request('/api/bookmark/save', { method: 'POST', body: { work_id: work_id, chapter_num: chapter_num, note: note || undefined } });
    },
    sign: function (path) { return request('/api/r2/sign?path=' + encodeURIComponent(path)); },
  };

  /* ---------------- 图片 ---------------- */

  // path -> 签名响应缓存。签名 URL 在服务器端按天稳定，
  // 过期时间内直接复用，避免每个封面反复请求 /api/r2/sign。
  var _signCache = {};

  Komichi.signedImageUrl = async function (r2Path) {
    if (!r2Path) return '';
    var cached = _signCache[r2Path];
    if (cached && cached.expire_at * 1000 > Date.now()) return cached.url;
    try {
      var data = await Komichi.api.sign(r2Path);
      if (data && data.url) {
        _signCache[r2Path] = data;
      }
      return (data && data.url) || '';
    } catch (e) {
      return '';
    }
  };

  /**
   * 探测式加载章节图片（R2 路径按约定，无数量记录）。
   * 返回签名 URL 数组。起始索引 0（兼容既有数据）。
   */
  Komichi.loadChapterPages = async function (workId, chapterNum) {
    var pages = [];
    var ext = null;
    var tries = ['jpg', 'png', 'webp', 'gif'];

    for (var i = 0; i < 1000; i++) {
      var exts = ext ? [ext] : tries;
      var found = false;
      for (var e = 0; e < exts.length; e++) {
        var path = 'komichi/chapters/' + workId + '/' + chapterNum + '/' + String(i).padStart(4, '0') + '.' + exts[e];
        try {
          var signed = await Komichi.api.sign(path);
          var probe = await fetch(signed.url, { method: 'HEAD' });
          if (probe.ok) {
            if (!ext) ext = exts[e];
            pages.push(signed.url);
            found = true;
            break;
          }
        } catch (err) { /* 网络抖动，尝试下一个 */ }
      }
      if (!found) break;
    }
    return pages;
  };

  /* ---------------- 工具 ---------------- */

  Komichi.timeAgo = function (iso) {
    if (!iso) return '';
    var t = new Date(iso).getTime();
    if (isNaN(t)) return '';
    var diff = (Date.now() - t) / 1000;
    if (diff < 60) return '刚刚';
    if (diff < 3600) return Math.floor(diff / 60) + ' 分钟前';
    if (diff < 86400) return Math.floor(diff / 3600) + ' 小时前';
    if (diff < 172800) return '昨天';
    if (diff < 604800) return Math.floor(diff / 86400) + ' 天前';
    var d = new Date(t);
    return (d.getMonth() + 1) + '-' + d.getDate();
  };

  Komichi.cover = function (work) {
    var el = document.createElement('img');
    el.loading = 'lazy';
    el.alt = work.title || '';
    var placeholders = ['cover-01.jpg', 'cover-02.jpg', 'cover-03.jpg', 'cover-04.jpg', 'cover-05.jpg', 'cover-06.jpg', 'cover-07.jpg', 'cover-08.jpg'];
    var ph = placeholders[((work.id || 1) - 1) % placeholders.length];
    el.src = '../assets/covers/' + ph;
    if (work.cover_r2_path) {
      Komichi.signedImageUrl(work.cover_r2_path).then(function (url) {
        if (url) el.src = url;
      }).catch(function () {});
    }
    return el;
  };

  Komichi.toast = function (msg) {
    var box = document.getElementById('komichi-toast');
    if (!box) {
      box = document.createElement('div');
      box.id = 'komichi-toast';
      box.style.cssText = 'position:fixed;left:50%;bottom:88px;transform:translateX(-50%);z-index:9999;max-width:80vw;padding:10px 16px;border-radius:var(--radius-lg);background:var(--bg-base-secondary);border:1px solid var(--border-neutral-l1);color:var(--text-default);font-size:var(--body-sm-font-size);box-shadow:0 8px 24px rgba(0,0,0,.35);transition:opacity .25s;pointer-events:none;';
      document.body.appendChild(box);
    }
    box.textContent = msg;
    box.style.opacity = '1';
    clearTimeout(Komichi.toast.timer);
    Komichi.toast.timer = setTimeout(function () { box.style.opacity = '0'; }, 2400);
  };

  /* ---------------- 导航 ---------------- */

  Komichi.initNav = function (active) {
    document.querySelectorAll('[data-nav-key]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        location.href = btn.dataset.navKey + '.html';
      });
      if (btn.dataset.navKey === active) btn.classList.add('is-active');
    });
    document.querySelectorAll('[data-back]').forEach(function (btn) {
      btn.addEventListener('click', function () { history.back(); });
    });
  };

  window.Komichi = Komichi;
})();
