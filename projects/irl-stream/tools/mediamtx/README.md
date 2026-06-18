# MediaMTX 本機中繼伺服器

這個資料夾放 IRL 中繼伺服器用的 MediaMTX。

請下載 Windows 版 MediaMTX，解壓縮後把 `mediamtx.exe` 放到：

```text
projects/irl-stream/tools/mediamtx/mediamtx.exe
```

`mediamtx.exe` 是本機執行檔，不進 Git。

`tools/mediamtx/mediamtx.yml` 只是範本，不放台主密鑰。實際執行用的設定會由白名單工具產生在：

```text
projects/irl-stream/config/mediamtx.yml
```

這份實際設定不進 Git。

## 白名單

台主推流 / 拉流資料不要手動組，請用：

```text
projects/irl-stream/launchers/管理IRL白名單.bat
```

新增台主後，工具會產生：

```text
手機 URL
手機 Stream ID
OBS 媒體來源輸入
```

這些資料會自動帶上 MediaMTX 的 SRT 帳號密碼。新增、停用或重新產生密鑰後，工具會更新 `config/mediamtx.yml`；如果 MediaMTX 正在跑，工具會自動重啟套用。

每次啟動 `啟動直播環境.bat` 時，也會先自動套用白名單，避免忘記手動套用。

## Dynu DDNS

這台電腦改用 Dynu 更新對外網址。第一次使用請雙擊：

```text
projects/irl-stream/launchers/設定DynuDDNS.bat
```

它會要求輸入 Dynu hostname、username 和 IP update password。之後啟動直播環境時，會在背景每 5 分鐘自動更新 Dynu。

設定會存在：

```text
projects/irl-stream/config/dynu_ddns.json
projects/irl-stream/config/relay_settings.json
```

這些檔案不進 Git。

## 管理員通知

台主本人不用收到通知；通知只給管理員。第一次使用請在跑中繼伺服器的電腦雙擊：

```text
projects/irl-stream/launchers/設定管理員通知.bat
```

目前使用 Discord Webhook。設定會存在：

```text
projects/irl-stream/config/notification.json
projects/irl-stream/config/notification_state.json
```

這些檔案不進 Git。通知內容只放狀態與 Twitch ID，不會把推流 / 拉流密鑰送到 Discord。

會通知的事件：

```text
中繼伺服器啟動 / 關閉
台主開始推流 / 停止推流
MediaMTX 停止與自動重啟結果
Dynu DDNS 更新失敗或 IP 改變
白名單新增、停用、刪除、重產密鑰
```

## 目前網路轉發

目前確認可用的架構是「外部固定用 5002，本機 MediaMTX 用 8890」：

```text
手機 5G / 外部台主
→ flycatirl.ddnsgeek.com:5002
→ H660WM 數據機 UDP 5002 轉到 Deco WAN IP:5002
→ Deco UDP 5002 轉到本機 192.168.68.50:8890
→ MediaMTX
```

管理員自己的 OBS 如果跟 MediaMTX 在同一台電腦，請用：

```text
srt://127.0.0.1:8890?streamid=read:<Twitch ID>:<read user>:<read key>
```

外部台主自己的 OBS 才用：

```text
srt://flycatirl.ddnsgeek.com:5002?streamid=read:<Twitch ID>:<read user>:<read key>
```

手機端 FPS 不是 MediaMTX 鎖住；目前看到 30 fps 是手機 App 送出的設定。要提高到 60 fps，請在 IRL Pro / Moblin 的 Video 設定改 60 fps，並優先使用 H264 / AVC。若 OBS 黑畫面或網路不穩，先退回 30 fps。

SRTLA 之後會另外加 receiver；目前這個伺服器先跑純 SRT。

## 筆電負責中繼伺服器

之後提到「筆電」時，預設就是 `LAPTOP-6N12C053`。目前管理員自用架構是：

```text
手機 5G / 外部 SRT
→ flycatirl.ddnsgeek.com:5002
→ 路由器轉發
→ 筆電 MediaMTX:8890
→ 桌電 OBS 拉筆電影像
→ 桌電 OBS 推到 Twitch
```

也就是：

```text
筆電：只負責開中繼伺服器、Dynu、MediaMTX、白名單
桌電：只負責 OBS、NOALBS、開台
```

桌電不需要另外分專案腳本；照平常開 OBS 和 NOALBS 即可。差別只有 OBS 拉流網址和 NOALBS 監測網址要改成筆電內網 IP。

## 之後更新筆電程式（常用）

筆電已經在跑、只想把腳本更新成最新版時，在桌電這台雙擊：

```text
projects/irl-stream/launchers/產生筆電程式更新包.bat
```

它只打包程式碼（scripts / launchers），**不含** config（白名單、密鑰、Dynu、通知設定），也不含 tools（mediamtx.exe）。產生的 zip 在 `config/exports/`。

把 zip 複製到筆電，解壓直接覆蓋筆電現有的 IRL 資料夾即可。只會更新腳本，config 與 tools 原封不動，白名單不會被動到，也不用再跑初始化。

> 筆電第一次啟用管理員通知時，更新完雙擊 `launchers/設定管理員通知.bat` 設定一次即可。

## 第一次全新搬到筆電（很少用到）

如果是全新筆電、還沒有專案資料夾：先用程式更新包把 scripts / launchers 帶過去解壓，再雙擊：

```text
projects/irl-stream/launchers/初始化筆電IRL環境.bat
```

初始化腳本會逐步詢問後才執行：下載 MediaMTX、建立防火牆規則、提示筆電內網 IP。白名單與密鑰請從原本電腦的 `config/` 手動複製過去，或重新用「管理IRL白名單.bat」建立。

## 路由器要改的地方

搬到筆電後，外部 SRT 固定仍然走 `flycatirl.ddnsgeek.com:5002`，但最後要轉到筆電：

```text
H660WM：UDP 5002 -> Deco WAN IP:5002
Deco：UDP 5002 -> 筆電內網 IP:8890
```

`H660WM` 那段通常不用改，因為它本來就轉到 Deco。最常需要改的是 Deco，把 UDP `5002` 的目標從桌電改成筆電內網 IP。

如果桌電 NOALBS 要讀筆電 MediaMTX 的訊號狀態，筆電 Windows 防火牆需要允許內網連 TCP `9997`。同區網使用時，不建議把 TCP `9997` 對外開到網際網路。

只有當你真的要讓外部電腦連 MediaMTX API 時，才需要另外確認：

```text
H660WM：TCP 9997 -> Deco WAN IP:9997
Deco：TCP 9997 -> 筆電內網 IP:9997
```

## 桌電要改的地方

桌電 OBS 不能再用 `127.0.0.1:8890`，因為 MediaMTX 已經改在筆電。桌電 OBS 的媒體來源要改成：

```text
srt://筆電內網IP:8890?streamid=read:<Twitch ID>:<read user>:<read key>
```

桌電 NOALBS 的 `config.json` 裡，`statsUrl` 也要改成筆電：

```text
http://筆電內網IP:9997/v3/paths/get/<Twitch ID>
```

如果 OBS 和 NOALBS 都改到筆電同一台跑，才使用 `127.0.0.1`。

## 每次開台順序

```text
1. 筆電：雙擊 啟動直播環境.bat
2. 桌電：開 OBS
3. 桌電或台主電腦：雙擊 直播輔助.bat，選 1 啟動 NOALBS + BRB
4. 手機：開始 SRT 推流
5. Twitch 聊天室：輸入 !start
```

關閉時：

```text
1. 桌電或台主電腦：雙擊 直播輔助.bat，選 2 關閉 NOALBS + BRB
2. 桌電：OBS 停止直播
3. 筆電：需要關中繼伺服器時，雙擊 關閉直播環境.bat
```

## 權限與關閉

初始化和 Windows 防火牆設定可能需要「以系統管理員身分執行」。平常開伺服器不需要管理員，直接雙擊 `啟動直播環境.bat` 即可。

如果之前用管理員權限啟動過 MediaMTX，當次 `mediamtx.exe` 也會是管理員權限。要改回一般權限：

```text
1. 雙擊 關閉直播環境.bat
2. 如果 mediamtx.exe 還在工作管理員，右鍵以系統管理員身分執行 關閉直播環境.bat
3. 確認 mediamtx.exe 已消失
4. 之後用一般雙擊 啟動直播環境.bat
```

`關閉直播環境.bat` 會先關 MediaMTX 監控，再關 Dynu DDNS 監控，最後關 MediaMTX。若 MediaMTX 是管理員權限啟動而一般權限關不掉，腳本會提示提權關閉或請到工作管理員手動結束。

## 未來：SRTLA 聚合

目前先維持純 SRT，不直接改成 SRTLA。MediaMTX 目前負責 SRT 中繼，不內建 SRTLA receiver；如果之後要做多網路聚合，需要在 MediaMTX 前面另外加一層 SRTLA receiver。

預期架構：

```text
手機 IRL App（SRTLA）
→ flycatirl.ddnsgeek.com:5002
→ 筆電 SRTLA receiver
→ 筆電 MediaMTX:8890
→ 桌電 OBS / NOALBS
```

實作時要保留兩種模式：

```text
模式 1：純 SRT，現階段穩定使用
模式 2：SRTLA 聚合，之後測試用
```

預估延遲：

```text
純 SRT：大約 1-3 秒
SRTLA 聚合：大約 2-5 秒
網路差或多路品質差很多：可能 5-10 秒以上
```

之後真的要做 SRTLA 時，要另外處理：SRTLA receiver 工具、啟動 / 關閉腳本、路由器 port、手機 App 設定、白名單 / 台主包是否要分 SRT 與 SRTLA 版本。
