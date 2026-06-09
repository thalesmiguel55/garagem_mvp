param(
    [int]$Port = 7070,
    [string]$HostAddress = "0.0.0.0",
    [string]$PublicUrl = ""
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$DefaultServerIp = "192.168.188.36"
$Python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "Ambiente virtual nao encontrado em .venv\Scripts\python.exe"
}

function Get-LocalIPv4 {
    $ips = @()
    $matches = ipconfig | Select-String -Pattern '(\d{1,3}\.){3}\d{1,3}'
    foreach ($match in $matches) {
        $ip = $match.Matches[0].Value
        if ($ip -notlike "127.*" -and $ip -notlike "169.254.*" -and $ip -ne "0.0.0.0") {
            $ips += $ip
        }
    }

    $preferred = $ips | Where-Object { $_ -like "192.168.188.*" } | Select-Object -First 1
    if ($preferred) { return $preferred }

    if ($ips.Count -gt 0) { return $ips[0] }
    return $DefaultServerIp
}

if ([string]::IsNullOrWhiteSpace($PublicUrl)) {
    $Ip = Get-LocalIPv4
    $PublicUrl = "http://${Ip}:$Port/"
}

Write-Host ""
Write-Host "Sistema Garagem"
Write-Host "URL para funcionarios: $PublicUrl"
Write-Host "Admin: http://$($Ip):$Port/admin"
Write-Host "QR Code: static\qrcode-garagem.png"
Write-Host ""
Write-Host "Servidor configurado para 192.168.188.36 na porta $Port"
Write-Host ""

& $Python gerar_qrcode.py --url $PublicUrl --output "static\qrcode-garagem.png" --html "static\qrcode.html"

Write-Host ""
Write-Host "Servidor iniciado. Para parar, pressione Ctrl+C."
& $Python -m uvicorn app:app --host $HostAddress --port $Port