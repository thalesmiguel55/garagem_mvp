# Garagem MVP

Aplicacao FastAPI para controle de entrada e saida de veiculos com interface web, upload de fotos e notificacoes via Telegram.

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
uvicorn app:app --host 0.0.0.0 --port 8000
```

Acesse `http://localhost:8000`.
