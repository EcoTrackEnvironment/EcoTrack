# Como inicializar o backend (EcoTrack API)

Guia rápido para rodar a API localmente. Para entender o que o sistema faz,
as premissas do modelo e os endpoints em detalhe, veja o [`README.md`](README.md).

## Pré-requisitos

- **Python 3.10+** (desenvolvido/testado em 3.12).
- **Internet** na primeira execução — o pipeline baixa ~1 ano de dados
  climáticos reais das APIs gratuitas Open-Meteo e NASA POWER. Depois de
  gerado, o servidor da API funciona offline (exceto a leitura de clima *ao
  vivo* do dia, que também consulta essas APIs).

Não é necessária nenhuma chave de API — Open-Meteo e NASA POWER são públicas
e gratuitas, sem cadastro.

## Passo a passo

```bash
# 1. Ambiente virtual + dependências
python3 -m venv .venv
source .venv/bin/activate        # Windows (PowerShell): .venv\Scripts\Activate.ps1

pip install -r requirements.txt

# 2. Pipeline offline (só na primeira vez — veja aviso abaixo)
python -m scripts.build_pipeline

# 3. Subir a API
uvicorn src.api:app --reload
# -> http://127.0.0.1:8000/docs   (Swagger, documentação interativa)
# -> http://127.0.0.1:8000/health (deve responder {"status":"ok",...})
```

## O passo 2 é obrigatório, não opcional

O modelo treinado (`models/climate_model.joblib`, ~28 MB) **não fica
versionado no git** (está no `.gitignore` — é um artefato binário
regenerável, não código). Os CSVs de `data/` vêm no clone normalmente, mas o
modelo em si não — é preciso rodar

```bash
python -m scripts.build_pipeline
```

**uma vez** para: (1) coletar ~1 ano de histórico climático real das APIs
para todas as células da rodovia, (2) treinar o modelo de previsão climática
e (3) gerar a previsão recursiva de 365 dias. Leva alguns minutos e precisa
de internet. Sem isso, `/variaveis-x` funciona só com clima do dia (ao vivo),
e endpoints que dependem de previsão para datas futuras (ex.: `/mapa/rodovia`
com uma data distante) respondem `503 modelo indisponível` ou `422 previsão
indisponível`.

Depois da primeira vez, os botões da API também servem para atualizar isso
sem precisar rodar o script de novo:
- `POST /historico/atualizar` — repuxa o histórico real e retreina o modelo.
- `POST /previsao/gerar` — regera os 365 dias de previsão.

## Testes de fumaça

```bash
python tests/test_smoke.py
# ou: pytest -q
```

## Problemas comuns

| Sintoma | Causa / solução |
|---|---|
| `503 modelo nao treinado` / `modelo indisponivel` | Rode `python -m scripts.build_pipeline` (passo 2). |
| Erro de rede ao rodar o pipeline | O passo 2 precisa de internet (Open-Meteo + NASA POWER). Tente de novo — falha total de rede faz a coleta falhar em vez de inventar dados. |
| Porta 8000 ocupada | `uvicorn src.api:app --reload --port 8001` (ajuste o `API` no frontend de acordo, veja [`COMO-CONECTAR.md`](COMO-CONECTAR.md)). |
| `ModuleNotFoundError` | Confirme que o `.venv` está ativado (`(.venv)` no início da linha do terminal) e que `pip install -r requirements.txt` rodou sem erro. |
