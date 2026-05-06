$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$ToolsDir = Join-Path $Root ".tools"
$VenvDir = Join-Path $ToolsDir "restaurant-build-venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$PythonVersion = "3.11.9"
$EmbedDir = Join-Path $ToolsDir "python-build"
$EmbedPython = Join-Path $EmbedDir "python.exe"
$Zip = Join-Path $ToolsDir "python-$PythonVersion-embed-amd64.zip"
$GetPip = Join-Path $ToolsDir "get-pip.py"
$PythonUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip"
$GetPipUrl = "https://bootstrap.pypa.io/get-pip.py"

New-Item -ItemType Directory -Path $ToolsDir -Force | Out-Null

function Test-PythonTk {
    param([string]$PythonExe)
    try {
        & $PythonExe -c "import tkinter; print(tkinter.TkVersion)" 2>$null | Out-Null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Find-FullPython {
    $candidates = @(
        "C:\Users\he014\AppData\Local\Programs\Python\Python311\python.exe",
        "C:\Users\he014\AppData\Local\Programs\Python\Python310\python.exe",
        "C:\Python311\python.exe",
        "C:\Python310\python.exe",
        "C:\Program Files\Python311\python.exe",
        "C:\Program Files\Python310\python.exe"
    )
    foreach ($candidate in $candidates) {
        if ((Test-Path $candidate) -and (Test-PythonTk $candidate)) {
            return $candidate
        }
    }
    return $null
}

if ((Test-Path $VenvPython) -and (Test-PythonTk $VenvPython)) {
    Write-Host "Build venv ready:"
    Write-Host $VenvPython
    exit 0
}

$FullPython = Find-FullPython
if ($FullPython) {
    Write-Host "Creating build venv from:"
    Write-Host $FullPython
    if (Test-Path $VenvDir) {
        Remove-Item -LiteralPath $VenvDir -Recurse -Force
    }
    & $FullPython -m venv $VenvDir
    if ((Test-Path $VenvPython) -and (Test-PythonTk $VenvPython)) {
        Write-Host "Build venv ready:"
        Write-Host $VenvPython
        exit 0
    }
}

Write-Host "Full Python with Tkinter was not found. Falling back to embeddable Python."
if (-not (Test-Path $EmbedPython)) {
    if (-not (Test-Path $Zip)) {
        Write-Host "Downloading embeddable Python $PythonVersion..."
        Invoke-WebRequest -Uri $PythonUrl -OutFile $Zip
    }

    if (Test-Path $EmbedDir) {
        Remove-Item -LiteralPath $EmbedDir -Recurse -Force
    }
    New-Item -ItemType Directory -Path $EmbedDir -Force | Out-Null
    Expand-Archive -LiteralPath $Zip -DestinationPath $EmbedDir -Force

    $pth = Get-ChildItem -LiteralPath $EmbedDir -Filter "python*._pth" | Select-Object -First 1
    if ($pth) {
        $content = Get-Content -LiteralPath $pth.FullName
        $content = $content | ForEach-Object {
            if ($_ -eq "#import site") { "import site" } else { $_ }
        }
        Set-Content -LiteralPath $pth.FullName -Encoding ASCII -Value $content
    }
}

if (-not (Test-Path (Join-Path $EmbedDir "Scripts\pip.exe"))) {
    if (-not (Test-Path $GetPip)) {
        Write-Host "Downloading pip bootstrap..."
        Invoke-WebRequest -Uri $GetPipUrl -OutFile $GetPip
    }
    Write-Host "Installing pip into embeddable Python..."
    & $EmbedPython $GetPip --no-warn-script-location
}

Write-Host "Embeddable Python ready:"
Write-Host $EmbedPython
Write-Host "Warning: embeddable Python may not include Tkinter. A full Python 3.10/3.11 install is preferred for GUI builds."
