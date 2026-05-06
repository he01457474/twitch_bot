# MediaMTX 本機版

這個資料夾放本機中繼伺服器用的 MediaMTX。

請下載 Windows 版 MediaMTX，解壓縮後把 `mediamtx.exe` 放在這個資料夾：

```text
projects/irl-stream/tools/mediamtx/mediamtx.exe
```

`mediamtx.exe` 是執行檔，不進 Git。設定檔使用同資料夾的 `mediamtx.yml`。

目前主線先支援 SRT：

```text
srt://flycat.ddns.net:5002
```

SRTLA 之後會另外加 receiver，不由 MediaMTX 直接處理。
