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
- 可主動提問以取得所需資訊
- 新建立的工具腳本一律放在工作目錄 `D:\tset\FlyCatClaude Code`，不放桌面或其他位置
- 目錄結構規則：
  - `.bat` 啟動檔 → 根目錄（方便雙擊）
  - `.ps1` 腳本 → `scripts/`
  - 工具程式 → `tools/`
  - 說明文件、圖片 → `docs/`
  - `__pycache__` 等快取目錄不納入 git，可直接刪除
- 有新的偏好規則或權限設定，都寫回 CLAUDE.md
- **使用量達 95% 時**，強制把所有未完成任務存到 memory，停止繼續執行，等用戶下次使用量重置後再繼續
- 測試過程建立的暫時腳本或檔案，任務完成後立即清除，不留在工作目錄
- 功能完成或重大修改後，直接執行 git commit，不等用戶提醒

## 說明風格
使用者非工程師，盡量用白話文與比喻方式說明，減少不必要的技術術語。

## 環境
- 作業系統：Windows 10
- 終端機：Windows Terminal
- 系統 code page：CP936（GBK），非 Unicode 程式預設用簡體中文編碼
- 慣用語言順序：中文（簡體，中國）→ 繁體中文（台灣）→ 韓文

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
| 公開 | `index.html` 指令手冊（GitHub Pages） | https://github.com/he01457474/twitch_bot |
| 私有 | `test.py` 機器人程式碼 | https://github.com/he01457474/twitch_bot_private |

### 本機路徑
- 工作目錄：`D:\tset\FlyCatClaude Code`（公開 repo）
- 私有暫存：`D:\tset\bot_private`（私有 repo）
- `.env` 永遠只留在 BOT 那台電腦，不上傳 GitHub

### 部署流程
1. **這台電腦**：改完 `3.py` / `index.html` → 執行 `deploy.bat`
2. **LAPTOP-6N12C053**：執行 `D:\下載\BOT2\repo_temp\update_bot.bat` → 自動 pull + 重啟 BOT

### 注意事項
- `3.py` 在這台電腦編輯，`deploy.bat` 會自動同步到私有 repo
- BOT 實際執行檔為 `D:\下載\BOT2\test.py`，由 `start_bot.bat` 啟動

## 已安裝的 MCP 工具

| 工具 | 用途 | 可存取範圍 |
|------|------|------------|
| **filesystem** | 讀寫本機檔案 | 桌面、文件、下載（`C:/Users/he014/Desktop`、`Documents`、`Downloads`） |
| **firecrawl** | 抓取並解析網頁內容 | 任意公開網址 |
| **playwright** | 操控真實瀏覽器（截圖、填表、登入後頁面） | 任意網址，含需登入的頁面 |
