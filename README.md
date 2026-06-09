# Garagem MVP

Aplicacao FastAPI para controle de entrada e saida de veiculos com interface web, upload de fotos e notificacoes via Telegram.

## Servidor local

| Item | Valor |
|------|-------|
| IP | `192.168.188.36` |
| Porta | `7070` |
| URL | `http://192.168.188.36:7070/` |
| Admin | `http://192.168.188.36:7070/admin` |

## Requisitos

- Python 3.11+
- Dependencias em `requirements.txt`

## Configuracao

1. Crie um ambiente virtual.
2. Instale as dependencias:

```powershell
pip install -r requirements.txt
```

3. Copie `config.example.json` para `config.json` e preencha o token e chat ID do Telegram.

## Execucao

```powershell
.\iniciar_servidor.ps1
```

Ou manualmente:

```powershell
uvicorn app:app --host 0.0.0.0 --port 7070
```

Acesse `http://192.168.188.36:7070/`.

Mais detalhes de rede em `ACESSO_REDE.md`.