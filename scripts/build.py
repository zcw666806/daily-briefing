#!/usr/bin/env python3
"""构建可部署版本。

用法：
    python3 scripts/build.py                  # 构建 dist/ 多文件版本（index.html + assets + data）
    python3 scripts/build.py --single-file    # 构建 dist/index.html 单文件版本（内联全部资源与数据）

单文件版本适合只能上传一个 HTML 文件的托管方式（如对象存储直传、某些 CMS），
双击即可在浏览器打开，无需本地服务器。
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"


def load_editions(limit: int = 30):
    manifest = json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))
    dates = sorted(manifest.get("editions", []), reverse=True)[:limit]
    editions = []
    for day in dates:
        p = ROOT / "data" / "editions" / f"{day}.json"
        if not p.exists():
            print(f"警告：缺少 {p}，已跳过", file=sys.stderr)
            continue
        editions.append(json.loads(p.read_text(encoding="utf-8")))
    return editions


def build_multi():
    if DIST.exists():
        shutil.rmtree(DIST)
    for src in ["index.html", "assets", "data", ".nojekyll"]:
        s = ROOT / src
        d = DIST / src
        if s.is_dir():
            shutil.copytree(s, d)
        elif s.exists():
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(s, d)
    print(f"多文件版本已构建：{DIST}/")


def build_single():
    editions = load_editions()
    css = (ROOT / "assets" / "css" / "style.css").read_text(encoding="utf-8")
    js = (ROOT / "assets" / "js" / "app.js").read_text(encoding="utf-8")
    data_json = json.dumps(editions, ensure_ascii=False)
    # 防止 </script> 出现在数据中破坏页面
    data_json = data_json.replace("</script", "<\\/script")

    shell = (ROOT / "index.html").read_text(encoding="utf-8")
    shell = shell.replace(
        '<link rel="stylesheet" href="assets/css/style.css" />',
        "<style>\n" + css + "\n</style>",
    )
    shell = shell.replace(
        '<script src="assets/js/app.js"></script>',
        '<script>window.__EDITIONS__ = ' + data_json + ";</script>\n  <script>\n" + js + "\n</script>",
    )
    # 去掉多余空白（可选的轻量压缩）
    shell = re.sub(r"[ \t]+\n", "\n", shell)

    DIST.mkdir(parents=True, exist_ok=True)
    out = DIST / "index.html"
    out.write_text(shell, encoding="utf-8")
    print(f"单文件版本已构建：{out}（{out.stat().st_size / 1024:.1f} KB，含 {len(editions)} 期）")


def main():
    ap = argparse.ArgumentParser(description="构建可部署版本")
    ap.add_argument("--single-file", action="store_true", help="构建单文件版本")
    args = ap.parse_args()
    if args.single_file:
        build_single()
    else:
        build_multi()


if __name__ == "__main__":
    main()
