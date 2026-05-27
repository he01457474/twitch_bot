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

它會要求輸入 Dynu hostname、username 和 IP update password，並建立每 5 分鐘更新一次的 Windows 排程。

設定會存在：

```text
projects/irl-stream/config/dynu_ddns.json
projects/irl-stream/config/relay_settings.json
```

這些檔案不進 Git。

SRTLA 之後會另外加 receiver；目前這個伺服器先跑純 SRT。
