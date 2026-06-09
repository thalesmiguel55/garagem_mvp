# Acesso pela rede e QR Code

## Servidor

| Item | Valor |
|------|-------|
| Rede | `192.168.188.0/24` |
| IP do desktop | `192.168.188.36` |
| Porta | `7070` |
| URL principal | `http://192.168.188.36:7070/` |
| Admin | `http://192.168.188.36:7070/admin` |

## Como iniciar

No desktop servidor, abra o PowerShell nesta pasta e execute:

```powershell
.\iniciar_servidor.ps1
```

O script sobe o sistema em `0.0.0.0:7070` e gera:

- `static\qrcode-garagem.png`
- `static\qrcode.html`

## Firewall do Windows

Libere a porta `7070` no desktop servidor:

```powershell
New-NetFirewallRule `
  -DisplayName "Garagem MVP 7070" `
  -Direction Inbound `
  -Action Allow `
  -Protocol TCP `
  -LocalPort 7070 `
  -Profile Any
```

## Teste rápido

```powershell
ping 192.168.188.36
Test-NetConnection 192.168.188.36 -Port 7070
```

No celular ou PC da rede, abra:

```text
http://192.168.188.36:7070/
```

## QR Code

Depois de iniciar, abra no servidor:

```text
static\qrcode.html
```

Imprima essa página ou use a imagem `static\qrcode-garagem.png`.

## IP fixo

Configure IP fixo `192.168.188.36` no Windows ou reserva DHCP no roteador/MikroTik.