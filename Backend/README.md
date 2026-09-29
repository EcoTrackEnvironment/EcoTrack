# EcoTrack — Backend

Sistema de **monitoramento preditivo de crescimento de grama** para orientar as
equipes de corte da **CCR Motiva** sobre *onde* e *quando* cortar a vegetação
nas margens do **Rodoanel Mário Covas (SP-021)**.

O backend calcula e expõe, via API, as **Variáveis X** — a **altura estimada da
grama (cm)** em pontos da rodovia e a **confiança** dessa estimativa. A altura
vem de uma **fórmula agronômica** alimentada com clima **real** (histórico das
APIs) e com o clima **futuro previsto por um modelo de machine learning**
treinado offline com 1 ano de dados reais.

---

## 1. Visão geral do fluxo

```
APIs gratuitas (Open-Meteo arquivo + NASA POWER)
        │  (até 1 ano de dados diários, todas as células climáticas da rodovia)
        ▼
data/climate_history.csv ──► Treino (src/train.py) ──► Modelo de PREVISÃO CLIMÁTICA
        │                                                      │
        │ (dias passados: dado real)        (dias futuros: clima previsto)
        ▼                                                      ▼
   Fórmula agronômica (src/growth.py): acumula a taxa diária de crescimento
        │
        ▼
   altura_cm + confiança  ──►  API /variaveis-x e /mapa/rodovia
```

1. **Coleta**: a API puxa **até 1 ano** de dados climáticos diários das APIs
   gratuitas (seção 2) para **todas as células climáticas** da rodovia e guarda
   em `data/climate_history.csv` (seção 3).
2. **Treino** de um **Random Forest multi-saída** que prevê as **variáveis
   climáticas de dias que ainda não vieram** (seção 5).
3. **Altura da grama**: calculada pela **fórmula agronômica** (seção 4),
   acumulando dia a dia a taxa de crescimento — clima real para o passado,
   clima previsto pelo modelo para o futuro.
4. **API** que expõe as Variáveis X no formato JSON pedido (seção 6).

---

## 2. APIs externas utilizadas (somente **Gratuitas**)

| Fonte | Uso no projeto | Variáveis | Custo |
|-------|----------------|-----------|-------|
| **Open-Meteo** (forecast) | Clima ao vivo do dia | temperatura, precipitação, umidade, vento | Gratuito |
| **Open-Meteo** (archive/ERA5) | Histórico de até 1 ano (dataset de treino) | temperatura, precipitação, umidade, vento | Gratuito |
| **NASA POWER** | Radiação solar (ao vivo e histórico) | radiação solar global (GHI, ~PAR) | Gratuito |

**Fontes deliberadamente NÃO usadas:**
- *Pagas*: AccuWeather for Business, IBM Environmental Intelligence Suite.
- *Freemium com chave obrigatória*: WeatherAPI, Solcast — exigem API key,
  então ficaram fora do escopo "gratuito sem chave" do MVP.
- INPE Queimadas, Cemaden e Google Earth Engine são gratuitas e podem ser
  integradas em evolução futura (o PDF as cita como ajustes de "reset" por fogo,
  umidade do solo e NDVI); o MVP segue a recomendação do próprio documento:
  **Open-Meteo + NASA POWER**.

**Frequência de atualização:** diária (as APIs são consultadas por dia solicitado).

### Tratamento de erro de API (**por variável**, sem climatologia sintética)
A leitura ao vivo (`src/ingest.py`) parte da **previsão do próprio modelo**
para o dia (ou do histórico real, se o dia já foi coletado) e **sobrescreve
cada variável** com o valor real que a API correspondente entregar:

- Open-Meteo → temperatura, precipitação, umidade, vento
- NASA POWER → radiação solar

Assim, a base do modelo é usada **apenas nas variáveis que a API não
forneceu**. Exemplo real: a NASA POWER publica a radiação com alguns dias de
defasagem, então para a data de *hoje* a radiação vem da previsão do modelo
enquanto as demais variáveis vêm reais do Open-Meteo — resultando em
`fonte_clima = "open-meteo+modelo-clima(radiacao_mj_m2)"`. Uma falha total de
rede degrada para `modelo-clima` (todas as variáveis); sem previsão gerada e
sem APIs, a leitura falha pedindo para gerar a previsão. A resposta traz, em
`clima.fontes`, a origem de **cada** variável
(`open-meteo` | `nasa-power` | `modelo-clima` | `historico-real`).

---

## 3. Histórico climático real (dataset de treino)

Arquivo: `data/climate_history.csv` — **~7.300 amostras reais** (365 dias ×
20 células climáticas), coletado por `src/historico.py`.

Como a resolução espacial das APIs de clima é de ~11 km (muito maior que os
200 m entre células do mapa), as coordenadas das células são agrupadas em
**células climáticas** numa grade de ~0.1° — todas as células do mapa ficam
cobertas sem baixar o mesmo dado centenas de vezes. Para cada célula climática
são feitas **duas chamadas** (uma por API, ambas aceitam intervalos de datas)
cobrindo **1 ano** de dados diários.

Colunas:

| Coluna | Descrição |
|--------|-----------|
| `data` | dia da leitura |
| `latitude`, `longitude` | célula climática (~11 km) |
| `temperatura_c` | temperatura média do ar (°C) |
| `precipitacao_mm` | precipitação diária (mm) |
| `umidade_pct` | umidade relativa média (%) |
| `radiacao_mj_m2` | radiação solar global (MJ/m²/dia) |
| `vento_kmh` | velocidade máxima do vento (km/h) |
| `variaveis_reais` | quantas das 5 variáveis vieram direto das APIs |

Dias/variáveis que as APIs não entregarem são preenchidos por **interpolação
dos dias reais vizinhos** da própria célula (sem climatologia sintética),
mantendo o CSV completo para o treino. Se uma variável não vier de jeito
nenhum para uma célula, a coleta **falha** em vez de inventar dados.

---

## 4. Modelo agronômico de crescimento (calcula a altura servida)

Como não existem séries reais de crescimento, a relação clima → crescimento é
dada por um modelo agronômico (`src/growth.py`) — é **ele** que calcula a
altura exposta pela API, alimentado com o clima de **cada dia** da janela desde
o corte (real no passado, previsto pelo modelo no futuro).

As cinco espécies **convivem no mesmo trecho** (é assim no campo: crescem
juntas, misturadas). Por isso cada célula do mapa é simulada para as cinco, e
**cada espécie tem seu próprio cálculo** — não apenas uma taxa base diferente
multiplicando as mesmas curvas.

**Parâmetros por espécie:**

| Espécie | Taxa base (cm/dia) | T ótima / mín / máx (°C) | Forma da curva térmica | Kc | Raiz (mm) | p (esgot.) | k radiação | Altura máx (cm) |
|---------|-----|-----|-----|-----|-----|-----|-----|-----|
| Brachiaria (Urochloa) | 4.2 | 30 / 12 / 42 | 1.7 | 0.95 | 900 | 0.55 | 11 | 90 |
| Cynodon (grama-seda) | 1.5 | 28 / 10 / 41 | 1.4 | 0.85 | 1300 | 0.65 | 14 | 45 |
| Megathyrsus (capim-colonião) | 9.5 | 31 / 13 / 43 | 2.1 | 1.15 | 1100 | 0.45 | 8 | 180 |
| Pennisetum (capim-elefante) | 14.5 | 32 / 14 / 43 | 2.3 | 1.25 | 1000 | 0.40 | 9 | 250 |
| Paspalum (grama-batatais) | 1.1 | 27 / 11 / 40 | 1.2 | 0.75 | 1500 | 0.70 | 10 | 40 |

(mais os parâmetros de dossel e acamamento, documentados em `src/config.py`.)

**A simulação carrega estado dia a dia** — água no solo e altura do dossel:

1. **Água entra** no reservatório do solo (chuva; o excedente escoa). O
   tamanho do reservatório é `prof_raiz × água disponível do solo`, então
   espécie de raiz mais funda atravessa veranico melhor.
2. **Água sai** por evapotranspiração: ET0 de referência por **Penman-Monteith
   (FAO-56)**, calculada com temperatura, umidade, radiação e vento, mais a
   altitude da RMSP. Cada espécie consome `Ks × Kc × ET0`.
3. **Estresse hídrico** `Ks` (FAO-56): sem estresse enquanto a espécie não
   esgota a fração `p` do reservatório; depois cai linearmente até o ponto de
   murcha.
4. **Temperatura** — beta normalizada de Yan & Hunt: vale 1 exatamente em
   `T_ótima`, zero nos cardeais; o expoente controla a largura (espécie rústica
   = curva larga, tropical exigente = pico estreito).
5. **Radiação** — Michaelis-Menten com meia-saturação **própria de cada
   espécie** (tolerância à sombra).
6. **Dossel** — fração de luz interceptada por Beer-Lambert sobre o IAF, que
   cresce com a altura. É o que produz a rebrota lenta logo após o corte.
7. **Vento** — penalidade **mecânica** de acamamento, proporcional à altura
   atual (capim alto tomba, gramado rasteiro não). O efeito evaporativo do
   vento já está no ET0; contar de novo seria dupla contagem.

**Incremento diário:**
```
Δaltura = taxa_base × f_temp × Ks × f_radiação × f_dossel × f_vento × (1 − (h/h_máx)^ν)
```

Como o incremento diário é não-negativo, a altura **nunca diminui** ao alargar
o horizonte de projeção. Todas as constantes são estimativas de engenharia
calibradas para gerar alturas realistas; **não substituem medições reais**.

### De onde vem o estado inicial (altura no corte + data do corte)

A simulação precisa de um ponto de partida, e ele **não é mais uma premissa do
código**: vem do banco operacional (`src/db.py`, SQLite em
`data/ecotrack.db`), alimentado pela tela **Registro de Cortes** do painel.

Cada registro guarda **quando** a roçada aconteceu e **a que altura a grama
ficou**, em um de dois escopos:

| Escopo | Abrangência | Uso típico |
|--------|-------------|-----------|
| `global` | rodovia inteira | roçada geral do anel |
| `ponto`  | dentro de `raio_influencia_m` da coordenada | trecho roçado isoladamente |

A base já sobe semeada com o corte de referência desta operação: **toda a
rodovia cortada a 2 cm em 07/08/2026**.

A tabela é um **histórico append-only** — registrar não sobrescreve nada.
A resolução (`corte_vigente`) escolhe, para cada célula, o registro que a
alcança com a `data_corte` mais recente; empatando a data, vence o de escopo
`ponto` (mais específico); persistindo o empate, o gravado por último. Apagar
um registro faz o anterior voltar a valer naquele trecho.

Consequência no mapa: cada célula tem a **sua** janela de crescimento
(`[corte + 1 dia, data-alvo]`) e parte da **sua** altura de corte. Trechos
roçados em datas diferentes aparecem com alturas diferentes na mesma varredura
— que é o retrato operacional que se quer.

**Consequências que o modelo reproduz** (verificadas em `tests/test_smoke.py`):
no verão úmido o porte manda (elefante e colonião disparam); no inverno as
espécies de clima ameno lideram e o capim-elefante quase para; num veranico
prolongado a ordem se inverte — o Cynodon ultrapassa a Brachiaria, e a
grama-batatais preserva mais do que o dobro do seu potencial em relação ao
capim-elefante.

---

## 5. Modelo de machine learning (previsão climática)

**Papel do modelo:** descobrir o **clima do dia seguinte analisando os climas
já passados** (temperatura, precipitação, umidade, radiação e vento), para
qualquer célula climática da rodovia. A altura da grama **não** é prevista por
ML — ela é calculada pela fórmula da seção 4 usando o clima real (passado) e o
clima previsto pelo modelo (futuro).

**Previsão recursiva (dia a dia):** o modelo só sabe prever **1 dia à frente**.
Para um dia distante (ex.: daqui 10 dias), todos os dias anteriores são
preparados primeiro: prevê o dia 1 a partir do histórico real, usa essa
previsão como "passado" para prever o dia 2, e assim por diante. O botão
**`POST /previsao/gerar`** roda essa recursão por **365 dias × todas as
células climáticas** e materializa tudo em `data/climate_forecast.csv` (com o
desvio-padrão entre as árvores por dia/variável). É esse CSV que a API
consulta nos dias futuros. O botão **`POST /historico/atualizar`** repuxa o
histórico real das APIs e retreina o modelo.

**Método escolhido: Random Forest Regressor multi-saída** (scikit-learn).
Justificativa:

- A relação (dias passados → dia seguinte) é **não-linear** e muda com a
  estação; árvores capturam isso sem engenharia de features manual.
- Dataset tabular de ~6.700 amostras: florestas são **robustas** e dispensam
  normalização e tuning pesado (mais que redes neurais Keras/MLP nesse volume).
- O ensemble fornece uma medida de **incerteza gratuita**: a dispersão do clima
  previsto entre as árvores é **propagada pela fórmula de crescimento** e vira
  a **confiança** exposta pela API.

**Features (para prever o dia D de uma célula):** por variável, o valor de
D−1 (`lag1`) e as médias dos últimos 7 e 30 dias; + sazonalidade do dia do ano
(`seno`/`cosseno`, contínua na virada do ano) + `latitude`/`longitude`.
**Alvos:** as 5 variáveis climáticas do dia D.

**Avaliação com split temporal** (últimos 20% dos dias como teste — treina no
passado, prevê o dia seguinte; ver `models/model_metadata.json`): MAE por
variável, ex.: temperatura ≈ 1.6 °C, precipitação ≈ 3.1 mm.

**Confiança:** o CSV de previsão guarda o desvio-padrão entre as árvores por
dia/variável. Cada dia previsto contribui com meia-faixa de taxa de
crescimento (clima ± std); os erros diários são somados em quadratura
(independentes) e atenuados pela saturação logística, virando
`confiança = 1 / (1 + std_cm/8cm)`. Janelas só com dados reais têm confiança
≈ 1. Ver `src/predict.py`.

> Observação: o `requirements.txt` mantém o ambiente pronto; caso se opte por
> testar uma rede neural (Keras/TensorFlow), instale-a **dentro da `.venv`**.

---

## 6. API (saída esperada)

Endpoint principal — `GET /variaveis-x`:

```
GET /variaveis-x?latitude=-23.55&longitude=-46.63&especie=Brachiaria (Urochloa)&dias_desde_corte=25
```

Resposta (formato pedido):
```json
{
  "localizacao": { "latitude": -23.55, "longitude": -46.63, "raio_metros": 500.0 },
  "previsao": { "altura": 8.9, "probabilidade": 0.789 },
  "especie": "Brachiaria (Urochloa)",
  "dias_desde_corte": 25,
  "data": "2026-07-17",
  "fonte_clima": "historico-real(20d)+ao-vivo(1d)+modelo-clima(5d)",
  "corte_recomendado": false
}
```

Os campos `localizacao` e `previsao` são o **contrato mínimo** exigido; os
demais são auxiliares operacionais. Em `previsao`, `altura` é a altura estimada
da grama em cm e `probabilidade` ∈ [0, 1] é a confiança da estimativa
(incerteza do clima previsto propagada pela fórmula de crescimento). O campo
`fonte_clima` resume a origem do clima de cada dia da janela, ex.:
`historico-real(175d)+ao-vivo(1d)+modelo-clima(30d)`.

**Outros endpoints:**

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/variaveis-x` | Variáveis X para lat/long arbitrário |
| GET | `/variaveis-x/ponto/{ponto_id}` | Idem, para um ponto pré-cadastrado |
| GET | `/mapa/rodovia` | Varre toda a rodovia em células de ~200 m de via (círculos de raio 100 m) e classifica cada uma por cor (verde 1–15 cm, amarelo 16–25 cm, vermelho > 25 cm). Aceita `especie=` para escolher qual das cinco colore o mapa; sem ela, cada célula recebe a **mais alta** do trecho (critério de disparo da roçada). Toda célula traz `alturas_por_especie` com as cinco alturas, então o painel troca de espécie sem nova varredura. Cada célula parte do **corte registrado** para ela (campo `corte`), então a data pedida é o horizonte da projeção — sem ela, o mapa mostra a via **hoje** |
| GET | `/cortes` | Histórico de cortes registrados (mais recente primeiro) |
| POST | `/cortes` | Registra um corte: `data_corte`, `altura_corte_cm` e, opcionalmente, `latitude`/`longitude`/`raio_influencia_m` (sem coordenada = corte geral da rodovia). Recusa data futura, altura fora de 0–50 cm e coordenada incompleta |
| DELETE | `/cortes/{id}` | Apaga um registro; o corte anterior volta a valer naquele trecho. O último corte geral é protegido |
| GET | `/cortes/vigente` | Qual corte o sistema usa como estado inicial num ponto |
| POST | `/historico/atualizar` | **Botão**: repuxa 1 ano de dados reais das APIs (todas as células) e retreina o modelo |
| POST | `/previsao/gerar` | **Botão**: previsão recursiva dia a dia (1 → 365) de todas as células → `climate_forecast.csv` |
| GET | `/previsao/status` | Situação do CSV de previsão (existe? qual período cobre?) |
| GET | `/status/apis` | Disponibilidade das APIs externas (Open-Meteo, NASA POWER) |
| GET | `/pontos` | Lista os trechos monitorados do Rodoanel |
| GET | `/especies` | Lista as espécies válidas |
| GET | `/modelo` | Metadados e métricas do modelo |
| GET | `/health` | Status do serviço |
| POST | `/chat` | Chatbot sem streaming |
| POST | `/chat/stream` | Chatbot com eventos SSE |
| DELETE | `/chat/conversations/{id}` | Limpa o vínculo local da conversa |

Documentação interativa automática em `/docs` (Swagger UI).

---

## 7. Assistente EcoTrack

O chatbot em português usa a Gemini Interactions API para interpretar a
pergunta e redigir a resposta. Todos os números operacionais são obtidos por
uma allowlist de ferramentas que chama diretamente as funções deste backend;
o modelo não calcula nem inventa altura, confiança, clima ou recomendação de
corte.

A integração mantém contexto por `conversation_id`, suporta streaming SSE,
valida novamente cada chamada de ferramenta e não expõe o ID interno da
Gemini. Sem `GEMINI_API_KEY`, somente `/chat*` responde `503`; os endpoints
anteriores continuam disponíveis. Configuração, contrato HTTP, retenção e
erros estão implementados em `src/chatbot/` e descritos nesta seção.

---

## 8. Como executar

Guia passo a passo (venv, pipeline offline, subir a API, troubleshooting) em
[`COMO-INICIALIZAR.md`](COMO-INICIALIZAR.md). Para montar um frontend que
consuma esta API, veja [`COMO-CONECTAR.md`](COMO-CONECTAR.md).

---

## 9. Estrutura do projeto

```
Backend/
├── requirements.txt
├── requirements-dev.txt
├── .env.example
├── README.md
├── COMO-INICIALIZAR.md            # passo a passo para rodar o backend
├── COMO-CONECTAR.md               # guia para conectar um frontend à API
├── .gitignore
├── data/
│   ├── climate_history.csv        # 1 ano de dados REAIS (dataset de treino)
│   ├── climate_forecast.csv       # 365 dias previstos (recursivo, por célula)
│   ├── ecotrack.db                # banco operacional (cortes registrados)
│   └── rodoanel_rota.json         # traçado real do SP-021 (OpenStreetMap)
├── models/
│   ├── climate_model.joblib       # Random Forest de previsão climática
│   └── model_metadata.json        # métricas e metadados do treino
├── scripts/
│   └── build_pipeline.py          # coleta o histórico + treina o modelo
├── src/
│   ├── config.py                  # rota, espécies, constantes
│   ├── growth.py                  # fórmula agronômica (calcula a altura)
│   ├── clients.py                 # clientes Open-Meteo / NASA POWER
│   ├── ingest.py                  # leitura ao vivo (APIs + base do modelo)
│   ├── historico.py               # coleta/consulta do histórico real (CSV)
│   ├── train.py                   # treino do modelo autorregressivo
│   ├── forecast.py                # previsão recursiva 365d → CSV
│   ├── predict.py                 # clima por dia da janela + altura + confiança
│   ├── mapa.py                    # varredura da rodovia (células de ~200 m)
│   ├── db.py                      # banco de cortes (estado inicial da simulação)
│   ├── chatbot/                   # prompt, tools, sessões, Gemini e rotas
│   └── api.py                     # composição FastAPI
└── tests/
    ├── test_smoke.py
    ├── test_cortes.py
    ├── test_chatbot_api.py
    ├── test_chatbot_service.py
    └── test_chatbot_tools.py
```
