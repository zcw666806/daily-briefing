#!/usr/bin/env python3
"""抓取国际行情，自动填充当日简报 JSON 的 market（国际 + 汇率）部分。

数据源（全部免费、无需 API key）：
  - 汇率 USD/CNY .... https://api.frankfurter.app/latest?from=USD&to=CNY
                       （欧洲央行每日牌价；注意：是离岸参考价，非中间价）
  - WTI / 黄金 / 白银 .. Yahoo Finance chart API（CL=F、GC=F、SI=F），
                       直接给出 regularMarketPrice（现价）与 chartPreviousClose（昨收），
                       涨跌幅 = (现价 - 昨收) / 昨收。
  - 国内金银 .......... 上金所官网 https://www.sge.com.cn/sjzx/mrhq_data?date=YYYY-MM-DD
                       Au99.99 收盘价（元/克）、Ag99.99 收盘价（元/千克÷1000→元/克），
                       附带官方涨跌幅；交易日每日更新，周末/节假日返回空表。

准确率铁律（2026-10-12 用户立规：不准的东西不如不做）：
  - 上金所无数据（空表/接口异常）时，从当日往前最多回溯 7 天取最近交易日；
    仍取不到 → 国内金银 value/change 全部填 "—"，换算差价同步 "—"；
  - 禁止沿用旧报价、禁止把"没有新数据"写成 0.00%。
  - 92 号汽油：发改委约 10 个工作日一调，沿用现价是正常属性，由 worker 按发改委通知手工维护，脚本不动。

抓不到的东西（脚本不动，留给你手动填）：
  - 中国区：92 号汽油（发改委调价口径）；
  - 所有新闻条目、洞察、待关注 —— 需要编辑判断，爬虫做不了。

用法：
    # 先用 new_day.py 建好当天的 JSON，再抓行情填进去
    python3 scripts/new_day.py 2026-09-29 --from 2026-09-28
    python3 scripts/fetch_market.py 2026-09-29

    # 国内金银默认走上金所自动抓取；如需手工覆盖（仅调试）：
    python3 scripts/fetch_market.py 2026-09-29 --china-gold 902.90 --china-silver 14.82
"""
import argparse
import datetime as dt
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


def fetch_sge_day(day: str):
    """取上金所某日行情。返回 (au9999收盘元/克, au涨跌幅%, ag9999收盘元/克, ag涨跌幅%)，
    空表/异常返回 None。列顺序：合约/开盘/收盘/最高/最低/涨跌/涨跌幅。"""
    url = f"https://www.sge.com.cn/sjzx/mrhq_data?date={day}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
    except Exception:
        return None
    out = {}
    for comment in re.findall(r"<!--(.*?)-->", raw, re.S):
        if "Au99.99" not in comment:
            continue
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", comment, re.S):
            cells = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip()
                     for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)]
            if cells and cells[0] in ("Au99.99", "Ag99.99") and len(cells) >= 7:
                try:
                    close = float(cells[2])
                except ValueError:
                    continue
                try:
                    chg = float(cells[6].replace("%", ""))
                except ValueError:
                    chg = None  # 涨跌幅缺失时只取价格
                out[cells[0]] = (close, chg)
        break
    if "Au99.99" not in out or "Ag99.99" not in out:
        return None
    au_close, au_chg = out["Au99.99"]
    ag_close_kg, ag_chg = out["Ag99.99"]
    return au_close, au_chg, ag_close_kg / 1000.0, ag_chg


def fetch_sge(day: str):
    """从 day 往前最多回溯 7 天取最近交易日。返回 (au, au_chg, ag, ag_chg, 实际报价日期)，取不到返回 None。"""
    d = dt.date.fromisoformat(day)
    for i in range(8):
        q = (d - dt.timedelta(days=i)).isoformat()
        r = fetch_sge_day(q)
        if r:
            return (*r, q)
    return None


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
    ap.add_argument("--china-gold", type=float, default=None, help="手工覆盖：国内黄金 元/克（默认走上金所自动抓取）")
    ap.add_argument("--china-silver", type=float, default=None, help="手工覆盖：国内白银 元/克（默认走上金所自动抓取）")
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

    # ---- 4. 国内金银（上金所自动抓取；--china-* 仅手工覆盖/调试） ----
    if args.china_gold is not None and args.china_silver is not None:
        au, ag = args.china_gold, args.china_silver
        au_chg = ag_chg = None
        qdate = "手工覆盖"
        print(f"国内金银使用手工覆盖值：Au {au} / Ag {ag}")
    else:
        sge = fetch_sge(args.day)
        if sge is None:
            # 熔断：无数据 → 显示"—"，禁止沿用旧价
            print("上金所 7 天内无数据，国内金银按熔断显示 —")
            au = ag = None
        else:
            au, au_chg, ag, ag_chg, qdate = sge
            print(f"上金所 {qdate}：Au99.99 收盘 {au:.2f}（{fmt_chg(au_chg)}）  Ag99.99 {ag:.2f}（{fmt_chg(ag_chg)}）")

    china = edition["market"]["china"]["items"]
    if au is None:
        for idx in (1, 2):
            china[idx]["value"] = "—"
            china[idx]["change"] = ""
            china[idx]["changeDir"] = ""
            china[idx]["dir"] = None
            china[idx]["sub"] = "暂无可验证报价"
    else:
        china[1].update({
            "label": "上金所 Au99.99 元/克",
            "value": f"{au:.2f}",
            "change": fmt_chg(au_chg) if au_chg is not None else "",
            "changeDir": direction(au_chg) if au_chg is not None else "",
            "dir": direction(au_chg) if au_chg is not None else None,
            "sub": f"上金所{qdate[5:].replace('-', '月')}日收盘价" if qdate != "手工覆盖" else "手工覆盖值",
        })
        china[2].update({
            "label": "上金所 Ag99.99 元/克",
            "value": f"{ag:.2f}",
            "change": fmt_chg(ag_chg) if ag_chg is not None else "",
            "changeDir": direction(ag_chg) if ag_chg is not None else "",
            "dir": direction(ag_chg) if ag_chg is not None else None,
            "sub": f"上金所{qdate[5:].replace('-', '月')}日收盘价" if qdate != "手工覆盖" else "手工覆盖值",
        })

    # ---- 5. 换算差价 ----
    fx_items = edition["market"]["fx"]["items"]
    if au is None:
        for item in fx_items:
            item["value"] = "—"
            item["dir"] = None
            item["sub"] = "国内暂无可验证报价"
    else:
        for item, usd_price, cn_price in zip(fx_items, [gold, silver], [au, ag]):
            converted = usd_price * fx / TROY_OZ
            basis = converted - cn_price
            item["value"] = f"{'+' if basis >= 0 else '−'}{abs(basis):.2f}"
            item["dir"] = direction(basis)
            item["sub"] = f"{converted:.2f} − {cn_price:.2f}"
            print(f"{item['label']}：{item['value']}（{item['sub']}）")

    path.write_text(json.dumps(edition, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已更新 {path}")


if __name__ == "__main__":
    main()
