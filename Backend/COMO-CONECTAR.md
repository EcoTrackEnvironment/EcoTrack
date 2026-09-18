# Como conectar um frontend à EcoTrack API

Este backend é uma API HTTP (FastAPI) que responde JSON. Qualquer frontend
(site estático, React, Vue, mobile, etc.) pode consumi-la.

## 1. Suba o backend primeiro

Siga [`COMO-INICIALIZAR.md`](COMO-INICIALIZAR.md). Com a API no ar em
`http://127.0.0.1:8000`, abra `http://127.0.0.1:8000/docs`, é a forma mais
rápida de explorar e testar cada endpoint antes de escrever código.

## 2. CORS

A API sobe por padrão com `Access-Control-Allow-Origin: *`, então
seu frontend pode chamar `fetch`/`axios` **direto do navegador**, de qualquer
origem/porta, sem proxy nem configuração extra. Para produção, o ideal é
defina `ECOTRACK_CORS_ORIGINS` com os domínios reais separados por vírgula.
O padrão aberto existe somente para preservar o uso local atual.

## 3. Guarde a URL base num único lugar

O frontend React deste repositório centraliza a URL em `frontend/src/api/client.js`.
Defina a variável no build do Vite; sem ela, o desenvolvimento local usa
`http://127.0.0.1:8000`:

```bash
VITE_ECOTRACK_API_URL=http://127.0.0.1:8001 npm run dev
```

Em produção, forneça a URL pública da API no mesmo nome durante o build e
inclua a origem pública do frontend em `ECOTRACK_CORS_ORIGINS`.

## 4. Endpoints principais

| Método | Rota | Uso |
|---|---|---|
| `GET` | `/variaveis-x` | Altura + confiança para uma coordenada arbitrária |
| `GET` | `/variaveis-x/ponto/{ponto_id}` | Idem, para um trecho pré-cadastrado (ver `/pontos`) |
| `GET` | `/mapa/rodovia` | Varre a rodovia inteira, já classificada por cor (verde/amarelo/vermelho) |
| `GET` | `/cortes` | Histórico de cortes registrados (alimenta a tabela da tela de registro) |
| `POST` | `/cortes` | Registra um corte: `{data_corte, altura_corte_cm}` e, opcionalmente, `{latitude, longitude, raio_influencia_m}` — sem coordenada é corte geral da rodovia |
| `DELETE` | `/cortes/{id}` | Apaga um registro (o corte anterior volta a valer no trecho) |
| `GET` | `/cortes/vigente` | Qual corte o sistema usa como estado inicial em `?latitude=&longitude=` |
| `GET` | `/pontos` | Lista de trechos monitorados — útil para popular um `<select>` |
| `GET` | `/especies` | Lista de espécies válidas — idem, para outro `<select>` |
| `GET` | `/modelo` | Métricas/metadados do modelo treinado |
| `GET` | `/status/apis` | Se as APIs externas (Open-Meteo, NASA POWER) estão no ar |
| `GET` | `/health` | Status simples do serviço (para um indicador "backend online") |
| `POST` | `/historico/atualizar` | Botão "atualizar dados": repuxa histórico real e retreina |
| `POST` | `/previsao/gerar` | Botão "gerar previsão": recalcula os 365 dias futuros |
| `POST` | `/chat` | Chatbot sem streaming |
| `POST` | `/chat/stream` | Chatbot com streaming SSE |
| `DELETE` | `/chat/conversations/{id}` | Limpa a conversa local |

Parâmetros e formatos completos de cada rota estão no `/docs` (Swagger) — ele
reflete o código, então é a fonte de verdade mais confiável.

## 5. Exemplo — consultar a altura de um ponto

```js
async function consultarAltura({ latitude, longitude, especie, diasDesdeCorte }) {
  const params = new URLSearchParams({
    latitude, longitude, especie,
    dias_desde_corte: diasDesdeCorte,
  });
  const resp = await fetch(`${API}/variaveis-x?${params}`);
  if (!resp.ok) {
    const erro = await resp.json().catch(() => ({}));
    throw new Error(erro.detail ?? `Erro ${resp.status}`);
  }
  return resp.json();
}
```

Resposta (`previsao.altura` em cm, `previsao.probabilidade` é a confiança
0–1; `localizacao` + `previsao` são o contrato mínimo, o resto é auxiliar):

```json
{
  "localizacao": { "latitude": -23.55, "longitude": -46.63, "raio_metros": 500.0 },
  "previsao": { "altura": 8.9, "probabilidade": 0.789 },
  "especie": "Brachiaria (Urochloa)",
  "dias_desde_corte": 25,
  "data": "2026-07-17",
  "fonte_clima": "historico-real(20d)+ao-vivo(1d)+modelo-clima(5d)",
  "corte_recomendado": false,
  "clima": {
    "temperatura_c": 24.3, "precipitacao_mm": 2.1, "umidade_pct": 71.0,
    "radiacao_mj_m2": 17.8, "vento_kmh": 12.4,
    "fontes": { "temperatura_c": "open-meteo", "radiacao_mj_m2": "modelo-clima" }
  }
}
```

## 6. Erros — o que tratar na UI

A API não retorna `200` com corpo vazio em erro; ela usa status HTTP +
`detail` (padrão FastAPI):

| Status | Quando acontece | O que mostrar |
|---|---|---|
| `422` | Espécie desconhecida, data inválida, parâmetro fora do range | Mensagem de validação (`detail`) |
| `404` | `ponto_id` inexistente em `/variaveis-x/ponto/{id}` | "Ponto não encontrado" |
| `503` | Modelo ainda não treinado, ou previsão indisponível para a data pedida | "Backend ainda inicializando" / sugerir rodar `/previsao/gerar` |

## 7. Dica: página de status

Antes de investir tempo na UI principal, vale montar uma telinha simples que
chama `/health` e `/status/apis` periodicamente — ajuda o time inteiro a
saber rapidamente se o problema é "backend fora do ar" vs. "bug no
frontend" vs. "API externa fora do ar".

## 8. Chatbot

O contrato completo, consumo de SSE com `fetch`, retenção e erros estão
implementados em `src/chatbot/` e descritos na seção de assistente do
[`README.md`](README.md). A chave Gemini pertence somente ao backend e nunca
deve aparecer no JavaScript, HTML, storage ou bundle do frontend.
