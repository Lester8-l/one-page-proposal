# One-Page Proposal · 一頁紙方案產生器

把客戶的需求與保險產品接成**一張** 1080×1350 的卡片，在 WhatsApp 直接發給客戶看。

設計風格取自 [lesterliang.com](https://www.lesterliang.com/)（森林綠 × 暖金 × 米白），
色票與字體與 `ig-post-generator` 共用同一套 token。

## 為什麼不是「排版工具」

一頁紙方案要回答的不是「產品有什麼」，而是「**你講嘅關注，點樣被回應**」。
所以每張卡的核心結構是：

```
客戶的原話（3 條）  →  方案要點（要點 → 對應關注）  →  關鍵數字  →  下一步
```

skill 內含**需求匹配引擎**（`references/matching-engine.md`）與**5 險種產品庫**
（`references/product-library.md`），負責把「驚病咗冇收入」翻譯成「危疾險的一筆過賠償」。

## 三款版型

| 代號 | 版型 | 用在什麼客戶 |
|---|---|---|
| **P1** | 需求對照（預設） | 已談過、明確講過關注點 |
| **P2** | 情境敘事 | 對抽象條款無感，需要具體畫面打動 |
| **P3** | 保障清單 | 已有信任，只想看「保咩、幾多錢」 |

## 安裝

```bash
cp -r one-page-proposal ~/.workbuddy/skills/
```

無第三方依賴，只需要 Python 3 與 headless Chrome／Edge。

## 用法

直接說「幫我出一頁紙方案，客戶係陳先生，佢最擔心…」，並附上產品資料。
skill 會先出**方案文字稿**給你核對，確認後才生成 HTML 與 PNG。
詳見 `SKILL.md`。

## 三支檢查腳本（交付前必跑）

```bash
python scripts/check-compliance.py plan.html   # 保險禁詞、非保證標示、過往績效標註
python scripts/check-fit.py plan.html          # 內容溢出裁切
python scripts/export-png.py plan.html --out out/   # 輸出 1080×1350 PNG
```

`check-compliance.py` 不通過（exit 1）**一律不准交付**。它攔截的包括：

- 禁止詞：穩賺、零風險、像定存、包賠、全賠、儲蓄替代品…
- 出現預期／潛在利益但沒有「非保證」標示
- 出現回報率／過往數據但沒有「過往表現不代表將來」
- 每張卡缺少「一切以正式保單條款為準」

## 檔案

```
one-page-proposal/
├── SKILL.md
├── assets/template.html          3 款版型 + 設定區 + SVG 線稿 + 瀏覽器匯出
├── references/
│   ├── matching-engine.md        需求 → 險種 → 賣點 的匹配邏輯
│   └── product-library.md        5 險種賣點框架與數字結構
├── scripts/
│   ├── check-compliance.py       合規守門員
│   ├── check-fit.py              溢出檢測
│   └── export-png.py             批次出圖
└── examples/
    ├── sample-input.md           範例輸入
    └── P1/P2/P3-*.png            三款示範成品
```

## 免責

本工具產出的內容為**方案摘要**，不構成保單條款或銷售建議。
所有數字須以保險公司正式保單及建議書為準，實際保障範圍與理賠條件依保單條文。
使用前請確認符合所屬地區的保險監管要求。
