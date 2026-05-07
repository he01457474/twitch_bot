# MediaMTX 本機中繼伺服器

這個資料夾放 IRL 中繼伺服器用的 MediaMTX。

請下載 Windows 版 MediaMTX，解壓縮後把 `mediamtx.exe` 放到：

```text
projects/irl-stream/tools/mediamtx/mediamtx.exe
```

`mediamtx.exe` 是本機執行檔，不進 Git；`mediamtx.yml` 是伺服器設定檔。

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

這些資料會自動帶上 MediaMTX 的 SRT 帳號密碼。停用台主或重新產生密鑰後，工具會更新 `mediamtx.yml`，需要重啟 MediaMTX 才會生效。

SRTLA 之後會另外加 receiver；目前這個伺服器先跑純 SRT。
