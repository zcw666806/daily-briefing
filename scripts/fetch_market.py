#!/usr/bin/env python3
"""抓取国际行情，自动填充当日简报 JSON 的 market（国际 + 汇率）部分。

数据源（全部免费、无需 API key）：
  - 汇率 USD/CNY .... https://api.frankfurter.app/latest?from=USD&to=CNY
                       （欧洲央行每日牌价；注意：是离岸参考价，非中间价）
  - WTI / 黄金 / 白银 .. Yahoo Finance chart API（CL=F、GC=F、SI=F），
                       直接给出 regularMarketPrice（现价）与 chartPreviousClose（昨收），
                       涨跌幅 = (现价 - 昨收) / 昨收。

抓不到的东西（脚本不动，留给你手动填）：
  - 中国区：水贝金银实价、92 号汽油 —— 国内没有稳定的公开行情接口；
  - 所有新闻条目、洞察、待关注 —— 需要编辑判断，爬虫做不了。

用法：
    # 先用 new_day.py 建好当天的 JSON，再抓行情填进去
    python3 scripts/new_day.py 2026-09-29 --from 2026-09-28
    python3 scripts/fetch_market.py 2026-09-29

    # 如果已知中国区实价，一并传入可自动算出“换算差价”栏
    python3 scripts/fetch_market.py 2026-09-29 --china-gold 912.22 --china-silver 14.13
"""
import argparse
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
    ap.add_argument("--china-gold", type=float, default=None, help="水贝黄金销售价 元/克")
    ap.add_argument("--china-silver", type=float, default=None, help="水贝白银销售价 元/克")
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

    # ---- 4. 换算差价（需要中国区实价） ----
    if args.china_gold is not None and args.china_silver is not None:
        for item, usd_price, cn_price in zip(
            fx_block["items"], [gold, silver], [args.china_gold, args.china_silver]
        ):
            converted = usd_price * fx / TROY_OZ
            basis = converted - cn_price
            item["value"] = f"{'+' if basis >= 0 else '−'}{abs(basis):.2f}"
            item["dir"] = direction(basis)
            item["sub"] = f"{converted:.2f} − {cn_price:.2f}"
            print(f"{item['label']}：{item['value']}（{item['sub']}）")
    else:
        print("未传入 --china-gold/--china-silver，换算差价栏保持原值（请手动填写）。")

    path.write_text(json.dumps(edition, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已更新 {path}")


if __name__ == "__main__":
    main()
