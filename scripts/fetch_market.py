#!/usr/bin/env python3
"""抓取国际行情，自动填充当日简报 JSON 的 market（国际 + 汇率）部分。

数据源（全部免费、无需 API key）：
  - 汇率 USD/CNY .... https://api.frankfurter.app/latest?from=USD&to=CNY
                       （欧洲央行每日牌价；注意：是离岸参考价，非中间价）
  - WTI / 黄金 / 白银 .. Yahoo Finance chart API（CL=F、GC=F、SI=F），
                       直接给出 regularMarketPrice（现价）与 chartPreviousClose（昨收），
                       涨跌幅 = (现价 - 昨收) / 昨收。

准确率铁律（2026-10-12 用户立规：不准的东西不如不做）：
  - 国内金银（水贝口径）优先从深圳本地宝"水贝今日金价（每日更新）"
    （https://sz.bendibao.com/news/2024315/970347.htm，固定地址、静态表格、每日更新）
    自动抓取；仅当表头日期"水贝金价（M月D日"与当天一致时采用，否则视为无数据；
  - 无当日数据且未手工传入 → value/change 显示"—"，换算差价同步"—"；
  - 禁止沿用旧报价、禁止把"没有新数据"写成 0.00%。
  - 92 号汽油：发改委约 10 个工作日一调，沿用现价是正常属性，由 worker 按发改委通知手工维护，脚本不动。

抓不到的东西（脚本不动，留给你手动填）：
  - 中国区：水贝金银当日报价、92 号汽油；
  - 所有新闻条目、洞察、待关注 —— 需要编辑判断，爬虫做不了。

用法：
    # 先用 new_day.py 建好当天的 JSON，再抓行情填进去
    python3 scripts/new_day.py 2026-09-29 --from 2026-09-28
    python3 scripts/fetch_market.py 2026-09-29

    # worker 搜到当日水贝报价后传入，自动算出"换算差价"栏；不传则按熔断显示"—"
    python3 scripts/fetch_market.py 2026-09-29 --china-gold 1061.00 --china-silver 13.84
"""
import argparse
import html
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TROY_OZ = 31.1035  # 金衡盎司 → 克


def get_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.load(resp)


def get_html(url: str) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=25) as resp:
        return resp.read().decode("utf-8", errors="ignore")


BENDIBAO_URL = "https://sz.bendibao.com/news/2024315/970347.htm"  # 深圳本地宝"水贝今日金价（每日更新）"，固定地址每日更新


def fetch_bendibao():
    """抓深圳本地宝水贝金价表。返回 (MM-DD日期, 首饰金元/克, 白银元/克)，失败返回 None。
    表格为静态 HTML；日期取自表头"水贝金价（M月D日"。"""
    try:
        raw = get_html(BENDIBAO_URL)
    except Exception:
        return None
    m = re.search(r"水贝金价（(\d{1,2})月(\d{1,2})", raw)
    if not m:
        return None
    date_str = f"{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    out = {}
    for tb in re.findall(r"<table[^>]*>(.*?)</table>", raw, re.S):
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", tb, re.S):
            cells = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip()
                     for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)]
            cells = [c for c in cells if c]
            if len(cells) >= 2 and cells[0] in ("首饰金", "白银"):
                mm = re.search(r"([\d.]+)\s*元/克", cells[1])
                if mm:
                    out[cells[0]] = float(mm.group(1))
        if "首饰金" in out and "白银" in out:
            break
    if "首饰金" not in out or "白银" not in out:
        return None
    return date_str, out["首饰金"], out["白银"]


def fetch_fx() -> tuple[float, str]:
    """返回 (USD/CNY, 牌价日期)。"""
    data = get_json("https://api.frankfurter.app/latest?from=USD&to=CNY")
    return float(data["rates"]["CNY"]), data.get("date", "")


def fetch_yahoo(symbol: str) -> tuple[float, float]:
    """返回 (现价, 涨跌幅%)。"""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5d"
    meta = get_json(url)["chart"]["result"][0]["meta"]
    price, prev = float(meta["regularMarketPrice"]), float(meta["chartPreviousClose"])
    return price, (price - prev) / prev * 100.0


def fmt_price(v: float) -> str:
    return f"{v:,.2f}"


def fmt_chg(c: float) -> str:
    # 页面风格：上涨 "+"，下跌用 "−"（U+2212）
    return f"{'+' if c >= 0 else '−'}{abs(c):.2f}%"


def direction(c: float) -> str:
    return "up" if c >= 0 else "down"


def main() -> None:
    ap = argparse.ArgumentParser(description="抓取国际行情并更新当日 JSON")
    ap.add_argument("day", help="日期，格式 YYYY-MM-DD（需已存在 data/editions/<日期>.json）")
    ap.add_argument("--china-gold", type=float, default=None, help="当日水贝首饰金挂牌价 元/克（无当日可验证报价时不传，按熔断显示—）")
    ap.add_argument("--china-silver", type=float, default=None, help="当日水贝白银批发价 元/克（无当日可验证报价时不传，按熔断显示—）")
    args = ap.parse_args()

    path = ROOT / "data" / "editions" / f"{args.day}.json"
    if not path.exists():
        sys.exit(f"找不到 {path}，请先运行 python3 scripts/new_day.py {args.day}")
    edition = json.loads(path.read_text(encoding="utf-8"))

    # ---- 1. 抓数 ----
    fx, fx_date = fetch_fx()
    wti, wti_chg = fetch_yahoo("CL=F")
    gold, gold_chg = fetch_yahoo("GC=F")
    silver, silver_chg = fetch_yahoo("SI=F")
    print(f"汇率 USD/CNY = {fx:.4f}（牌价日期 {fx_date}）")
    print(f"WTI = {wti:.2f}（{fmt_chg(wti_chg)}）  黄金 = {gold:.2f}（{fmt_chg(gold_chg)}）  白银 = {silver:.2f}（{fmt_chg(silver_chg)}）")

    # ---- 2. 填国际区 ----
    intl = edition["market"]["intl"]["items"]
    for item, (price, chg) in zip(intl, [(wti, wti_chg), (gold, gold_chg), (silver, silver_chg)]):
        item["value"] = fmt_price(price)
        item["dir"] = direction(chg)
        item["change"] = fmt_chg(chg)
        item["changeDir"] = direction(chg)

    # ---- 3. 填汇率区 ----
    fx_block = edition["market"]["fx"]
    fx_block["noteHtml"] = re.sub(
        r"1 美元 = [\d.]+ 元人民币",
        f"1 美元 = {fx:.3f} 元人民币",
        fx_block["noteHtml"],
    )
    fx_block["formula"] = f"国际价 × {fx:.3f} ÷ {TROY_OZ} − 中国销售价"

    # ---- 4. 国内金银（优先级：深圳本地宝每日更新 > --china-* 手工传入 > 熔断"—"） ----
    china = edition["market"]["china"]["items"]
    fx_items = edition["market"]["fx"]["items"]
    au = ag = None
    au_src = ""
    bdb = fetch_bendibao()
    if bdb and bdb[0] == args.day[5:]:
        _, au, ag = bdb
        au_src = f"深圳本地宝{bdb[0].replace('-', '月')}日"
        print(f"本地宝 {bdb[0]}：首饰金 {au:.2f} / 白银 {ag:.2f}")
    elif args.china_gold is not None and args.china_silver is not None:
        au, ag = args.china_gold, args.china_silver
        au_src = "手工传入"
        print(f"国内金银使用手工传入值：Au {au} / Ag {ag}")
    else:
        print("本地宝非今日数据且未手工传入，按熔断显示 —（禁止沿用旧价）")
    if au is None:
        for idx in (1, 2):
            china[idx]["value"] = "—"
            china[idx]["change"] = ""
            china[idx]["changeDir"] = None
            china[idx]["dir"] = None
        for item in fx_items:
            item["value"] = "—"
            item["dir"] = None
            item["sub"] = "国内暂无可验证报价"
    else:
        # 涨跌幅按昨日 JSON 的真实数字计算（规则见任务指令）
        for idx, price in ((1, au), (2, ag)):
            china[idx]["value"] = f"{price:.2f}"
            china[idx]["label"] = ("水贝首饰金挂牌价 元/克" if idx == 1
                                   else "水贝白银 元/克")
            china[idx]["sub"] = au_src
        for item, usd_price, cn_price in zip(fx_items, [gold, silver], [au, ag]):
            converted = usd_price * fx / TROY_OZ
            basis = converted - cn_price  # 国际折算 − 国内；为负表示国内贵
            # 页面显示取反：+红色=国内贵，−绿色=国内便宜（用户锁定口径）
            item["value"] = f"{'+' if basis <= 0 else '−'}{abs(basis):.2f}"
            item["dir"] = "up" if basis <= 0 else "down"
            item["sub"] = f"{converted:.2f} − {cn_price:.2f}"
            print(f"{item['label']}：{item['value']}（{item['sub']}）")

    path.write_text(json.dumps(edition, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已更新 {path}")


if __name__ == "__main__":
    main()
