$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$py = Get-Command py -ErrorAction SilentlyContinue
if (-not $py) { throw '未检测到 Python Launcher。请安装 Python 3.11 或 3.12，并勾选 Python Launcher。' }
$version = $null
foreach ($candidate in '3.11', '3.12') {
  & py "-$candidate" --version 2>$null
  if ($LASTEXITCODE -eq 0) { $version = $candidate; break }
}
if (-not $version) { throw '需要 Python 3.11 或 3.12。可从 https://www.python.org/downloads/windows/ 安装。' }
if (-not (Test-Path '.venv\Scripts\python.exe')) { & py "-$version" -m venv .venv }
& '.venv\Scripts\python.exe' -m pip install --upgrade pip
& '.venv\Scripts\python.exe' -m pip install -r requirements.txt
Write-Host ''
Write-Host '安装完成。双击 run.bat 启动 QQ Local Inbox。'
Write-Host '运行程序时只连接本机 WebSocket / NapCat HTTP / 本机模型端点，不会将聊天内容发送到云端。'
