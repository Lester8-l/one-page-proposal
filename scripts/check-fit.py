#!/usr/bin/env python3
"""
檢查方案卡的內容有沒有「裝不下」（被 overflow:hidden 靜默裁切）。

Usage:
    python check-fit.py plan.html
    python check-fit.py plan.html --chrome "C:\\...\\chrome.exe"

原理：
    headless Chrome 開臨時頁，注入 JS 讀每張卡 .frame 的
    scrollHeight 與 clientHeight。scrollHeight > clientHeight 就是溢出。

    為什麼要量而不是看圖？溢出被裁掉的往往是最後一行的下緣或卡片底部，
    肉眼在縮圖上幾乎看不出來——但發到 WhatsApp 客人一眼就看到斷字。
    flex 版面在空間不足時不會壓扁內容（min-height:auto 擋著），
    所以溢出幾乎都會如實反映成 scrollHeight 的差值。

退出碼：任何一張溢出 → 1；正常 → 0。
"""
import argparse
import html as html_mod
import json
import pathlib
import re
import shutil
import subprocess
import sys

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

PROBE = r"""
(function(){
  function finish(p){ var e=document.createElement('pre'); e.id='__fit'; e.textContent=JSON.stringify(p); e.style.display='none'; document.body.appendChild(e); }
  function run(){
    var rows=[];
    document.querySelectorAll('.card').forEach(function(c){
      var f=c.querySelector('.frame');
      if(!f) return;
      var blocks=[...f.querySelectorAll('.blk')].map(function(b){
        return { cls:(b.className||'').replace('blk','').trim(), h:Math.round(b.getBoundingClientRect().height) };
      });
      rows.push({
        f: c.dataset.filename || 'card',
        sh: f.scrollHeight,
        ch: f.clientHeight,
        over: f.scrollHeight - f.clientHeight,
        blocks: blocks
      });
    });
    finish(rows);
  }
  if(document.fonts&&document.fonts.ready){ document.fonts.ready.then(function(){setTimeout(run,1400);}); }
  else { setTimeout(run,2800); }
})();
"""


def find_browser(explicit=None):
    if explicit:
        return explicit
    for p in CHROME_CANDIDATES:
        if pathlib.Path(p).exists():
            return p
    for name in ("chrome", "google-chrome", "chromium", "msedge"):
        f = shutil.which(name)
        if f:
            return f
    home = pathlib.Path.home() / ".agent-browser" / "browsers"
    if home.exists():
        for exe in home.glob("chrome-*/chrome.exe"):
            return str(exe)
    raise SystemExit("找不到 Chrome / Edge，請用 --chrome <path> 指定。")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("--chrome", default=None)
    ap.add_argument("--wait", type=int, default=18000)
    ap.add_argument("--tolerance", type=int, default=2, help="容許的溢出像素")
    args = ap.parse_args()

    src = pathlib.Path(args.html).resolve()
    if not src.exists():
        raise SystemExit(f"檔案不存在：{src}")
    browser = find_browser(args.chrome)

    html = src.read_text(encoding="utf-8")
    base_tag = f'<base href="{src.parent.as_uri()}/">'
    html = html.replace("<head>", "<head>\n" + base_tag, 1) if "<head>" in html else base_tag + html
    html = html.replace("</body>", "<script>" + PROBE + "</script></body>", 1)

    tmp = src.parent / "_fit_probe.html"
    tmp.write_text(html, encoding="utf-8")
    try:
        r = subprocess.run([
            browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
            "--window-size=1200,2200", f"--virtual-time-budget={args.wait}",
            "--dump-dom", tmp.as_uri(),
        ], capture_output=True, text=True)
        dom = r.stdout or ""
    finally:
        tmp.unlink(missing_ok=True)

    m = re.search(r'<pre id="__fit"[^>]*>(.*?)</pre>', dom, re.S)
    if not m:
        print("⚠ 取不到量測結果（頁面可能沒載入完）")
        sys.exit(2)
    rows = json.loads(html_mod.unescape(m.group(1)))
    if not rows:
        print("⚠ 找不到 .card / .frame 結構，請確認這是本 skill 產出的 HTML。")
        sys.exit(2)

    print(f"{'卡片':<20}{'內容高':>8}{'可用高':>8}{'溢出':>8}{'狀態':>10}")
    print("-" * 56)
    bad = []
    for r in rows:
        over = r["over"]
        if over > args.tolerance:
            status, note = "✗ 溢出", f"多出 {over}px"
            bad.append(r["f"])
        elif over < -120:
            status, note = "△ 偏空", f"尚餘 {-over}px 可放內容"
        else:
            status = "✓"
            note = ""
        print(f"{r['f']:<20}{r['sh']:>8}{r['ch']:>8}{over:>8}{status:>10} {note}")
        if r.get("blocks"):
            print("      區塊高度：" + " / ".join(f"{b['cls']} {b['h']}" for b in r["blocks"]))

    print()
    if bad:
        print(f"✗ {len(bad)} 張溢出，會被 overflow:hidden 裁掉：{bad}")
        print("  修法：減字、精簡要點至三條、或把該區塊字級降一級。")
        sys.exit(1)
    print("✓ 全部裝得下，沒有裁切。")


if __name__ == "__main__":
    main()
