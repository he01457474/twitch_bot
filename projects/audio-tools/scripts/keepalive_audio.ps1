# 靜音保活 - 持續播放無聲音訊，防止喇叭進入休眠
$sampleRate = 44100
$dataSize   = $sampleRate * 2
$fileSize   = $dataSize + 36

$ms = New-Object System.IO.MemoryStream
$bw = New-Object System.IO.BinaryWriter($ms)
$bw.Write([byte[]][System.Text.Encoding]::ASCII.GetBytes("RIFF"))
$bw.Write([int32]$fileSize)
$bw.Write([byte[]][System.Text.Encoding]::ASCII.GetBytes("WAVE"))
$bw.Write([byte[]][System.Text.Encoding]::ASCII.GetBytes("fmt "))
$bw.Write([int32]16)
$bw.Write([int16]1)
$bw.Write([int16]1)
$bw.Write([int32]$sampleRate)
$bw.Write([int32]($sampleRate * 2))
$bw.Write([int16]2)
$bw.Write([int16]16)
$bw.Write([byte[]][System.Text.Encoding]::ASCII.GetBytes("data"))
$bw.Write([int32]$dataSize)
$bw.Write((New-Object byte[] $dataSize))
$bw.Flush()
$ms.Position = 0

$player = New-Object System.Media.SoundPlayer($ms)
$player.PlayLooping()

while ($true) { Start-Sleep -Seconds 300 }
