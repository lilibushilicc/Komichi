<#
.SYNOPSIS
    Komichi crawler-daemon + Cloudflare Tunnel 一键启动脚本
.DESCRIPTION
    1. 启动 crawler-daemon (FastAPI, port 8788)
    2. 启动 cloudflared quick tunnel，暴露 8788 到公网
    3. 自动提取隧道 URL，通过 CLI 更新 Worker 的 VPS_URL（无需重新部署）
    4. 监控两个进程，任一退出则自动重启
    5. 支持 Ctrl+C 优雅退出
.NOTES
    首次运行前确保:
    - cloudflared.exe 已下载到 .trae-cn\work\<session>\cloudflared.exe 或 PATH 中
    - crawler-daemon 依赖已安装 (pip install -r crawler-daemon/requirements.txt)
    - CLI 已配置 worker_url / username / password (komichi-cli init)
#>

[CmdletBinding()]
param(
    [string]$CrawlerDir = "$PSScriptRoot\crawler-daemon",
    [string]$CloudflaredPath = "",
    [int]$Port = 8788,
    [int]$RestartDelay = 5
)

$ErrorActionPreference = "Stop"

# ---- 定位 cloudflared.exe ----
if (-not $CloudflaredPath -or -not (Test-Path $CloudflaredPath)) {
    $candidates = @(
        (Get-Command cloudflared.exe -ErrorAction SilentlyContinue)?.Source,
        (Get-ChildItem "$env:USERPROFILE\.trae-cn\work" -Recurse -Filter "cloudflared.exe" -ErrorAction SilentlyContinue | Select-Object -First 1)?.FullName
    ) | Where-Object { $_ }
    $CloudflaredPath = $candidates | Select-Object -First 1
    if (-not $CloudflaredPath) {
        Write-Host "[X] 未找到 cloudflared.exe，请下载或指定 -CloudflaredPath" -ForegroundColor Red
        Write-Host "    下载: https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
        exit 1
    }
}
Write-Host "[i] cloudflared: $CloudflaredPath" -ForegroundColor Cyan

# ---- 定位 Python ----
$python = (Get-Command python -ErrorAction SilentlyContinue)?.Source
if (-not $python) {
    Write-Host "[X] 未找到 python" -ForegroundColor Red
    exit 1
}
Write-Host "[i] python: $python" -ForegroundColor Cyan

# ---- 状态变量 ----
$script:running = $true
$script:crawlerProc = $null
$script:tunnelProc = $null
$script:currentTunnelUrl = ""

# ---- 提取隧道 URL 的正则 ----
$tunnelUrlRegex = 'https://[a-z0-9-]+\.trycloudflare\.com'

function Start-CrawlerDaemon {
    <# 启动 crawler-daemon，返回进程对象 #>
    Write-Host "`n[*] 启动 crawler-daemon (port $Port)..." -ForegroundColor Yellow
    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = $python
    $psi.Arguments = "-m komichi_crawler serve --host 0.0.0.0 --port $Port"
    $psi.WorkingDirectory = $CrawlerDir
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    $proc = [System.Diagnostics.Process]::new($psi)
    $proc.EnableRaisingEvents = $true
    # 输出重定向
    $null = Register-ObjectEvent -InputObject $proc -EventName "OutputDataReceived" -SourceIdentifier "crawler-stdout" -Action {
        if ($EventArgs.Data) { Write-Host "  [crawler] $($EventArgs.Data)" -ForegroundColor DarkGray }
    }
    $null = Register-ObjectEvent -InputObject $proc -EventName "ErrorDataReceived" -SourceIdentifier "crawler-stderr" -Action {
        if ($EventArgs.Data) { Write-Host "  [crawler] $($EventArgs.Data)" -ForegroundColor DarkYellow }
    }
    $null = $proc.Start()
    $proc.BeginOutputReadLine()
    $proc.BeginErrorReadLine()
    Write-Host "[OK] crawler-daemon PID=$($proc.Id)" -ForegroundColor Green
    return $proc
}

function Start-Tunnel {
    <# 启动 cloudflared tunnel，返回进程对象。自动提取隧道 URL。 #>
    Write-Host "`n[*] 启动 Cloudflare Tunnel..." -ForegroundColor Yellow
    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = $CloudflaredPath
    $psi.Arguments = "tunnel --url http://localhost:$Port"
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    $proc = [System.Diagnostics.Process]::new($psi)
    $proc.EnableRaisingEvents = $true

    $tunnelFound = $false
    $null = Register-ObjectEvent -InputObject $proc -EventName "ErrorDataReceived" -SourceIdentifier "tunnel-stderr" -Action {
        $line = $EventArgs.Data
        if (-not $line) { return }
        Write-Host "  [tunnel] $line" -ForegroundColor DarkGray
        # 匹配隧道 URL
        if ($line -match 'https://[a-z0-9-]+\.trycloudflare\.com') {
            $script:currentTunnelUrl = $Matches[0]
            Write-Host ""
            Write-Host "[OK] Tunnel URL: $($script:currentTunnelUrl)" -ForegroundColor Green
        }
    }
    $null = Register-ObjectEvent -InputObject $proc -EventName "OutputDataReceived" -SourceIdentifier "tunnel-stdout" -Action {
        if ($EventArgs.Data) { Write-Host "  [tunnel] $($EventArgs.Data)" -ForegroundColor DarkGray }
    }

    $null = $proc.Start()
    $proc.BeginOutputReadLine()
    $proc.BeginErrorReadLine()
    Write-Host "[OK] cloudflared PID=$($proc.Id)" -ForegroundColor Green
    return $proc
}

function Update-WorkerVpsUrl {
    <# 等待隧道 URL 就绪后，通过 CLI 更新 Worker 的 VPS_URL #>
    Write-Host "`n[*] 等待隧道 URL 就绪..." -ForegroundColor Yellow
    $waited = 0
    while (-not $script:currentTunnelUrl -and $waited -lt 30) {
        Start-Sleep -Seconds 1
        $waited++
    }
    if (-not $script:currentTunnelUrl) {
        Write-Host "[!] 30秒内未检测到隧道 URL，跳过自动更新" -ForegroundColor Red
        Write-Host "    请手动执行: komichi-cli config set-vps-url <tunnel-url>" -ForegroundColor Yellow
        return
    }
    Write-Host "[*] 更新 Worker VPS_URL -> $($script:currentTunnelUrl)..." -ForegroundColor Yellow
    try {
        $output = & komichi-cli config set-vps-url $script:currentTunnelUrl 2>&1
        Write-Host "[OK] $output" -ForegroundColor Green
    } catch {
        Write-Host "[!] CLI 更新失败: $_" -ForegroundColor Red
        Write-Host "    请手动执行: komichi-cli config set-vps-url $($script:currentTunnelUrl)" -ForegroundColor Yellow
    }
}

function Stop-ProcessGraceful {
    param([System.Diagnostics.Process]$proc, [string]$name)
    if ($proc -and -not $proc.HasExited) {
        Write-Host "[*] 停止 $name (PID=$($proc.Id))..." -ForegroundColor Yellow
        try {
            $proc.Kill()
            $proc.WaitForExit(5000)
        } catch {}
    }
}

# ---- 清理事件 ----
function Cleanup-Events {
    @("crawler-stdout", "crawler-stderr", "tunnel-stdout", "tunnel-stderr") | ForEach-Object {
        Unregister-Event -SourceIdentifier $_ -ErrorAction SilentlyContinue
    }
}

# ---- Ctrl+C 处理 ----
[Console]::TreatControlCAsInput = $false
$null = Register-EngineEvent -SourceIdentifier "PowerShell.Exiting" -Action {
    $script:running = $false
}

# ============================================================
# 主循环
# ============================================================
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Komichi Crawler + Tunnel Launcher" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " crawler-daemon: $CrawlerDir"
Write-Host " port:           $Port"
Write-Host " cloudflared:    $CloudflaredPath"
Write-Host " 按 Ctrl+C 退出"
Write-Host ""

$tunnelUrlUpdated = $false

while ($script:running) {
    # 1. 启动/重启 crawler-daemon
    if (-not $script:crawlerProc -or $script:crawlerProc.HasExited) {
        if ($script:crawlerProc -and $script:crawlerProc.HasExited) {
            Write-Host "[!] crawler-daemon 已退出 (exit=$($script:crawlerProc.ExitCode))，${RestartDelay}秒后重启..." -ForegroundColor Red
            Start-Sleep -Seconds $RestartDelay
        }
        $script:crawlerProc = Start-CrawlerDaemon
    }

    # 2. 启动/重启 tunnel
    if (-not $script:tunnelProc -or $script:tunnelProc.HasExited) {
        if ($script:tunnelProc -and $script:tunnelProc.HasExited) {
            Write-Host "[!] cloudflared 已退出 (exit=$($script:tunnelProc.ExitCode))，${RestartDelay}秒后重启..." -ForegroundColor Red
            Start-Sleep -Seconds $RestartDelay
        }
        $script:currentTunnelUrl = ""
        $tunnelUrlUpdated = $false
        $script:tunnelProc = Start-Tunnel
    }

    # 3. 隧道 URL 就绪后自动更新 Worker
    if (-not $tunnelUrlUpdated -and $script:currentTunnelUrl) {
        Update-WorkerVpsUrl
        $tunnelUrlUpdated = $true
    }

    # 4. 监控循环（每 2 秒检查一次）
    Start-Sleep -Seconds 2
}

# ---- 退出清理 ----
Write-Host "`n[*] 正在停止所有服务..." -ForegroundColor Yellow
Stop-ProcessGraceful $script:tunnelProc "cloudflared"
Stop-ProcessGraceful $script:crawlerProc "crawler-daemon"
Cleanup-Events
Write-Host "[OK] 已退出" -ForegroundColor Green
