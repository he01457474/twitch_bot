# VOD9094 YouTube 備份

這個資料夾用來備份 `https://www.youtube.com/@vod9094/videos` 的公開影片。

非公開播放清單：

`https://www.youtube.com/playlist?list=PLOvdacObECFhoCU_fpTDinLvKGanxGdRz`

## 使用方式

雙擊：

`projects/youtube-backup/launchers/備份VOD9094頻道.bat`

備份非公開播放清單時，雙擊：

`projects/youtube-backup/launchers/備份VOD9094非公開播放清單.bat`

影片會下載到：

`I:\YT影片備份\vod9094`

已下載紀錄會寫到：

`I:\YT影片備份\vod9094\download-archive.txt`

之後中斷或重跑時，`yt-dlp` 會依照這個紀錄跳過已完成的影片。

## CMD 進度視窗

雙擊：

`projects/youtube-backup/launchers/開啟VOD9094進度CMD.bat`

CMD 視窗會每 30 秒刷新一次目前完成數、總數和百分比。關掉 CMD 視窗只會關閉監看器，不會停止下載。

目前總數以公開頻道 135 部加上非公開播放清單可見 30 部計算，共 165 部。YouTube 回報這個播放清單另有 1 部不可用影片被隱藏，但沒有提供影片 ID 或標題。

## 未公開影片

未公開影片通常不會出現在頻道的 `/videos` 頁面。後續要補未公開影片時，需要提供未公開影片網址清單，或用 YouTube / Google 匯出的資料整理出影片連結再下載。
