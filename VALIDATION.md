# 驗證紀錄

- 2026-11-03：40 個 unittest 測試通過，`compileall` 通過，CLI `--help` 正常。
- 實際離線執行 demo 兩次：第一次 2 筆（1 筆核實、1 筆待確認），第二次 0 筆新增。
- 缺少 Search API key 時回傳退出碼 1，提供明確設定提示。
- 獨立唯讀程式碼審查後，已修正必要年資被加分條件覆蓋、複雜年資寫法、遺漏 JSON-LD qualifications、過期待送項目、已知 URL 讀取失敗重複通知、非字串 schema type 等問題，補有回歸測試。
- 未提供真實 API key，因此未實際呼叫 Brave Search API 或傳送 Telegram；Docker build 與 GitHub Actions 遠端執行也尚未完成。部署後請先手動執行一次，檢查真實來源的可讀性與報告品質。
- 本機驗證使用 Python 3.9.7；Docker／Actions 設定採 Python 3.12。Anaconda 的 SQLite DLL 路徑衝突已在測試命令環境中排除，未修改使用者系統設定。
