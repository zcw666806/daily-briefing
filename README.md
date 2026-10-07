# 今日信息差 · 可部署源码

每天一期的中文信息差简报页面：报纸式排版，含行情快照（国际/中国/汇率三栏）、
分类筛选、精简阅读模式、三条洞察、待关注事项、核验边界，以及最近 30 期历史存档切换。

纯静态站点，无需数据库、无需后端，任何静态托管都能部署。

## 目录结构

```
daily-briefing-site/
├── index.html                  # 页面骨架（存档栏 + 内容容器）
├── assets/
│   ├── css/style.css           # 全部样式（浅色/深色自适应、响应式）
│   └── js/app.js               # 数据驱动渲染 + 筛选/存档/精简模式交互
├── data/
│   ├── manifest.json           # 期号清单（新日期追加到这里）
│   └── editions/
│       └── 2026-09-28.json     # 每一期的数据（示例为 9 月 28 日完整一期）
├── scripts/
│   ├── new_day.py              # 生成新一期数据骨架
│   └── build.py                # 构建 dist/（多文件版 / 单文件版）
├── dist/                       # 构建产物（部署时上传这个目录，或单文件版的一个 html）
└── .nojekyll                   # GitHub Pages 用
```

## 本地预览

```bash
cd daily-briefing-site
python3 -m http.server 8000
# 浏览器打开 http://localhost:8000
```

> 直接双击 `index.html` 打开会因浏览器安全限制读不到 `data/` 下的 JSON。
> 想双击即用，先构建单文件版（见下）。

## 每日更新流程（约 2 分钟）

```bash
# 1. 生成新一期骨架（以上一期为模板复制结构）
python3 scripts/new_day.py 2026-09-29 --from 2026-09-28

# 2. 用编辑器打开 data/editions/2026-09-29.json，填写：
#    行情数字、17 条新闻（标题/解读/来源链接/日期）、3 条洞察、
#    待关注事项、核验边界、页脚时间
#    - 标题里想高亮的词包上 <span class="mark">…</span>
#    - priority: true 的条目会在编号上显示红色，排在前面请手动排序
#    - caveats 数组放黄色警示小标签，如 ["仅为早盘，不是收盘数据"]

# 3. 本地刷新确认无误后重新部署（见下）
```

`manifest.json` 会由脚本自动更新，页面会自动把最新一期置顶，
历史存档保留最近 30 期，下拉框可切换查看往期。

### 行情数字可以自动抓（可选）

`scripts/fetch_market.py` 会从免费公开接口拉取国际行情并填进当日 JSON，
实测可用、无需 API key：

| 数据 | 接口 |
|---|---|
| 汇率 USD/CNY | `api.frankfurter.app`（欧洲央行每日牌价） |
| WTI 原油 / 黄金 / 白银现价与涨跌幅 | Yahoo Finance（`CL=F` / `GC=F` / `SI=F`，自带昨收盘价） |

```bash
python3 scripts/new_day.py 2026-09-29 --from 2026-09-28
python3 scripts/fetch_market.py 2026-09-29 --china-gold 912.22 --china-silver 14.13
```

脚本逻辑（`scripts/fetch_market.py`，约 100 行，可直接读）：
1. `fetch_fx()` / `fetch_yahoo(symbol)` 分别请求上面两个接口，拿到现价、昨收、汇率；
2. 涨跌幅 =（现价 − 昨收）/ 昨收，正负决定红绿（`up`/`down`）与 `+`/`−` 符号；
3. 把结果写进 `market.intl`（国际三栏）与 `market.fx`（汇率数字、换算公式）；
4. 若传入 `--china-gold/--china-silver`，按页面公式
   `国际价 × 汇率 ÷ 31.1035 − 中国销售价` 自动算出"换算差价"栏。

注意两点：一是汇率用的是欧洲央行牌价（非人民币中间价），页面已注明"仅用于差价对照"；
二是**中国区实价（水贝金银、92 号汽油）没有稳定的公开接口**，仍需手动填写，
新闻条目与洞察更需要人工/ AI 编辑判断——这也是线上版每天由 AI 研究员通读全网后撰写、
而非爬虫抓取的原因。

## 数据字段速查

| 字段 | 说明 |
|---|---|
| `date` / `label` | 期号 `2026-09-29` / 下拉框显示 `2026年9月29日`（"· 最新一期"由程序自动追加） |
| `editionLine` | 版头小字，如 `2026.09.29 · TUESDAY EDITION` |
| `headlineHtml` | 大标题，支持 `<br>` 换行 |
| `dek` | 标题下的一句话导语 |
| `stamp` | 右上角时间戳 `{time, note}` |
| `market.intl/china/fx` | 三栏行情：国际（美元）/ 中国（人民币实价）/ 汇率与换算差价 |
| `insights` | 左侧三条洞察 `{num, title, text}` |
| `watch` | "接下来盯什么" `{date, event}` |
| `categories` | 四个板块，每板块 `stories` 数组；`filterName` 是筛选按钮文字 |
| `boundary` | "核验边界" 说明条（支持 HTML） |
| `footer` | 页脚左右两行文字 |

## 部署方式

任选其一。页面无构建步骤，源码即产物。

### A. GitHub Pages（免费）

```bash
cd daily-briefing-site
git init && git add . && git commit -m "daily briefing"
# 在 GitHub 新建仓库后：
git remote add origin git@github.com:<你>/<仓库>.git
git push -u origin main
```

仓库 → Settings → Pages → Deploy from branch → `main` / `/ (root)`，
`.nojekyll` 已内置，推送后约 1 分钟生效，地址形如
`https://<你>.github.io/<仓库>/`。

### B. Vercel / Netlify / Cloudflare Pages（免费）

- **Vercel**：`vercel --prod` 或网页端 Import 仓库，框架选 Other，无需构建命令，输出目录填 `.`（项目根）。
- **Netlify**：网页端拖拽整个项目文件夹到 Netlify Drop，或连接仓库，Build command 留空，Publish directory 填 `.`。
- **Cloudflare Pages**：连接仓库，构建命令留空，输出目录填 `/`。

### C. 自己的服务器（Nginx / 宝塔）

```bash
# 把项目根目录所有文件拷到网站根目录即可，例如：
scp -r daily-briefing-site/* user@server:/www/wwwroot/briefing/
```

Nginx 示例：

```nginx
server {
    listen 80;
    server_name briefing.example.com;
    root /www/wwwroot/briefing;
    index index.html;
    location / { try_files $uri $uri/ =404; }
}
```

宝塔面板：新建站点 → 把文件上传到站点目录 → 直接访问域名。

### D. 单文件版（只能传一个 html 的场景）

```bash
python3 scripts/build.py --single-file
# 得到 dist/index.html（约几十 KB，内联了样式、脚本和全部 30 期数据）
```

把这一个文件上传到任何对象存储 / 虚拟主机 / 甚至微信文件传输助手发给自己，
双击或直接访问就能打开，离线也可看（在线时字体更美观）。

## 自定义

- **改标题/口号**：`index.html` 里 `<title>`；版头文字在每期 JSON 的 `editionLine/headlineHtml/dek`。
- **改配色**：`assets/css/style.css` 顶部 `:root` 变量（`--accent` 是主绿色，`--signal` 是警示红），深色模式在 `@media (prefers-color-scheme: dark)` 里。
- **增减板块**：在 JSON 的 `categories` 里加/删对象即可，筛选按钮自动生成；`id` 保持英文唯一。
- **改存档保留期数**：`assets/js/app.js` 顶部 `ARCHIVE_LIMIT`（默认 30）。
- **换字体**：`index.html` 的 Google Fonts 链接可替换；离线环境会自动降级为系统字体。

## 说明

- 本站点的示例数据为 2026 年 9 月 28 日一期的真实简报内容，供排版参考；
  正式使用前请按"每日更新流程"替换为你自己的内容。
- 来源链接请保留原出处，转载新闻内容时注意版权与平台规范。
