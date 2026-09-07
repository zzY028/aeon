/* ==========================================================================
   Aeon Shell · 全局「主题 + 移动端导航」
   —— 全站唯一负责人

   ① 主题读取 / 切换 / 持久化（首屏防闪 + 多标签同步）
   ② 主题切换入口（桌面侧栏底 / 移动端底栏 / 无侧栏页浮动钮）
   ③ 移动端底栏分级导航（4 个主 Tab + 「更多」抽屉）

   引入方式：每个页面 <head> 内 <script src="/static/common/aeon-shell.js"></script>
   ⚠️ 必须在 <body> 之前同步加载，否则已选浅色的用户首屏会闪一下深色。

   约定：data-theme 只取 'light' | 'dark' 两个显式值，
        不再用「去掉属性 = 浅色」的隐式写法（那是之前切换出 bug 的根源之一）。
   ========================================================================== */
(function () {
  'use strict';

  var KEY = 'aeon_theme';
  var LABEL = { light: '白昼胶片', dark: '午夜胶片' };
  var root = document.documentElement;

  /* ---------- 工具 ---------- */
  function normalize(v) { return v === 'light' ? 'light' : 'dark'; }
  function base(href) { return String(href || '').split(/[?#]/)[0].split('/').pop(); }
  function curPage() { return base(location.pathname); }

  function lsGet() {
    try { return localStorage.getItem(KEY); } catch (e) { return null; }
  }
  function lsSet(t) {
    try { localStorage.setItem(KEY, t); } catch (e) { /* 隐私模式忽略 */ }
  }

  /* ---------- ① 主题状态 ---------- */

  // 所有需要跟随主题刷新文案的入口节点
  var entries = [];
  var seg = null;

  function paint(t) {
    var target = t === 'dark' ? 'light' : 'dark';
    var svg = target === 'light' ? SVG_SUN() : SVG_MOON();   // ⚠️ 必须调用，不能传函数引用

    for (var i = 0; i < entries.length; i++) {
      var n = entries[i];
      n.setAttribute('data-cur', t);
      n.setAttribute('title', LABEL[target]);
      n.setAttribute('aria-label', '切换到' + LABEL[target]);
      var ic = n.querySelector('.js-tico');
      if (ic) ic.innerHTML = svg;
      var tx = n.querySelector('.js-ttxt');
      if (tx) tx.textContent = n.hasAttribute('data-compact') ? '' : LABEL[target];
    }

    if (seg) {
      for (var j = 0; j < seg.children.length; j++) {
        var b = seg.children[j];
        if (b.getAttribute('data-theme-set') === t) b.classList.add('on');
        else b.classList.remove('on');
      }
    }
  }

  function apply(t) {
    t = normalize(t);
    root.setAttribute('data-theme', t);
    paint(t);
    // 广播出去，供页面级 UI（如设置页的开关）保持同步
    try {
      document.dispatchEvent(new CustomEvent('aeon:themechange', { detail: { theme: t } }));
    } catch (e) { /* 老浏览器忽略 */ }
    return t;
  }

  var Api = {
    get: function () { return normalize(root.getAttribute('data-theme')); },
    set: function (t) { t = apply(t); lsSet(t); return t; },
    toggle: function () { return Api.set(Api.get() === 'dark' ? 'light' : 'dark'); }
  };
  window.AeonTheme = Api;

  /* ========== 立即落地：赶在 body 绘制前定好主题，杜绝首屏闪烁 ========== */
  apply(normalize(lsGet() === null ? root.getAttribute('data-theme') : lsGet()));

  // 多标签页 / 多窗口同步
  window.addEventListener('storage', function (e) {
    if (e.key === KEY && e.newValue) apply(e.newValue);
  });

  /* ---------- 图标 ---------- */
  function SVG_SUN() {
    return '<svg class="ic" viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">' +
      '<circle cx="12" cy="12" r="4"/>' +
      '<path d="M12 2.5v2.2M12 19.3v2.2M2.5 12h2.2M19.3 12h2.2M5.3 5.3l1.6 1.6M17.1 17.1l1.6 1.6M18.7 5.3l-1.6 1.6M6.9 17.1l-1.6 1.6"/>' +
      '</svg>';
  }
  function SVG_MOON() {
    return '<svg class="ic" viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">' +
      '<path d="M12 3a9 9 0 0 1 0 18 5.5 9 0 0 0 0-18z"/></svg>';
  }
  function SVG_MORE() {
    return '<svg class="ic" viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">' +
      '<circle cx="5" cy="12" r="1.7"/><circle cx="12" cy="12" r="1.7"/><circle cx="19" cy="12" r="1.7"/></svg>';
  }

  /* ---------- ② 构造切换入口 ---------- */
  function makeEntry() {
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'theme-x';
    b.innerHTML = '<span class="js-tico"></span><span class="js-ttxt"></span>';
    b.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      Api.toggle();
    });
    entries.push(b);
    return b;
  }

  /* ---------- ③ 「更多」抽屉 ---------- */
  var mask = null;

  function openSheet() {
    if (!mask) return;
    mask.classList.add('open');
    document.body.classList.add('sheet-locked');
  }
  function closeSheet() {
    if (!mask) return;
    mask.classList.remove('open');
    document.body.classList.remove('sheet-locked');
  }

  function buildSheet(secondary) {
    mask = document.createElement('div');
    mask.className = 'aeon-sheet-mask';
    mask.innerHTML =
      '<div class="aeon-sheet" role="dialog" aria-label="更多功能" aria-modal="true">' +
        '<div class="sheet-handle"></div>' +
        '<div class="sheet-block">' +
          '<div class="sheet-cap">外观 · APPEARANCE</div>' +
          '<div class="sheet-seg" id="aeonThemeSeg">' +
            '<button type="button" data-theme-set="light">' + SVG_SUN() + '<span>白昼胶片</span></button>' +
            '<button type="button" data-theme-set="dark">' + SVG_MOON() + '<span>午夜胶片</span></button>' +
          '</div>' +
        '</div>' +
        '<div class="sheet-block">' +
          '<div class="sheet-cap">更多功能 · MORE</div>' +
          '<div class="sheet-grid" id="aeonSheetGrid"></div>' +
        '</div>' +
      '</div>';
    document.body.appendChild(mask);

    // 复用原导航项的图标 + 文案，避免两份来源不一致
    var grid = mask.querySelector('#aeonSheetGrid');
    secondary.forEach(function (a) {
      var c = document.createElement('a');
      c.className = 'sheet-item';
      c.setAttribute('href', a.getAttribute('href') || '#');
      if (a.classList.contains('on')) c.classList.add('on');
      c.innerHTML = a.innerHTML;
      grid.appendChild(c);
    });

    seg = mask.querySelector('#aeonThemeSeg');
    seg.addEventListener('click', function (e) {
      var el = e.target, hit = null;
      while (el && el !== seg) {
        if (el.getAttribute && el.getAttribute('data-theme-set')) { hit = el; break; }
        el = el.parentNode;
      }
      if (hit) Api.set(hit.getAttribute('data-theme-set'));
    });

    mask.addEventListener('click', function (e) {
      if (e.target === mask) closeSheet();          // 点遮罩关闭
    });
    mask.querySelector('.sheet-handle').addEventListener('click', closeSheet);
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') closeSheet();
    });
  }

  /* ---------- DOM 装配 ---------- */
  // 移动端底栏保留的一级入口（其余进「更多」）
  var PRIMARY = ['index.html', 'ledger.html', 'habits.html', 'schedule.html'];

  function build() {
    var side = document.querySelector('.side');
    var foot = side ? side.querySelector('.side-foot') : null;
    var nav = side ? side.querySelector('.nav') : null;

    // 桌面：侧栏底部放一个带文字的入口（所有页面统一）
    if (foot) foot.insertBefore(makeEntry(), foot.firstChild);

    if (!nav) {
      // 无侧栏页（登录 / 独立工具页）：右下浮动入口
      var fab = makeEntry();
      fab.classList.add('is-fab');
      document.body.appendChild(fab);
      paint(Api.get());
      return;
    }

    var links = Array.prototype.slice.call(nav.querySelectorAll('a'));
    var page = curPage();
    var secondary = [];

    links.forEach(function (a) {
      if (PRIMARY.indexOf(base(a.getAttribute('href'))) < 0) {
        a.classList.add('nav-sub');      // 移动端隐藏，桌面不受影响
        secondary.push(a);
      }
    });

    // 「更多」Tab
    var more = document.createElement('a');
    more.className = 'nav-more';
    more.setAttribute('href', 'javascript:void 0');
    more.setAttribute('role', 'button');
    more.setAttribute('aria-label', '更多功能');
    more.innerHTML = SVG_MORE() + '<span>更多</span>';
    more.addEventListener('click', function (e) { e.preventDefault(); openSheet(); });

    // 当前页属于二级时，点亮「更多」
    var onSecondary = secondary.some(function (a) { return base(a.getAttribute('href')) === page; });
    if (onSecondary) more.classList.add('on');
    nav.appendChild(more);

    // 底栏右端常驻的图标型主题入口（移动端可见）
    var compact = makeEntry();
    compact.classList.add('nav-theme');
    compact.setAttribute('data-compact', '1');
    nav.appendChild(compact);

    buildSheet(secondary);
    paint(Api.get());
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', build);
  } else {
    build();
  }
})();
