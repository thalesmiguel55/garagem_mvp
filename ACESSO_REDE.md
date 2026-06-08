# Acesso pela rede e QR Code

## Rede do servidor

| Item | Valor |
|------|-------|
| Rede | `192.168.88.0/24` |
| Gateway | `192.168.88.1` |
| IP do servidor | `192.168.88.249` |
| Porta | `8000` |
| URL principal | `http://192.168.88.249:8000/` |
| Admin | `http://192.168.88.249:8000/admin` |

## Como iniciar

No servidor, abra o PowerShell nesta pasta e execute:

```powershell
.\iniciar_servidor.ps1
```

O script sobe o sistema em `0.0.0.0:8000`, usa o IP `192.168.88.249` e gera:

- `static\qrcode-garagem.png`
- `static\qrcode.html`

## Quem acessa de onde

| Origem | URL |
|--------|-----|
| Rede `192.168.88.x` | `http://192.168.88.249:8000/` |
| Rede `192.168.90.x` | `http://192.168.88.249:8000/` |

Funcionários na rede `88` acessam diretamente, sem rota entre VLANs.

Se alguém estiver na rede `192.168.90.x`, a equipe de rede precisa permitir acesso de `192.168.90.0/24` para `192.168.88.249` na porta TCP `8000`.

## Firewall do Windows

Regra recomendada:

```powershell
New-NetFirewallRule `
  -DisplayName "Garagem MVP - Subredes" `
  -Direction Inbound `
  -Action Allow `
  -Protocol TCP `
  -LocalPort 8000 `
  -RemoteAddress "192.168.88.0/24","192.168.90.0/24" `
  -Profile Any
```

## Teste rápido

```powershell
ping 192.168.88.249
Test-NetConnection 192.168.88.249 -Port 8000
```

No celular ou PC da rede 88, abra:

```text
http://192.168.88.249:8000/
```

## QR Code

Depois de iniciar, abra no servidor:

```text
static\qrcode.html
```

Imprima essa página ou use a imagem `static\qrcode-garagem.png`.

## IP fixo

O servidor deve permanecer fixo em `192.168.88.249` (configuração estática no Windows ou reserva DHCP no MikroTik).

Se o IP mudar, rode o script novamente e reimprima o QR Code.