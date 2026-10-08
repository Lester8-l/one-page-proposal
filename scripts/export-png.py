#!/usr/bin/env python3
"""
把方案卡 HTML 逐張匯出成 1080x1350 PNG（WhatsApp 發送用）。

Usage:
    python export-png.py plan.html [--out <dir>] [--chrome <chrome.exe>]
                                   [--width 1080] [--height 1350]

How it works:
    HTML 裡每張卡是一個 <div class="card" data-filename="P1-需求對照">。
    這支腳本為每張卡寫一個只顯示該卡的臨時頁（其餘用 CSS 隱藏），
    再用 headless Chrome 截圖成 1080x1350。輸出檔名取自 data-filename。

    為什麼不用瀏覽器裡的 html2canvas？
    兩者都可以。html2canvas 要手動按一下、而且要等 CDN 載入；
    這支腳本是給 agent / CI 用的，直接把檔案寫到磁碟，零依賴。

Requirements:
    headless Chrome 或 Edge，會自動偵測常見路徑，可用 --chrome 覆寫。
"""
import argparse
import pathlib
import re
import shutil
import subprocess
import sys

CARD_RE = re.compile(r'data-filename="([^"]+)"')

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
]


def find_browser(explicit=None):
    if explicit:
        return explicit
    for p in CHROME_CANDIDATES:
        if pathlib.Path(p).exists():
            return p
    for name in ("chrome", "google-chrome", "chromium", "msedge"):
        found = shutil.which(name)
        if found:
            return found
    home = pathlib.Path.home() / ".agent-browser" / "browsers"
    if home.exists():
        for exe in home.glob("chrome-*/chrome.exe"):
            return str(exe)
    raise SystemExit("找不到 Chrome / Edge，請用 --chrome <path> 指定。")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("deck")
    ap.add_argument("--out", default=None, help="輸出目錄（預設為 HTML 同層的 out/）")
    ap.add_argument("--chrome", default=None)
    ap.add_argument("--width", type=int, default=1080)
    ap.add_argument("--height", type=int, default=1350)
    args = ap.parse_args()

    deck_path = pathlib.Path(args.deck).resolve()
    if not deck_path.exists():
        raise SystemExit(f"檔案不存在：{deck_path}")
    out_dir = pathlib.Path(args.out).resolve() if args.out else deck_path.parent / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir = out_dir / "_tmp_pages"
    tmp_dir.mkdir(exist_ok=True)

    browser = find_browser(args.chrome)
    html = deck_path.read_text(encoding="utf-8")
    names = CARD_RE.findall(html)
    if not names:
        raise SystemExit("找不到任何 data-filename 卡片，請確認 HTML 結構。")

    base_tag = f'<base href="{deck_path.parent.as_uri()}/">'
    if "<head>" in html:
        html = html.replace("<head>", "<head>\n" + base_tag, 1)
    else:
        html = base_tag + html

    print(f"browser : {browser}")
    print(f"size    : {args.width}x{args.height}")
    print(f"cards   : {len(names)} -> {names}")

    failures = []
    for i, name in enumerate(names, start=1):
        extra = f"""<style>
  body{{padding:0 !important;background:#FFFDF8 !important;}}
  .toolbar,.controls,.btn,.btn-dl,.btn-edit,.card-label,.ovf,[data-noexport]{{display:none !important;}}
  .deck{{gap:0 !important;max-width:none !important;margin:0 !important;}}
  .card-wrap:not(:nth-child({i})){{display:none !important;}}
  .card-wrap{{gap:0 !important;}}
</style>
</head>"""
        page = tmp_dir / f"{i:02d}.html"
        page.write_text(html.replace("</head>", extra, 1), encoding="utf-8")
        png = out_dir / f"{name}.png"
        cmd = [
            browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
            "--force-device-scale-factor=1",
            f"--window-size={args.width},{args.height}",
            "--virtual-time-budget=12000",
            f"--screenshot={png}", page.as_uri(),
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)
        ok = png.exists() and png.stat().st_size > 2000
        size_kb = png.stat().st_size // 1024 if png.exists() else 0
        print(f"  {'OK  ' if ok else 'FAIL'} {name}.png  {size_kb}KB")
        if not ok:
            failures.append(name)
            if r.stderr:
                print("       ", r.stderr.strip()[-200:])

    shutil.rmtree(tmp_dir, ignore_errors=True)
    print(f"\n完成：{len(names) - len(failures)}/{len(names)} 張 -> {out_dir}")
    if failures:
        print("失敗：", failures)
        sys.exit(1)


if __name__ == "__main__":
    main()
