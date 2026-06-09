param(
    [string]$ServerIp = "192.168.188.36",
    [int[]]$Ports = @(7070)
)

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "Diagnostico de acesso ao Garagem MVP"
Write-Host "Servidor alvo: $ServerIp"
Write-Host ""

$ip = Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.IPAddress -like "192.168.*" -and $_.PrefixOrigin -ne "WellKnown" } |
    Select-Object -First 1

if ($ip) {
    Write-Host "IP local detectado: $($ip.IPAddress)"
} else {
    Write-Host "IP local detectado: (nao encontrado)"
}

Write-Host ""
Write-Host "1) Teste de ping"
$ping = Test-Connection -ComputerName $ServerIp -Count 2 -Quiet
if ($ping) {
    Write-Host "   OK - ping respondeu" -ForegroundColor Green
} else {
    Write-Host "   FALHA - sem rota ate o servidor" -ForegroundColor Red
}

Write-Host ""
Write-Host "2) Teste de portas HTTP"
foreach ($port in $Ports) {
    $test = Test-NetConnection -ComputerName $ServerIp -Port $port -WarningAction SilentlyContinue
    if ($test.TcpTestSucceeded) {
        Write-Host "   OK - TCP $port aberta -> http://${ServerIp}:$port/" -ForegroundColor Green
    } else {
        Write-Host "   FALHA - TCP $port bloqueada" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "3) Teste HTTP"
foreach ($port in $Ports) {
    $url = "http://${ServerIp}:$port/"
    try {
        $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5
        Write-Host "   OK - $url respondeu $($response.StatusCode)" -ForegroundColor Green
    } catch {
        Write-Host "   FALHA - $url" -ForegroundColor Red
    }
}

Write-Host ""