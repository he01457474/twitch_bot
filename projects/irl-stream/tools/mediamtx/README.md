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
