# 使用者偏好設定

## 語言
一律繁體中文對話，除非有指定特別的語言。

## 回覆風格
- 語氣自然像朋友對話，少用生硬詞彙，例如「旨在」、「總的來說」
- 盡量減少相似回覆的套話和冗詞

## 中文排版原則
- 中文遇到英文、數字時，兩側各加一個半形空格，例如：我有 3 台 iPhone 手機
- 保留專業術語的英文原文與縮寫，例如 Google Search Console、Notion、OpenAI

## 開發行動原則
- 執行重要開發行動前，先輸出簡要計劃，等確認後再執行
- 若信心度低或有更好方案，上網研究後直接提出，無須護主
- 可主動提問以取得所需資訊；但能用工具自查的（Read、Grep、Bash）就自己查，不要問用戶
- 新建立的工具腳本一律放在工作目錄 `D:\tset\FlyCatClaude Code`，不放桌面或其他位置
- 目錄結構規則：
  - 同一個項目的專案檔案集中放在 `projects/<project-name>/`
  - 專案資料夾內再分 `launchers/`、`scripts/`、`tools/`、`docs/`
  - `.bat` 啟動檔 → 專案內 `launchers/`（方便雙擊）
  - `.ps1` 腳本 → 專案內 `scripts/`
  - 工具程式 → 專案內 `tools/`
  - 說明文件、圖片 → 專案內 `docs/`
  - `index.html`、`deploy.bat`、`3.py` 因既有部署流程暫時保留在工作目錄根層
  - 目前專案：餐廳工具 `projects/restaurant-bot/`、IRL / 直播環境 `projects/irl-stream/`、音訊工具 `projects/audio-tools/`、Twitch Bot 文件 `projects/twitch-bot/`
  - `__pycache__` 等快取目錄不納入 git，可直接刪除
- 有新的偏好規則或權限設定，都寫回 AGENTS.md 和 CLAUDE.md（兩個檔案保持同步）
- 修改登入 / 重連相關功能時，必須同步處理「自動重連」和「手動登入」兩條流程，讓使用者可以直接用手動登入測試同一套行為
- 對外給別人用的 GUI 工具要保留「一般版」和「除錯版」入口；一般版隱藏一般使用者用不到的測試工具，除錯版保留完整偵測、截圖、OCR 測試等工具
- 餐廳機器人對外發佈以單一 `.exe` 為主，不把除錯版或額外 bat / README 一起交給一般使用者；打包版設定檔放在 exe 同目錄，方便使用者刪除重置
- 餐廳 / 釣魚工具顯示名稱與打包檔名使用「摩爾莊園輔助」
- 給使用者雙擊的啟動檔檔名優先使用中文，方便辨識；不要只為了避開亂碼問題改成英文檔名。若 `.bat` 或腳本出現中文亂碼，優先修正編碼、BOM、PowerShell wrapper 或把中文訊息移到 UTF-8 BOM 的 `.ps1`，不要改掉使用者要看的中文檔名。
- 餐廳 / 釣魚工具只有使用者明確要求「打包」或「產 exe」時才執行打包腳本；平常修改只做程式檢查
- **使用量達 95% 時**，強制把所有未完成任務存到 memory，停止繼續執行，等用戶下次使用量重置後再繼續
- 測試過程建立的暫時腳本或檔案，任務完成後立即清除，不留在工作目錄
- 功能完成或重大修改後，直接執行 git commit，不等用戶提醒
- 之後 git add / git commit 由助理自行執行，不需要另外詢問使用者
- 說明網頁更新完成後，自動 commit 並 push 到對應網頁 repo，不需要另外詢問使用者；若因網路或權限失敗，回覆中說明即可
- 如果 git add / git commit 因權限被 sandbox 擋住，不要再向使用者彈出權限確認；先保留未提交狀態並在回覆中說明
- 語法檢查、編譯檢查等本地驗證由助理自行執行並修到通過，不需要另外詢問使用者
- 程式修改完成後，若新功能需要使用者校準座標、確認顏色值、或提供其他資訊，必須在回覆末尾明確條列出來
- 重要的偏好規則或設定，直接寫進 CLAUDE.md 和 AGENTS.md，不要只存到 memory
- 一般版（非除錯版）的 UI 按鈕顯示邏輯，平時開發不需同步維護；只有在要打包成 exe 對外發布前，才統一核對一般版應顯示哪些功能

## 說明風格
使用者非工程師，盡量用白話文與比喻方式說明，減少不必要的技術術語。

## 環境
- 作業系統：Windows 10
- 終端機：Windows Terminal
- 系統 code page：CP936（GBK），非 Unicode 程式預設用簡體中文編碼
- 慣用語言順序：中文（簡體，中國）→ 繁體中文（台灣）→ 韓文
- 本機 Python 執行檔：`D:\tset\FlyCatClaude Code\.tools\python-3.13.3-embed\python.exe`；語法檢查請用完整路徑，例如 `& 'D:\tset\FlyCatClaude Code\.tools\python-3.13.3-embed\python.exe' -m py_compile 3.py`，不要只用 `python` 或 `py`
- 筆電固定指 `LAPTOP-6N12C053`；之後使用者提到「筆電」時，除非另有說明，一律指這台。
- 在筆電端執行自動化、下載工具、建立或覆蓋檔案、修改系統設定或防火牆規則前，必須先明確提示並等使用者確認後才繼續。
- IRL 中繼伺服器若搬到筆電，目標機器預設為 `LAPTOP-6N12C053`。

## 中文亂碼處理
遇到工具輸出 GBK 亂碼時：
1. 先以 CP936/GBK 解讀，轉成**繁體中文**呈現
2. 無法轉繁體時，用中文呈現即可，不要把亂碼直接丟給用戶

## 時間
- 永遠使用台北時間（Asia/Taipei, UTC+8）
- 涉及日期計算、時間戳記、檔案命名等操作前，先執行 `date` 確認系統時間

## PowerShell 腳本編碼
- 包含中文的 `.ps1` 一律加 UTF-8 BOM（`EF BB BF`），否則 PS5 會以 GBK 讀取，破壞語法
- 寫入方式：`[System.IO.File]::WriteAllText($path, $content, (New-Object System.Text.UTF8Encoding $true))`

## 中文亂碼處理
遇到工具輸出 GBK 亂碼時：
1. 先以 CP936/GBK 解讀，轉成**繁體中文**呈現
2. 無法轉繁體時，用中文呈現即可，不要把亂碼直接丟給用戶

## 時間
- 永遠使用台北時間（Asia/Taipei, UTC+8）
- 涉及日期計算、時間戳記、檔案命名等操作前，先執行 `date` 確認系統時間

## 部署架構

### Repo 分工
| Repo | 內容 | 網址 |
|------|------|------|
| 公開 | `index.html` 指令手冊（Netlify） | https://github.com/he01457474/twitch_bot |
| 私有 | `test.py` 機器人程式碼 | https://github.com/he01457474/twitch_bot_private |

### 分支規則
- `index.html` 更新後，必須推到 **`main`** 分支，Netlify 才會自動部署
- `master` 分支照常 commit，但 `index.html` 要額外 `git push origin main` 或用 `git checkout main && git checkout master -- index.html && git commit && git push origin main && git checkout master`

### 本機路徑
- 工作目錄：`D:\tset\FlyCatClaude Code`（公開 repo）
- 私有暫存：`D:\tset\bot_private`（私有 repo）
- `.env` 永遠只留在 BOT 那台電腦，不上傳 GitHub

### 部署流程
1. **這台電腦**：改本機 BOT 檔案 `D:\tset\FlyCatClaude Code\3.py`，完成後同步到私有 repo `D:\tset\bot_private\src\test.py` 並 commit/push
2. **LAPTOP-6N12C053**：執行 `D:\下載\BOT2\repo_temp\update_bot.bat` → 自動 pull + 重啟 BOT

### 注意事項
- 之後聊天 BOT 相關修改，可以先改本機 `D:\tset\FlyCatClaude Code\3.py`；修完後必須同步到私有 repo `D:\tset\bot_private\src\test.py`
- 同步到私有 repo 後直接 commit/push 到 GitHub，讓另一台 BOT 電腦可以 pull 更新
- `.env`、資料庫、log、備份、執行暫存都不能提交
- BOT 實際執行檔為 `D:\下載\BOT2\test.py`，由 `start_bot.bat` 啟動

## 已安裝的 MCP 工具

| 工具 | 用途 | 可存取範圍 |
|------|------|------------|
| **filesystem** | 讀寫本機檔案 | 桌面、文件、下載（`C:/Users/he014/Desktop`、`Documents`、`Downloads`） |
| **firecrawl** | 抓取並解析網頁內容 | 任意公開網址 |
| **playwright** | 操控真實瀏覽器（截圖、填表、登入後頁面） | 任意網址，含需登入的頁面 |

## IRL 中繼伺服器白名單
- IRL 借用者的手機 Stream ID 和 OBS 拉流網址，統一由 `projects/irl-stream/launchers/管理IRL白名單.bat` 產生，不手動組公開的 `publish:<Twitch ID>`。
- 私有白名單資料放在 `projects/irl-stream/config/relay_users.json`，不提交 Git。
- 實際執行用的 MediaMTX 白名單設定放在 `projects/irl-stream/config/mediamtx.yml`，不提交 Git；`tools/mediamtx/mediamtx.yml` 只當無密鑰範本。
- 新增、停用或重新產生 IRL 台主密鑰後，白名單工具會自動套用設定；若 MediaMTX 正在執行，會自動重啟。啟動直播環境時也會先自動套用白名單。
- IRL 對外 DDNS 改由 Dynu 管理；本機私有設定放在 `projects/irl-stream/config/dynu_ddns.json` 和 `projects/irl-stream/config/relay_settings.json`，不提交 Git。
