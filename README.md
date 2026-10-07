# Agente Macro — POC

Aplicação experimental em Python que consulta séries do SGS/Banco Central, solicita à API Groq a elaboração de um relatório ilustrativo e apresenta o resultado em uma página web.

> **Aviso:** o relatório é informativo e hipotético. Não constitui recomendação financeira nem garantia de resultados.

## Como funciona

- `agente.py` consulta as séries SGS 1 e 433 e solicita o relatório à Groq.
- `web.py` fornece a página web e o endpoint protegido que executa o agente.
- `Relatorio_Estresse_Patrimonial.md` contém o relatório de exemplo incluído no repositório.

A cada solicitação, o serviço gera um novo relatório. O arquivo temporário produzido durante a execução não é armazenamento permanente.

## Requisitos

- Python 3.11 ou superior
- Chave de API da Groq
- Acesso à internet para consultar o SGS/Banco Central e a API Groq

## Executar localmente

No diretório do projeto:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Crie `.env` na raiz do projeto:

```dotenv
GROQ_API_KEY=sua_chave_groq
APP_TOKEN=seu_token_forte
```

Não compartilhe esses valores nem envie o `.env` ao GitHub. Gere um token forte, por exemplo:

```bash
openssl rand -hex 32
```

Inicie o servidor:

```bash
flask --app web run --host 0.0.0.0 --port 5000
```

Abra <http://localhost:5000>, informe o valor de `APP_TOKEN` e clique em **Gerar relatório**.

Também é possível executar somente o agente:

```bash
python agente.py
```

## API

- `GET /` — página web.
- `GET /health` — verificação de saúde do serviço.
- `POST /generate` — executa o agente; requer autenticação Bearer com `APP_TOKEN`.

Exemplo:

```bash
curl -X POST "http://localhost:5000/generate" \
  -H "Authorization: Bearer SEU_APP_TOKEN"
```

## Deploy no Render

Crie um **Web Service** conectado ao repositório e configure:

- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `gunicorn web:app --bind 0.0.0.0:$PORT`

Adicione em **Environment** as variáveis:

- `GROQ_API_KEY` — chave da API Groq.
- `APP_TOKEN` — token forte usado para proteger a geração do relatório.

Não coloque segredos no código ou no repositório. Se uma chave for exposta, revogue-a e gere outra.

## Arquivos principais

- `agente.py` — consulta ao SGS e geração do relatório via Groq.
- `web.py` — interface web e endpoint de geração.
- `requirements.txt` — dependências Python.
- `.gitignore` — exclui arquivos locais e segredos, como `.env`.

## Limitações

Os dados consultados e as respostas de modelos de linguagem podem ter limitações. Projeções dependem de premissas e não devem ser interpretadas como previsões garantidas ou aconselhamento financeiro.