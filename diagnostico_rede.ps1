param(
    [string]$ServerIp = "192.168.88.249",
    [int[]]$Ports = @(8000, 80, 8080)
)

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "Diagnostico de acesso ao Garagem MVP"
Write-Host "Executar este script em um PC/celular na rede 192.168.88.x"
Write-Host ""

$ip = Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.IPAddress -like "192.168.*" -and $_.PrefixOrigin -ne "WellKnown" } |
    Select-Object -First 1

if ($ip) {
    Write-Host "IP local detectado: $($ip.IPAddress)"
} else {
    Write-Host "IP local detectado: (nao encontrado)"
}

Write-Host "Servidor alvo: $ServerIp"
Write-Host ""

Write-Host "1) Teste de ping"
$ping = Test-Connection -ComputerName $ServerIp -Count 2 -Quiet
if ($ping) {
    Write-Host "   OK - ping respondeu" -ForegroundColor Green
} else {
    Write-Host "   FALHA - sem rota ate o servidor" -ForegroundColor Red
    Write-Host "   Verifique se o servidor esta ativo em 192.168.88.249 e se a rede local tem rota ate ele"
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
Write-Host "Se ping OK e portas falharem, o firewall/roteador esta bloqueando as portas entre VLANs."
Write-Host "Se tudo falhar, nao existe rota da rede 88 para a rede 90."
Write-Host ""