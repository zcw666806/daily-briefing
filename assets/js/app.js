/* 今日信息差 · 数据驱动渲染
 * 数据来源（二选一）：
 *  1) 单文件构建时由构建脚本注入 window.__EDITIONS__
 *  2) 多文件部署时从 data/manifest.json + data/editions/<date>.json 加载
 */
(function () {
  'use strict';

  var ARCHIVE_LIMIT = 30;
  var DIR_ARROW = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M7 17 17 7M7 7h10v10"/></svg>';

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  function dirClass(d) { return d === 'up' ? 'up' : d === 'down' ? 'down' : ''; }

  /* ---------- 片段渲染 ---------- */

  function renderIntlTape(t) {
    var items = t.items.map(function (it) {
      return '<div class="pulse"><b class="' + dirClass(it.dir) + '">' + esc(it.value) + '</b>' +
        '<span>' + esc(it.unit) + '　<span class="' + dirClass(it.changeDir || it.dir) + '">' + esc(it.change) + '</span></span></div>';
    }).join('');
    return '<div class="tape-kicker"><strong>' + esc(t.title) + '</strong><span>' + esc(t.note || '') + '</span></div>' +
      '<div class="tape">' + items + '</div>';
  }

  function renderChinaTape(t) {
    var items = t.items.map(function (it) {
      var v = '<b' + (it.dir ? ' class="' + dirClass(it.dir) + '"' : '') + '>' + esc(it.value) + '</b>';
      var detail = '<span class="pulse-detail"><span>' + esc(it.label) +
        (it.change ? '　<span class="' + dirClass(it.changeDir) + '">' + esc(it.change) + '</span>' : '') + '</span>' +
        (it.sub ? '<small>' + esc(it.sub) + '</small>' : '') + '</span>';
      return '<div class="pulse">' + v + detail + '</div>';
    }).join('');
    return '<div class="tape-kicker"><strong>' + esc(t.title) + '</strong><span>' + (t.noteHtml || '') + '</span></div>' +
      '<div class="tape rmb-tape">' + items + '</div>';
  }

  function renderFxTape(t) {
    var formula = '<div class="pulse"><b>' + esc(t.formulaLabel || '换算口径') + '</b>' +
      '<span class="pulse-detail"><span>' + esc(t.formula) + '</span>' +
      (t.formulaNote ? '<small>' + esc(t.formulaNote) + '</small>' : '') + '</span></div>';
    var items = t.items.map(function (it) {
      return '<div class="pulse"><b>' + esc(spreadText(it.value)) + '</b>' +
        '<span class="pulse-detail"><span>' + esc(it.label) + '</span>' +
        (it.sub ? '<small>' + esc(it.sub) + '</small>' : '') + '</span></div>';
    }).join('');
    return '<div class="tape-kicker"><strong>' + esc(t.title) + '</strong><span>' + (t.noteHtml || '') + '</span></div>' +
      '<div class="tape basis-tape">' + formula + items + '</div>';
  }

  // 换算差价是国内外静态价差（国际折算价 − 国内报价），不是涨跌：
  // 不用红绿涨跌色，把 "-162.78" 翻译成人话
  function spreadText(v) {
    if (v == null) return '—';
    var s = String(v).trim();
    if (s === '—' || s === '-' || s === '') return '—';
    var num = parseFloat(s.replace(/−/g, '-').replace(/,/g, ''));
    if (isNaN(num)) return s;
    if (num === 0) return '基本持平';
    var abs = Math.abs(num).toFixed(2);
    return (num < 0 ? '国内贵 ' : '国内便宜 ') + abs;
  }

  function renderMarket(m) {
    return '<section class="market-snapshot" aria-label="市场早盘快照">' +
      renderIntlTape(m.intl) + renderChinaTape(m.china) + renderFxTape(m.fx) + '</section>';
  }

  function renderInsights(d) {
    var insights = d.insights.map(function (it) {
      return '<article class="insight"><div class="insight-num">' + esc(it.num) + '</div>' +
        '<h2>' + esc(it.title) + '</h2><p>' + esc(it.text) + '</p></article>';
    }).join('');
    var watch = (d.watch || []).map(function (w) {
      return '<li><span>' + esc(w.date) + '</span><strong>' + esc(w.event) + '</strong></li>';
    }).join('');
    return '<aside class="insights" aria-label="三条核心洞察"><div>' +
      '<div class="section-label">一句话洞察 × 3</div>' +
      '<div class="insight-stack">' + insights + '</div></div>' +
      (watch ? '<div class="watch"><h3>接下来盯什么</h3><ul>' + watch + '</ul></div>' : '') + '</aside>';
  }

  function renderSource(s) {
    return '<a class="source" href="' + esc(s.url) + '" target="_blank" rel="noopener">' +
      esc(s.name) + ' ' + DIR_ARROW + '</a>';
  }

  function renderStory(st) {
    var meta = st.sources.map(renderSource).join('<span class="dot">·</span>') +
      '<span class="dot">·</span><span>' + esc(st.date) + '</span>' +
      (st.caveats || []).map(function (c) { return '<span class="caveat">' + esc(c) + '</span>'; }).join('');
    return '<article class="story' + (st.priority ? ' priority' : '') + '" data-category="' + esc(st.category) + '">' +
      '<div class="num">' + esc(st.num) + '</div><div>' +
      '<h3>' + st.titleHtml + '</h3>' +
      '<p class="why"><strong>为什么重要</strong>' + esc(st.why) + '</p>' +
      '<div class="meta">' + meta + '</div></div></article>';
  }

  function renderFeed(d) {
    var cats = d.categories.map(function (c) {
      var stories = c.stories.map(function (st) {
        st.category = c.id;
        return renderStory(st);
      }).join('');
      return '<section class="category" data-category="' + esc(c.id) + '" id="cat-' + esc(d.date) + '-' + esc(c.id) + '">' +
        '<div class="category-head"><h2>' + esc(c.title) + '</h2><span>' + c.stories.length + ' 条</span></div>' +
        stories + '</section>';
    }).join('');
    return '<main class="feed">' + cats + '<div class="empty">该分类暂无条目。</div></main>';
  }

  function renderToolbar(d) {
    var total = d.categories.reduce(function (n, c) { return n + c.stories.length; }, 0);
    var btns = '<button class="filter active" data-filter="all" aria-pressed="true">全部 ' + total + '</button>' +
      d.categories.map(function (c) {
        return '<button class="filter" data-filter="' + esc(c.id) + '" aria-pressed="false">' +
          esc(c.filterName) + ' ' + c.stories.length + '</button>';
      }).join('');
    return '<nav class="toolbar" aria-label="简报筛选"><div class="filters">' + btns + '</div>' +
      '<button class="mode" aria-pressed="false" title="切换精简阅读">' +
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h10"/></svg>' +
      '<span>精简阅读</span></button></nav>';
  }

  function renderBoundary(d) {
    if (!d.boundary || !d.boundary.length) return '';
    var items = d.boundary.map(function (b) {
      return '<div class="boundary-item">' + b + '</div>';
    }).join('');
    return '<section class="boundary" aria-labelledby="boundary-title-' + esc(d.date) + '">' +
      '<h2 id="boundary-title-' + esc(d.date) + '">核验边界</h2>' +
      '<div class="boundary-list">' + items + '</div></section>';
  }

  function renderEdition(d) {
    return '<article class="briefing-edition" data-edition="' + esc(d.date) + '" data-label="' + esc(d.label) + '">' +
      '<header class="mast"><div>' +
      '<div class="edition">' + esc(d.editionLine) + '</div>' +
      '<h1>' + d.headlineHtml + '</h1>' +
      '<p class="dek">' + esc(d.dek) + '</p></div>' +
      '<div class="stamp"><strong>' + esc(d.stamp.time) + '</strong><span>' + esc(d.stamp.note) + '</span></div>' +
      '</header>' +
      renderMarket(d.market) + renderToolbar(d) +
      '<div class="lead-grid">' + renderInsights(d) + renderFeed(d) + '</div>' +
      renderBoundary(d) +
      '<footer class="foot"><span>' + esc(d.footer.left) + '</span><span>' + esc(d.footer.right) + '</span></footer>' +
      '</article>';
  }

  /* ---------- 交互 ---------- */

  function wireEdition(article) {
    article.querySelectorAll('.filter').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var selected = btn.getAttribute('data-filter');
        article.querySelectorAll('.filter').forEach(function (b) {
          var active = b === btn;
          b.classList.toggle('active', active);
          b.setAttribute('aria-pressed', active ? 'true' : 'false');
        });
        article.querySelectorAll('.category').forEach(function (section) {
          section.hidden = selected !== 'all' && section.getAttribute('data-category') !== selected;
        });
        var grid = article.querySelector('.lead-grid');
        if (grid) window.scrollTo({ top: grid.offsetTop - 62, behavior: 'smooth' });
      });
    });
    article.querySelectorAll('.mode').forEach(function (modeBtn) {
      modeBtn.addEventListener('click', function () {
        var compact = document.body.classList.toggle('compact');
        document.querySelectorAll('.mode').forEach(function (button) {
          button.setAttribute('aria-pressed', compact ? 'true' : 'false');
          button.querySelector('span').textContent = compact ? '展开解读' : '精简阅读';
        });
      });
    });
  }

  function mount(editions) {
    editions.sort(function (a, b) { return b.date.localeCompare(a.date); });
    editions = editions.slice(0, ARCHIVE_LIMIT);

    var host = document.getElementById('editions');
    host.innerHTML = editions.map(renderEdition).join('');
    var articles = Array.prototype.slice.call(host.querySelectorAll('.briefing-edition'));
    articles.forEach(wireEdition);

    var select = document.getElementById('archiveSelect');
    var count = document.getElementById('archiveCount');
    articles.forEach(function (article, index) {
      var option = document.createElement('option');
      option.value = article.getAttribute('data-edition');
      option.textContent = article.getAttribute('data-label') + (index === 0 ? ' · 最新一期' : '');
      select.appendChild(option);
      article.hidden = index !== 0;
    });
    count.textContent = '最近 30 天 · 当前 ' + articles.length + ' 期';
    if (articles.length) select.value = articles[0].getAttribute('data-edition');

    select.addEventListener('change', function () {
      articles.forEach(function (article) {
        article.hidden = article.getAttribute('data-edition') !== select.value;
      });
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  }

  /* ---------- 数据加载 ---------- */

  function fail(msg) {
    document.getElementById('editions').innerHTML =
      '<p style="padding:60px 20px;text-align:center;color:#888">' + esc(msg) + '</p>';
  }

  if (window.__EDITIONS__) {
    mount(window.__EDITIONS__);
  } else {
    fetch('data/manifest.json').then(function (r) {
      if (!r.ok) throw new Error('manifest');
      return r.json();
    }).then(function (manifest) {
      var dates = (manifest.editions || []).slice(0, ARCHIVE_LIMIT);
      return Promise.all(dates.map(function (date) {
        return fetch('data/editions/' + date + '.json').then(function (r) {
          if (!r.ok) throw new Error(date);
          return r.json();
        });
      }));
    }).then(mount).catch(function () {
      fail('简报数据加载失败，请检查 data/ 目录是否完整，或使用单文件版本部署。');
    });
  }
})();
