#!/usr/bin/env python3
"""
保險合規守門員：掃描一頁紙方案 HTML 的**可見文字**，攔截違規表述。

Usage:
    python check-compliance.py plan.html
    python check-compliance.py plan.html --strict     # 連 WARN 也視為失敗

為什麼要獨立一支腳本：
    保險銷售材料的違規多半不在「排版」，而在「用字」——
    一句「穩賺」或一個沒標示「非保證」的回報數字，
    輕則要重印，重則涉及監管問題。用眼睛掃很容易漏，
    用機器掃是零成本。

退出碼：有 ERROR → 1；只有 WARN → 0（除非 --strict）；乾淨 → 0。
"""
import argparse
import html as html_mod
import pathlib
import re
import sys

# ── 一律禁止的詞（無條件）──
BANNED = [
    (r"穩賺|稳赚",            "承諾獲利，屬違規表述"),
    (r"必賺|一定賺|保證賺|包賺", "承諾獲利，屬違規表述"),
    (r"零風險|無風險|冇風險|絕無風險|零风险", "「零風險」不可用於保險產品"),
    (r"像定存|似定存|等同定存|如同定存",      "不得與銀行存款混淆"),
    (r"等同儲蓄|儲蓄替代品|取代儲蓄",          "不得宣稱為儲蓄替代品"),
    (r"包賠|全賠|100%\s*賠|必定賠|一定賠|必賠", "理賠不得寫成必然結果"),
    (r"保本保息|保證保本|保本增值",            "不得承諾保本（保證現金價值須用保單術語）"),
    (r"唔會蝕|不會虧損|穩陣必勝",              "不得承諾不虧損"),
    (r"最好|第一|全港最|市場上唯一",            "不得作絕對化或唯一性宣稱"),
]

# ── 有條件的規則：(必須出現的觸發詞, 同卡必須存在的字樣, 說明) ──
CONDITIONAL = [
    (
        r"預期(回報|收益|現金價值|價值|紅利|派息)|潛在(回報|收益)|非保證紅利|預期利益",
        r"非保證",
        "出現預期／潛在利益，但沒有標示「非保證」",
    ),
    (
        r"回報率|派息率|年化|過往表現|歷史回報|過去.*回報",
        r"過往(表現)?不代表(將來|未來)",
        "出現回報率／過往數據，但沒有標註「過往表現不代表將來」",
    ),
    (
        r"保證(回報|收益|利潤|增長|升值|賺)|保證.*回報",
        None,   # 直接違規，不需要補救字樣
        "「保證」與收益詞連用，構成保證回報表述",
    ),
]

# ── 每張卡都必須有的免責聲明 ──
REQUIRED_IN_CARD = [
    (r"以(正式)?保單條款為準", "缺少免責聲明：「一切以正式保單條款為準。」"),
]

# ── 不該出現在圖上的敏感資料 ──
SENSITIVE = [
    (r"\b[A-Z]{1,2}\d{6}\(\d\)\b", "疑似香港身份證號碼"),
    (r"\b\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\b", "疑似信用卡／銀行卡號"),
    (r"\bP\d{8,}\b|\b[A-Z]{2}\d{7,}\b", "疑似保單號碼"),
]

# ── 建議改進（不阻斷交付）──
WARNINGS = [
    (r"確診即賠", "「確診即賠」易被理解為任何確診均賠，建議改為「符合保單定義下可獲賠償」"),
    (r"實報實銷(?!.*合理)", "「實報實銷」宜補上「合理及慣常費用」的界定"),
    (r"[^\d]保證[^\d]", "出現「保證」二字，請確認僅用於保單既有術語（如「保證現金價值」）"),
    (r"100\s*%", "出現 100%，請確認不是對理賠或回報的絕對化描述"),
]

CARD_SPLIT = re.compile(r'<div[^>]*class="card[^"]*"[^>]*data-filename="([^"]+)"')


def strip_html(s: str) -> str:
    s = re.sub(r"<script.*?</script>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<style.*?</style>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<!--.*?-->", " ", s, flags=re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html_mod.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def cards_of(raw: str):
    """回傳 [(卡片名, 可見文字)]；找不到卡片結構時，整份當一張處理。"""
    parts = CARD_SPLIT.split(raw)
    if len(parts) < 3:
        return [("（整份文件）", strip_html(raw))]
    out = []
    for i in range(1, len(parts), 2):
        out.append((parts[i], strip_html(parts[i + 1])))
    return out


def context(text: str, m: re.Match, span: int = 14) -> str:
    a = max(0, m.start() - span)
    b = min(len(text), m.end() + span)
    return ("…" if a else "") + text[a:b] + ("…" if b < len(text) else "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("--strict", action="store_true", help="把 WARN 也視為失敗")
    args = ap.parse_args()

    path = pathlib.Path(args.html).resolve()
    if not path.exists():
        raise SystemExit(f"檔案不存在：{path}")
    raw = path.read_text(encoding="utf-8")
    cards = cards_of(raw)

    print(f"掃描 {path.name}　共 {len(cards)} 張卡\n")
    errors, warns = [], []

    for name, text in cards:
        for pat, msg in BANNED:
            for m in re.finditer(pat, text):
                errors.append((name, msg, context(text, m)))
        for trig, fix, msg in CONDITIONAL:
            for m in re.finditer(trig, text):
                if fix is None:
                    errors.append((name, msg, context(text, m)))
                elif not re.search(fix, text):
                    errors.append((name, msg, context(text, m)))
        for pat, msg in REQUIRED_IN_CARD:
            if not re.search(pat, text):
                errors.append((name, msg, "（整張卡）"))
        for pat, msg in SENSITIVE:
            for m in re.finditer(pat, text):
                errors.append((name, msg, context(text, m)))
        for pat, msg in WARNINGS:
            for m in re.finditer(pat, text):
                warns.append((name, msg, context(text, m)))

    def dump(title, rows, mark):
        if not rows:
            return
        print(f"{mark} {title}（{len(rows)}）")
        for name, msg, ctx in rows:
            print(f"   [{name}] {msg}")
            print(f"        ↳ {ctx}")
        print()

    dump("必須修正", errors, "✗")
    dump("建議檢查", warns, "△")

    if errors:
        print(f"✗ 合規檢查不通過（{len(errors)} 項錯誤）。這份方案不可交付。")
        print("  修法：改寫用字，或補上「非保證」「過往表現不代表將來」等標示。")
        sys.exit(1)
    if warns and args.strict:
        print(f"✗ --strict 模式下 {len(warns)} 項提醒視為失敗。")
        sys.exit(1)
    print("✓ 合規檢查通過。")
    if warns:
        print("  提醒：上面 △ 項目仍值得人工確認一次。")


if __name__ == "__main__":
    main()
