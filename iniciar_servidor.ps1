param(
    [int]$Port = 8000,
    [string]$HostAddress = "0.0.0.0",
    [string]$PublicUrl = ""
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$Python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "Ambiente virtual nao encontrado em .venv\Scripts\python.exe"
}

function Get-LocalIPv4 {
    $matches = ipconfig | Select-String -Pattern '(\d{1,3}\.){3}\d{1,3}'
    foreach ($match in $matches) {
        $ip = $match.Matches[0].Value
        if ($ip -notlike "127.*" -and $ip -notlike "169.254.*" -and $ip -ne "0.0.0.0") {
            return $ip
        }
    }
    throw "Nao foi possivel detectar o IP local. Informe -PublicUrl http://IP_DO_SERVIDOR:$Port/"
}

if ([string]::IsNullOrWhiteSpace($PublicUrl)) {
    $Ip = Get-LocalIPv4
    $PublicUrl = "http://${Ip}:$Port/"
}

Write-Host ""
Write-Host "Sistema Garagem"
Write-Host "URL para funcionarios: $PublicUrl"
Write-Host "QR Code: static\qrcode-garagem.png"
Write-Host ""
Write-Host "Se celulares de outras subredes nao acessarem, libere a porta $Port no firewall do Windows e no roteamento entre VLANs/subredes."
Write-Host ""

& $Python gerar_qrcode.py --url $PublicUrl --output "static\qrcode-garagem.png" --html "static\qrcode.html"

Write-Host ""
Write-Host "Servidor iniciado. Para parar, pressione Ctrl+C."
& $Python -m uvicorn app:app --host $HostAddress --port $Port
