# News Monitor v2.2 — 模擬輸出與驗收清單

## 一、模擬輸出（符合新格式）

以下為單則完整合併後的範例；實際發送會依 2800 字在 `━━━━━━━━━━` 邊界切段，第 2 段起加「📰 全球財經日報 · 分來源摘要」等標題。

```
📰 *全球財經日報* | 2026-03-06
📊 5 來源 | 28 則新聞 | 5 點數

━━━━━━━━━━

🔥 *宏觀洞察*
風險溫度：中
主驅動：利率預期、地緣風險、能源供給
資產映射：美股↑ 黃金→ 原油↓ BTC↑
24h 關注：Fed 官員談話 | 歐盟天然氣儲備數據 | 美國非農前瞻

━━━━━━━━━━

📌 *Top 5 必看*
🌍宏觀 Fed signals delay to rate cuts amid sticky inflation
  市場延後降息預期，風險資產承壓 [→](https://www.wsj.com/fed-rates)
💹市場 Tech earnings beat estimates; AI capex in focus
  科技財報優於預期，AI 資本支出成焦點 [→](https://www.ft.com/tech-earnings)
🛢能源 OPEC+ extends output cuts into Q2
  產油國延長減產，油價獲支撐 [→](https://www.reuters.com/opec)
🧠AI Nvidia unveils next-gen data center chip
  新晶片發表帶動 AI 板塊情緒 [→](https://www.bloomberg.com/nvidia)
🌍宏觀 China sets 5% growth target for 2026
  中國增長目標符合預期，關注刺激細節 多源確認：Reuters, Economist

━━━━━━━━━━

📰 *分來源摘要*
*WSJ*
  🌍宏觀 Fed signals delay to rate cuts
    延後降息預期升溫 [→](https://www.wsj.com/fed-rates)
  💹市場 Treasury yields rise on strong data
    強數據推升殖利率 [→](https://www.wsj.com/treasury)
*FT*
  💹市場 Tech earnings beat estimates
    科技財報亮眼 [→](https://www.ft.com/tech-earnings) 多源確認：Bloomberg
  🛢能源 European gas storage above seasonal norm
    歐洲天然氣庫存高於季節 [→](https://www.ft.com/gas)
*Reuters*
  🛢能源 OPEC+ extends output cuts
    減產延長 [→](https://www.reuters.com/opec)
  🌍宏觀 China sets 5% growth target
    中國增長目標 [→](https://www.reuters.com/china) 多源確認：Economist

━━━━━━━━━━

📋 *明日跟蹤清單*
  • 美國 2 月非農就業與失業率
  • 歐洲央行官員談話
  • 比特幣現貨 ETF 淨流入數據

---
_🤖 News Monitor Bot v2.2_
```

若超過 2800 字，第 2 段會以段落標題開頭，例如：

```
📰 *全球財經日報* · 分來源摘要

━━━━━━━━━━

*Bloomberg*
  🧠AI Nvidia unveils next-gen chip
    ...
```

---

## 二、驗收清單（5 條）

| # | 項目 | 驗證方式 |
|---|------|----------|
| 1 | **可讀性** | 檢查：Header（日期、來源數、總條數）→ Top 5（每條 2 行+連結）→ 宏觀 4 行 → 分來源（每來源 3–5 條、標籤+多源確認）→ 明日 3 條；分隔符 `━━━━━━━━━━` 一致；主題標籤 🌍/🛢/💹/🧠 正確。 |
| 2 | **去重效果** | 跨來源相同事件只出現一則主訊息，且標註「多源確認：WSJ/FT/Reuters」；單一主題（如戰爭/利率）整份最多約 4 條，無刷屏。 |
| 3 | **分段完整性** | 單則約 2500–3000 字（實作 2800）於 `━━━━━━━━━━` 邊界切段；第 2 段起有段落標題（如「📰 全球財經日報 · 分來源摘要」），無孤立「2/3、3/3」。 |
| 4 | **連結保留** | 每則新聞的「閱讀原文」為 [→](URL)；Top 5、分來源皆保留原連結；多源合併時保留主訊息連結。 |
| 5 | **Token/成本變化** | 摘要改為單次 JSON 結構化輸出（macro + top5 + per_source + tomorrow），總 token 與 v2.1 相近或略增；提取階段未改，成本持平。可對比同一批來源的 v2.1 / v2.2 實際 token 用量。 |

---

## 三、修改檔案與原因摘要

| 檔案 | 修改原因 |
|------|----------|
| **summarizer.py** | 宏觀洞察改為 4 行結構化（風險溫度、主驅動、資產映射、24h 關注）；新 prompt 產出 JSON（macro_insight, top5, per_source, tomorrow）；加入 `deduplicate_across_sources()`（標題相似度 + 多源確認）；`_render_telegram_body()` 組裝易讀排版與分隔符；補齊 top5/per_source 的 link 與 sources_confirming。 |
| **notifier.py** | 單則長度改為 2800 字；`split_message_smart()` 改為在 `━━━━━━━━━━` 邊界切段；多段時第 2 段起加 `_segment_title()`（如「📰 全球財經日報 · 分來源摘要」），避免孤立「2/3、3/3」。 |
| **main.py** | 僅版本註解改為 v2.2，流程不變（header + summary + footer → send_long_message）。 |

未新增依賴，僅使用標準庫 `re`、`difflib`。
