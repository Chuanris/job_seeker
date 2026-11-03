# 台灣 Data Science 新鮮人職缺 Bot

每天搜尋台灣可供應屆畢業生申請的全職 Data Scientist 職缺，產生 Markdown／JSON 報告，用 SQLite 去重，並可選擇將新增職缺送到 Telegram。

**這是可自行部署的原始碼，尚未替你部署或啟用排程。** 不需要 OpenAI key；搜尋模式需要你自己的 **Brave Search API key**。Search API 的可用額度與費用以你的方案為準。程式僅使用 Python 標準函式庫，不需要 pip 安裝套件。

## 先試用：不連網、不需要 key

需要 Python 3.9 以上。先解壓縮 ZIP，切換到專案根目錄：

```sh
python -m jobbot --demo
```

查看 `reports/demo-*.md`。內容是明確標示的**合成示範資料**，不是真實職缺。第一次會出現一筆符合資格與一筆待確認；再次執行會是零筆新增。示範模式永遠不呼叫搜尋或 Telegram，且使用獨立的 `data/demo-state.db`。

## 正式執行一次

1. 到 [Brave Search API](https://api-dashboard.search.brave.com/) 建立可使用 Web Search 的 key。
2. 設定環境變數。不要把 key 寫進程式或提交到 GitHub。

PowerShell：

```powershell
$env:BRAVE_SEARCH_API_KEY='你的搜尋 API key'
python -m jobbot
```

macOS／Linux：

```sh
export BRAVE_SEARCH_API_KEY='你的搜尋 API key'
python -m jobbot
```

讀取 `reports/` 最新的 `.md` 與 `.json`。終端機也會印出報告路徑、待回報筆數與來源警告數。上述命令是**執行一次**；每日自動執行請使用下方 GitHub Actions 或自己的排程器。

正式執行前想先看報告、保留待送狀態：

```sh
python -m jobbot --preview
```

`--preview` 不送 Telegram、不標記已回報；仍會儲存發現的職缺。正常執行在完整報告成功寫出後才標記已回報。若啟用 Telegram，必須收到 Telegram 成功回應才標記。傳輸逾時可能發生已送達但未收到確認的情況，因此重試採「至少一次」語意，偶爾可能重複送出。

## 建議部署：GitHub Actions 每日 09:00

這個方式不需要自己的電腦持續開機。

1. 建立 GitHub repository，將**解壓縮後的專案內容**上傳到 repository 根目錄，包含隱藏資料夾 `.github/workflows/daily.yml`。
2. 在 repository 的 **Settings → Secrets and variables → Actions → Secrets** 新增 `BRAVE_SEARCH_API_KEY`。
3. 開啟 **Actions → Taiwan DS new-grad jobs → Run workflow**，先手動跑一次。
4. 確認成功後，預設每天 **01:00 UTC，也就是台灣時間 09:00** 自動執行。排程檔必須位於預設分支；GitHub 排程可能延遲，不能當成準點 SLA。
5. 每次的 Actions run 可直接看 Summary，並下載 `jobs-...` artifact，內有 Markdown／JSON 報告與 `state.db` 備份。

每次排程會先跑測試，再進行搜尋；同一 repository 的 bot 不會同時執行。SQLite 狀態以 Actions cache 保存，通知失敗時也會保存未送項目。Cache **不是永久資料庫**：GitHub 會清除超過 7 天未存取的快取，也可能因容量而移除；artifact 預設保存 30 天。若停跑或快取被移除，可能重新回報舊職缺。需要長期穩定去重，建議採 Docker／伺服器與持久化磁碟，並定期備份 `data/state.db`。

公開 repository 若 60 天沒有活動，GitHub 可能停用排程，需到 Actions 重新啟用。GitHub Actions 的用量與可用功能以帳號／repository 方案為準。

## 選配：Telegram 通知

預設 `telegram` 為 `false`，只產生報告檔案。需要通知時：

1. 在 Telegram 透過官方 `@BotFather` 建立 bot，取得 bot token，先對自己的 bot 發送 `/start`。
2. 透過 Telegram Bot API `getUpdates` 取得自己的 chat ID。請在自己的環境操作，避免把含 token 的網址貼到公開場所。
3. GitHub Actions：新增 secrets `TELEGRAM_BOT_TOKEN`、`TELEGRAM_CHAT_ID`，再在 **Variables** 新增 `TELEGRAM_ENABLED=true`。
4. 本機／Docker：設定同名環境變數，並設定 `TELEGRAM_ENABLED=true`，或將 `config.json` 的 `telegram` 改為 `true`。

有新增／實質變動時，bot 會上傳一份完整 `.md` 文件，避免訊息長度上限造成截斷。沒有新增時不送 Telegram；來源受限與警告仍會寫入本地報告／Actions Summary。全部搜尋失敗會回傳非零退出碼，請查看 Actions run 的錯誤紀錄。

本次開發沒有對任何真實 Telegram 帳號送訊息，沒有真實投遞履歷。

## Docker 或自己的主機

```sh
docker build -t taiwan-ds-job-bot .
```

複製 `.env.example` 為 `.env`，填入自己的 key。建立 `data/`、`reports/` 後執行：

```sh
docker run --rm --env-file .env -v "$PWD/data:/app/data" -v "$PWD/reports:/app/reports" taiwan-ds-job-bot
```

這個容器也是**單次執行**。請用主機 cron、NAS 排程器、雲端排程或 Windows 工作排程器每天啟動。Linux 主機若時區設成 UTC，cron 範例為：

```cron
0 1 * * * cd /absolute/path/taiwan-ds-job-bot && /usr/bin/python3 -m jobbot >> bot.log 2>&1
```

cron 環境也必須取得 `BRAVE_SEARCH_API_KEY`；不要只在互動式終端機 export 後就假設 cron 會繼承。Windows 工作排程器請指定 Python 執行檔、引數 `-m jobbot`，並將「開始位置」設為專案根目錄。使用標準 CPython 較簡單；若使用 Anaconda，請在已啟用的 conda 環境執行，避免 SQLite DLL 版本衝突。

## 預設搜尋與篩選

- 來源：透過 Brave Search 尋找 104、Cake、Yourator、LinkedIn 及公司招募網站的**公開頁面**。不使用這些平台的私人／未公開 API，也不操作登入。
- 地點：台灣各縣市，或遠端職缺明確列出可在台灣申請／工作。
- 職務：Data Scientist、資料／數據科學家，以及 Machine Learning Engineer／Scientist。想只收 Data Scientist，移除 `config.json` 的 ML 搜尋字串，並縮小 `jobbot/rules.py` 的 `ROLE` 規則。
- 主清單：職缺頁具有單一 `JobPosting` JSON-LD、公司與台灣地點可讀、明確全職，且有歡迎新鮮人、零年經驗或包含零年的年資範圍等證據。
- 排除：資深／主管、明確必要年資大於零、在學限定實習、兼職／約聘、已截止或頁面顯示停止收件。
- 待確認：無法取得完整公開內文、只有搜尋摘要、缺少年資、地點或全職證據。這些**不算已核實的新鮮人職缺**。

每筆包含資格依據、刊登日期（若有）、首次發現時間、薪資（若有）、學歷與內文節錄、投遞來源。未公開的資訊不會自行補數字。

## 調整 config.json

| 設定 | 預設 | 用途 |
|---|---|---|
| `queries` | 8 組中英搜尋 | 可依產業、城市與學歷增刪 |
| `freshness` | `pm` | 搜尋引擎近 31 天索引／更新範圍；不等於雇主刊登日期。`pw` 為近 7 天，空字串表示不限 |
| `pages_per_query` | 1 | 每組最多 20 個結果；可提高到 10 頁，僅在 API 表示仍有結果時翻頁 |
| `max_pages` | 100 | 每輪實際讀取頁面上限；超出時報告會提示 |
| `seed_urls` | `[]` | 加入已知單一官方職缺頁，避免只靠搜尋索引；`queries=[]` 配合 seeds 可不用搜尋 key |
| `state_path` | `data/state.db` | 去重與待送資料庫；請持久保存 |
| `report_dir` | `reports` | 本地完整報告位置 |
| `telegram` | `false` | 是否啟用 Telegram；也可透過環境變數啟用 |

預設約 8 次 Search API 請求／輪，重試、增加翻頁或搜尋組數會增加用量。公開職缺頁另外發 HTTP 請求，遵守 `robots.txt` 與網站 crawl delay；無法核實 robots 時不抓取。不得假設搜尋涵蓋所有職缺：索引會延遲，登入／反機器人／純 JavaScript 頁面可能讀不到；這類限制會出現在報告中。

## 去重與已知限制

同公司、同職稱、同地點的項目合併來源 URL；只有刷新刊登日期或追蹤參數不算新增。薪資、內文或資格分類變動會再次回報。若平台將同一職缺的公司／地點翻譯成不同文字，仍可能重複；反過來，同公司同地點同職稱的不同 requisition 可能被合併。這是可讀規則版本的取捨，不是完整的人力平台同步器。

去重以保留的資料庫為準，不會因搜尋沒有找到舊項目就刪掉紀錄。讀取失敗不會將舊職缺標成關閉。新鮮人資格使用明確的中英文規則，不能完整理解所有 JD 語意；未見關閉標示也不代表保證仍在收件。投遞前仍需查看原始職缺頁。

預設只在本地保存報告，不會替你投遞、聯絡雇主或傳送個資。程式**未以真實 Search API key 做端到端驗證**；已使用離線 fixture 測試篩選、去重、錯誤與待送狀態，並實際執行示範流程。Docker build 與遠端 Actions 執行需在部署環境完成。

## 測試

```sh
python -m unittest discover -s tests -v
python -m compileall -q jobbot
```

## 官方參考

- [Brave Web Search API](https://api-dashboard.search.brave.com/api-reference/web/search/get)：搜尋參數、分頁與認證。
- [Schema.org JobPosting](https://schema.org/JobPosting)：公開職缺欄位。
- [GitHub Actions schedule](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)：UTC 排程、延遲與停用條件。
- [GitHub Actions cache](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching)：狀態快取限制。
- [Telegram Bot API](https://core.telegram.org/bots/api#senddocument)：選配的文件通知。
