$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Entry = Join-Path $Root "tools\restaurant_bot.py"
$Dist = Join-Path $Root "dist\restaurant_bot_for_users"
$Work = Join-Path $Root "build\restaurant_bot"
$Spec = Join-Path $Root "build"
$Requirements = Join-Path $Root "requirements-restaurant.txt"
$TempDir = Join-Path $Root ".tools\tmp"
$PreferredLocalPython = Join-Path $Root ".tools\restaurant-build-venv\Scripts\python.exe"
$FallbackLocalPython = Join-Path $Root ".tools\python-build\python.exe"
$LocalPython = if (Test-Path $PreferredLocalPython) {
    $PreferredLocalPython
} elseif (Test-Path $FallbackLocalPython) {
    $FallbackLocalPython
} else {
    Get-ChildItem -Path (Join-Path $Root ".tools") -Recurse -Filter python.exe -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -match "\\python-[^\\]+\\python.exe$" } |
    Select-Object -First 1 -ExpandProperty FullName
}

if (-not (Test-Path $Entry)) {
    throw "Entry file not found: $Entry"
}

function Invoke-PythonCommand {
    param(
        [string[]]$CommandParts,
        [string[]]$PythonArgs
    )
    $cmd = $CommandParts[0]
    $prefix = @()
    if ($CommandParts.Count -gt 1) {
        $prefix = $CommandParts[1..($CommandParts.Count - 1)]
    }
    & $cmd @prefix @PythonArgs
}

function Test-PythonCommand {
    param([string[]]$CommandParts)
    try {
        $result = Invoke-PythonCommand $CommandParts @("-c", "import sys; print(sys.executable)") 2>$null
        return ($LASTEXITCODE -eq 0 -and $result)
    } catch {
        return $false
    }
}

function Resolve-PythonCommand {
    if ($env:PYTHON_EXE) {
        $candidate = @($env:PYTHON_EXE)
        if (Test-PythonCommand $candidate) {
            return $candidate
        }
    }

    if ($LocalPython) {
        $candidate = @($LocalPython)
        if (Test-PythonCommand $candidate) {
            return $candidate
        }
    }

    foreach ($cmd in @("python", "python3")) {
        if (Get-Command $cmd -ErrorAction SilentlyContinue) {
            $candidate = @($cmd)
            if (Test-PythonCommand $candidate) {
                return $candidate
            }
        }
    }

    if (Get-Command py -ErrorAction SilentlyContinue) {
        foreach ($arg in @("-3.13", "-3", "")) {
            $candidate = if ($arg) { @("py", $arg) } else { @("py") }
            if (Test-PythonCommand $candidate) {
                return $candidate
            }
        }
    }

    throw "No usable Python was found. Run scripts\setup_restaurant_build_env.ps1, install Python 3, or set PYTHON_EXE to python.exe."
}

$PythonCommand = Resolve-PythonCommand
Write-Host ("Using Python: " + ($PythonCommand -join " "))
Invoke-PythonCommand $PythonCommand @("--version")
if ($LASTEXITCODE -ne 0) {
    throw "Python version check failed."
}

New-Item -ItemType Directory -Path $TempDir -Force | Out-Null
$env:TEMP = $TempDir
$env:TMP = $TempDir
$env:PIP_NO_CACHE_DIR = "1"

if (Test-Path $Requirements) {
    Write-Host "Installing / checking build dependencies..."
    Invoke-PythonCommand $PythonCommand @("-m", "pip", "install", "-r", $Requirements)
    if ($LASTEXITCODE -ne 0) {
        throw "Dependency installation failed."
    }
}

if (Test-Path $Dist) {
    Remove-Item -LiteralPath $Dist -Recurse -Force
}

$pyInstallerArgs = @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--onefile",
    "--windowed",
    "--name", "restaurant_bot",
    "--distpath", $Dist,
    "--workpath", $Work,
    "--specpath", $Spec,
    "--hidden-import", "winsdk.windows.media.ocr",
    "--hidden-import", "winsdk.windows.globalization",
    "--hidden-import", "winsdk.windows.graphics.imaging",
    "--hidden-import", "winsdk.windows.storage.streams",
    $Entry
)
Invoke-PythonCommand $PythonCommand $pyInstallerArgs
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed."
}

$Exe = Join-Path $Dist "restaurant_bot.exe"
if (-not (Test-Path $Exe)) {
    throw "Build finished but exe was not found: $Exe"
}

$ReleaseBase = -join ([char[]](0x6469, 0x723E, 0x838A, 0x5712, 0x8F14, 0x52A9))
$ReleaseName = "$ReleaseBase.exe"
$ReleaseExe = Join-Path $Dist $ReleaseName
if (Test-Path $ReleaseExe) {
    Remove-Item -LiteralPath $ReleaseExe -Force
}
Rename-Item -LiteralPath $Exe -NewName $ReleaseName
$Exe = $ReleaseExe

Write-Host "Package created:"
Write-Host $Exe
Write-Host "Give users only $ReleaseName."
