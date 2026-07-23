# Como conectar um frontend à EcoTrack API

Este backend é uma API HTTP (FastAPI) que responde JSON. Qualquer frontend
(site estático, React, Vue, mobile, etc.) pode consumi-la.

## 1. Suba o backend primeiro

Siga [`COMO-INICIALIZAR.md`](COMO-INICIALIZAR.md). Com a API no ar em
`http://127.0.0.1:8000`, abra `http://127.0.0.1:8000/docs`, é a forma mais
rápida de explorar e testar cada endpoint antes de escrever código.

## 2. CORS já está liberado

A API já sobe com `Access-Control-Allow-Origin: *` (ver `src/api.py`), então
seu frontend pode chamar `fetch`/`axios` **direto do navegador**, de qualquer
origem/porta, sem proxy nem configuração extra. Para produção, o ideal é
restringir `allow_origins` ao domínio real do site — hoje está aberto porque
o uso é local/times fechados.

## 3. Guarde a URL base num único lugar

Evite espalhar `http://127.0.0.1:8000` pelo código. Um padrão simples que
funciona bem (e permite trocar a porta/host sem recompilar nada):

```js
// config.js
const API = (localStorage.getItem("ecotrack_api") || "http://127.0.0.1:8000")
  .replace(/\/$/, "");
```

Assim, se alguém rodar o backend em outra porta, basta no console do
navegador: `localStorage.setItem('ecotrack_api', 'http://127.0.0.1:8001')`.

## 4. Endpoints principais

| Método | Rota | Uso |
|---|---|---|
| `GET` | `/variaveis-x` | Altura + confiança para uma coordenada arbitrária |
| `GET` | `/variaveis-x/ponto/{ponto_id}` | Idem, para um trecho pré-cadastrado (ver `/pontos`) |
| `GET` | `/mapa/rodovia` | Varre a rodovia inteira, já classificada por cor (verde/amarelo/vermelho) |
| `GET` | `/pontos` | Lista de trechos monitorados — útil para popular um `<select>` |
| `GET` | `/especies` | Lista de espécies válidas — idem, para outro `<select>` |
| `GET` | `/modelo` | Métricas/metadados do modelo treinado |
| `GET` | `/status/apis` | Se as APIs externas (Open-Meteo, NASA POWER) estão no ar |
| `GET` | `/health` | Status simples do serviço (para um indicador "backend online") |
| `POST` | `/historico/atualizar` | Botão "atualizar dados": repuxa histórico real e retreina |
| `POST` | `/previsao/gerar` | Botão "gerar previsão": recalcula os 365 dias futuros |

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
