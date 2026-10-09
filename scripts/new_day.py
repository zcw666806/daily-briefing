#!/usr/bin/env python3
"""新建一期简报的数据骨架。

用法：
    python3 scripts/new_day.py 2026-09-29
    python3 scripts/new_day.py 2026-09-29 --from 2026-09-28   # 以上一期为模板复制结构

脚本会在 data/editions/<日期>.json 生成骨架，并自动更新 data/manifest.json。
之后只需用编辑器填写各字段内容，刷新页面即可看到新的一期。
"""
import argparse
import json
import re
import sys
from datetime import date as date_cls
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EDITIONS = ROOT / "data" / "editions"
MANIFEST = ROOT / "data" / "manifest.json"

WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def skeleton(day: str) -> dict:
    d = date_cls.fromisoformat(day)
    weekday = WEEKDAY_CN[d.weekday()]
    return {
        "date": day,
        "label": f"{d.year}年{d.month}月{d.day}日",
        "editionLine": f"{d.year}.{d.month:02d}.{d.day:02d} · {weekday.upper()} EDITION",
        "headlineHtml": "今天真正值得知道的<br>N 件事",
        "dek": "一句话概括今天的整体基调（政策 / 地缘 / 市场 / 科技）。",
        "stamp": {"time": "上海时间 HH:MM", "note": "早间快照 · 市场未收盘"},
        "market": {
            "intl": {
                "title": "国际市场",
                "note": "原始行情报价",
                "items": [
                    {"value": "0.00", "dir": "up", "unit": "WTI 美元/桶", "change": "+0.00%", "changeDir": "up"},
                    {"value": "0.00", "dir": "up", "unit": "现货黄金 美元/盎司", "change": "+0.00%", "changeDir": "up"},
                    {"value": "0.00", "dir": "down", "unit": "现货白银 美元/盎司", "change": "−0.00%", "changeDir": "down"},
                ],
            },
            "china": {
                "title": "中国市场",
                "noteHtml": "金银为独立人民币报价，非汇率换算",
                "items": [
                    {"value": "约 0.00", "dir": None, "label": "国内 92 号汽油 元/升（各地略有差异）", "change": "+0.00 元/升", "changeDir": "up", "sub": "调价说明"},
                    {"value": "0.00", "dir": "down", "label": "水贝黄金销售价 元/克", "change": "−0.00%", "changeDir": "down", "sub": "回收价 0.00 元/克"},
                    {"value": "0.00", "dir": "down", "label": "水贝白银销售价 元/克", "change": "−0.00%", "changeDir": "down", "sub": "回收价 0.00 元/克"},
                ],
            },
            "fx": {
                "title": "当日汇率",
                "noteHtml": "1 美元 = 0.000 元人民币 · 仅用于下方差价对照",
                "formulaLabel": "换算口径",
                "formula": "国际价 × 汇率 ÷ 31.1035 − 中国销售价",
                "formulaNote": "计算口径为国际折算价减中国价，页面显示时取反：+红色表示国内比国际贵，−绿色表示国内比国际便宜；国际与国内报价各自保持原始口径",
                "items": [
                    {"label": "黄金差价 元/克", "value": "+0.00", "dir": "up", "sub": "0.00 − 0.00"},
                    {"label": "白银差价 元/克", "value": "−0.00", "dir": "down", "sub": "0.00 − 0.00"},
                ],
            },
        },
        "insights": [
            {"num": "01 / 主题", "title": "洞察标题", "text": "一句话洞察正文。"},
            {"num": "02 / 主题", "title": "洞察标题", "text": "一句话洞察正文。"},
            {"num": "03 / 主题", "title": "洞察标题", "text": "一句话洞察正文。"},
        ],
        "watch": [
            {"date": "MM月DD日", "event": "待关注事件"},
        ],
        "categories": [
            {
                "id": "china", "filterName": "中国", "title": "中国 · 政策与经济",
                "stories": [
                    {
                        "num": "01", "priority": True,
                        "titleHtml": "<span class=\"mark\">关键词高亮</span>，标题其余部分",
                        "why": "为什么重要：一句话说清影响。",
                        "sources": [{"name": "来源媒体", "url": "https://example.com"}],
                        "date": "M月D日", "caveats": [],
                    },
                ],
            },
            {"id": "world", "filterName": "国际", "title": "国际 · 地缘与事件", "stories": []},
            {"id": "tech", "filterName": "科技", "title": "科技 · AI 与产业", "stories": []},
            {"id": "market", "filterName": "市场", "title": "财经 · 市场与公司", "stories": []},
        ],
        "boundary": ["<strong>核验边界示例。</strong> 数据口径、未收录传闻等说明写在这里。"],
        "footer": {
            "left": "简报检索窗口：XXXX年X月X日—X日 · 上海时区",
            "right": "资料截至：XXXX年X月X日 HH:MM · 点击来源可查看原文",
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="新建一期简报数据骨架")
    ap.add_argument("day", help="日期，格式 YYYY-MM-DD")
    ap.add_argument("--from", dest="from_day", default=None, help="以哪一期为模板复制结构")
    args = ap.parse_args()

    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.day):
        sys.exit("日期格式应为 YYYY-MM-DD，例如 2026-09-29")
    target = EDITIONS / f"{args.day}.json"
    if target.exists():
        sys.exit(f"已存在：{target}，请直接编辑它")

    if args.from_day:
        src = EDITIONS / f"{args.from_day}.json"
        if not src.exists():
            sys.exit(f"模板不存在：{src}")
        data = json.loads(src.read_text(encoding="utf-8"))
        # 保留结构，清空内容字段
        data["date"] = args.day
        d = date_cls.fromisoformat(args.day)
        data["label"] = f"{d.year}年{d.month}月{d.day}日"
        data["editionLine"] = f"{d.year}.{d.month:02d}.{d.day:02d} · {WEEKDAY_CN[d.weekday()].upper()} EDITION"
    else:
        data = skeleton(args.day)

    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if args.day not in manifest["editions"]:
        manifest["editions"].append(args.day)
        manifest["editions"].sort(reverse=True)
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"已生成 {target}")
    print("已更新 data/manifest.json")


if __name__ == "__main__":
    main()
