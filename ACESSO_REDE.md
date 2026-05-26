# Acesso pela rede e QR Code

## Como iniciar

No servidor, abra o PowerShell nesta pasta e execute:

```powershell
.\iniciar_servidor.ps1
```

O script sobe o sistema em `0.0.0.0:8000`, detecta o IP local e gera:

- `static\qrcode-garagem.png`
- `static\qrcode.html`

Pelo IP atual detectado nesta maquina, a URL esperada e:

```text
http://192.168.90.23:8000/
```

## QR Code

Depois de iniciar, abra no servidor:

```text
static\qrcode.html
```

Imprima essa pagina ou use a imagem `static\qrcode-garagem.png`.

## Subredes e Wi-Fi

Para funcionarios em outras subredes/VLANs/Wi-Fi acessarem, a rede precisa permitir rota ate o servidor na porta `8000`.

No Windows Firewall do servidor, libere entrada TCP na porta `8000`. Em PowerShell como Administrador:

```powershell
New-NetFirewallRule -DisplayName "Garagem MVP 8000" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8000
```

Se a empresa tiver VLANs separadas, o roteador/firewall tambem precisa permitir origem das redes dos funcionarios para `192.168.90.23:8000`.

## IP fixo

Para o QR Code continuar funcionando, configure IP fixo ou reserva DHCP para o servidor. Se o IP mudar, rode o script novamente e reimprima o QR Code.
