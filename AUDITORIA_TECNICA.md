# Auditoria técnica EcoTrack — 17/09/2026

## Escopo e método

Auditoria iniciada sem alterações no código. Instruções lidas em `../AGENTS.md` e `../.codex/agents/*.toml`. O repositório Git real é esta pasta `EcoTrack/`, inicialmente limpa; os caminhos abaixo são relativos a ela. Foram usados explorer, test-reviewer, frontend-engineer e backend-engineer. A revisão de segurança foi executada por agente compatível com as instruções do security-reviewer: o modelo configurado gpt-5.6 foi recusado pela conta. A revisão de integração foi feita pelo explorer seguindo as instruções do integration-engineer após o limite de threads impedir uma nova instância. A revisão científica usa agente compatível com as instruções do ml-agronomy-specialist pelo mesmo impedimento de modelo.

Evidências são de código, testes isolados e auditorias de dependências, sem acesso a produção. Severidade de advisory não equivale a exploração demonstrada nesta aplicação. Números de linha referem-se ao estado inicial e podem mudar nas correções. Não houve consulta nem publicação de credenciais.

## Arquitetura e contratos observados

- FastAPI em `Backend/src/api.py`, SQLite em `db.py`; React/Vite em `frontend/src`, shell `layout/DashboardLayout.jsx`.
- `clients.py` → Open-Meteo/NASA POWER → `historico.py` (CSV diário) → `train.py` (Random Forest multi-saída, split por data) → `forecast.py` (recursão diária) → `predict.py` → `growth.py` → altura/confiança → API → frontend.
- **ML prevê clima; altura vem da simulação agronômica.** Cinco espécies são simuladas; mapa sem filtro usa a maior altura. `config.classificar_cor` usa limites 15 e 25 cm (valores fracionários acima de 15 já são amarelos; zero é verde).
- Cortes são inseridos como histórico. Resolução compara data, especificidade e recência. Exclusão permite retorno do registro anterior; o último corte global é protegido.
- Rotas: `/`, `/health`, `/status/apis`, `/pontos`, `/especies`, `/modelo`, `/variaveis-x`, `/variaveis-x/ponto/{id}`, `/mapa/rodovia`, `/crescimento/serie`, GET/POST `/cortes`, DELETE `/cortes/{id}`, `/cortes/vigente`, POST `/historico/atualizar`, POST `/previsao/gerar`, `/previsao/status`, POST `/chat`, POST `/chat/stream`, DELETE `/chat/conversations/{id}`.
- `/variaveis-x` exige espécie e retorna `previsao.altura/probabilidade`; mapa retorna `altura_cm/confianca/corte/alturas_por_especie`. SSE usa `session/status/delta/done/error`.
- Chat tem sete ferramentas de leitura explicitamente permitidas, validação Pydantic, sessões TTL/LRU e limite por IP no processo. Não oferece ferramentas de escrita/pipeline.
- Dependências: `Backend/requirements*.txt`, `frontend/package*.json`. Configuração em `Backend/src/config.py` e `.env.example`; frontend não consumia variável de URL. O arquivo joblib está ausente neste checkout, embora CSVs e metadata estejam versionados.
- Testes backend em `Backend/tests`; nenhum teste frontend inicial. Workflows estão incorretamente em `Backend/.github/workflows/`.

## Validação inicial

- Ambiente isolado `/tmp/ecotrack-audit-venv`; banco de testes em `/tmp`.
- `python -m pytest -q`: **47 passaram**. `compileall` e `pip check`: passaram.
- `npm ci`: passou, sem mudança do lockfile. `npm run build`: passou, aviso de chunk principal ~1,15 MB (~362 kB gzip).
- `npm run lint`: **falhou**, 1 erro (`react-hooks/refs`) e 1 warning em `ConsultaTrecho.jsx`.
- `npm audit --json`: após repetir fora da restrição de rede, **9 entradas: 1 crítica, 6 altas, 2 moderadas**. Relatório bruto em `/tmp/ecotrack-npm-audit-before.json`.
- `pip-audit`: requests e Starlette têm advisories. Auditoria do ambiente também incluiu o pip do venv e entradas duplicadas; não se deve atribuir o total bruto ao projeto. Relatório em `/tmp/ecotrack-pip-audit-before.json`.
- Pipeline de coleta/retreino não executado: alteraria artefatos e exige rede/custo; testes usam dependências simuladas.

## A. Bugs críticos

Nenhum bug funcional com impacto crítico demonstrado. Existe advisory crítico em dependência (D4), sem caminho de exploração demonstrado: `rechart` não é importado pelo código. Falhas de consulta são classificadas como altas, não críticas.

## B. Bugs médios e altos

| ID / severidade | Arquivo e função/trecho | Causa e impacto | Solução sugerida / risco de regressão |
|---|---|---|---|
| B1 **alto** | `Backend/src/mapa.py:126`, `gerar_mapa_rodovia` | Resolve cortes com `referencia=hoje`, mesmo para alvo passado; corte posterior ao alvo pode aparecer como já executado. Reproduzido com alvo 01/09 e corte 10/09. | Resolver na data-alvo; teste com cortes históricos. **Baixo**, corrige seleção histórica sem mudar precedência. |
| B2 **alto** | `Backend/src/predict.py:243-250`, `prever_altura` | Janela inclusiva `fim-N..fim` contém N+1 dias; zero dias já cresce. Diverge da convenção mapa/série. | Integrar exatamente N dias após corte; zero mantém altura inicial, com clima auxiliar válido. **Médio**, altera alturas antes superestimadas; não altera fórmula. |
| B3 **alto** | `Backend/src/api.py:234`, `health` | Só verifica metadata, existente sem joblib no checkout. Reporta modelo treinado enquanto previsão retorna 503. | Verificar artefato realmente exigido, preservar campos públicos. **Baixo**. |
| B4 **médio** | `Backend/src/api.py:389-401`, `crescimento_serie` | `obter_clima` fora do try: ausência esperada de cobertura vira 500. | Incluir leitura no tratamento 422/503. **Baixo**. A rota do mapa já envolve `gerar_mapa_rodovia` em try; não é o mesmo defeito. |
| B5 **alto** | `Backend/src/api.py:413-429`, `forecast.py:120`, atualização/consulta | Retreino mantém previsão anterior e status só indica existência; cache/CSV continuam servindo versão anterior. | Versionar artefatos e invalidar previsão após retreino; publicar conjunto consistente. **Médio/alto**, altera disponibilidade após atualização; exige desenho de ciclo dos artefatos. |
| B6 **médio** | `Backend/src/db.py:288`, `_ordenacao` | `criado_em` precede `id`; relógio regressivo faz registro antigo vencer no empate. | Desempatar por ID autoincremental após data/escopo. **Baixo**, cumpre última inserção. |
| B7 **médio** | `Backend/src/clients.py:66-76,170-179`, parsers | HTTP 200 com null, tipo inesperado ou não finito escapa como TypeError/valor inválido em ingestão. | Validar esquema/número finito na fronteira e normalizar `ClimateAPIError`. **Baixo**; fallback passa a funcionar. |
| B8 **alto** | `Backend/src/db.py:251-267`, `remover_corte` | Busca/contagem/delete separados sem transação de exclusão mútua; duas remoções globais podem ambas observar dois registros e remover o último global. Também pode haver sucesso para linha já apagada. | Transação de escrita envolvendo consulta, proteção e delete. **Baixo/médio**, contenção deve ser testada. |

## C. Bugs menores

| ID / severidade | Arquivo e trecho | Causa e impacto | Solução / risco |
|---|---|---|---|
| C1 **baixo** | `frontend/.../ConsultaTrecho.jsx:202` | Leitura de `ref.current` no render viola lint e faz render depender de valor não reativo. | Estado/props para exibição. **Baixo**. |
| C2 **médio** | `frontend/.../Mapa.jsx:156`, ambos `GraficoLinha.jsx`, telas de cortes | `toISOString` usa UTC; entre 21h e meia-noite BRT pode selecionar amanhã. Backend usa timezone do processo, não força região. | Datas civis explícitas e alinhamento de timezone por contrato. **Médio**; não mudar silenciosamente datas armazenadas. |
| C3 **baixo** | `frontend/.../Exportacao.jsx:444`, `exportarCSV` | Botão apenas escreve no console e não exporta. | Indicar indisponível até implementação real. **Baixo**. |

## D. Riscos de segurança

| ID / severidade | Arquivo e trecho | Causa, precondição e impacto | Solução / risco |
|---|---|---|---|
| D1 **alto** | `Backend/src/api.py:293-326,413-447`; `frontend/.../Login.jsx:16`, `main.jsx` | Não há autenticação/autorização no servidor; login apenas navega. Qualquer cliente com acesso à API pode criar/apagar cortes e executar pipeline. | Identidade e RBAC no servidor, guardas UI complementares. **Alto**, exige decisão de arquitetura e credenciais dos consumidores. |
| D2 **alto** | `Backend/src/config.py:321`, `api.py:69` | CORS padrão `*` com POST/DELETE amplia chamadas por sites terceiros à API pública. Não é substituto de autenticação. | Origens explícitas por ambiente e política de autenticação. **Médio**, pode bloquear frontends legítimos sem inventário de origens. |
| D3 **alto** | `Backend/src/chatbot/service.py:304-314,395-445,450-497`; `prompts.py` | Ferramentas são opcionais e texto/deltas livres são repassados. Prompt não garante lastro; modelo pode inventar valor mesmo após consultar ferramenta. | Respostas operacionais estruturadas/determinísticas derivadas das ferramentas, separadas de explicação livre. **Alto**, muda protocolo/orquestração; regex ou exigir qualquer tool não garante correção. |
| D4 **crítico no advisory; exposição não demonstrada** | `frontend/package.json`, `package-lock.json`, `rechart → lodash@3.10.1` | Pacote antigo não usado traz advisories de prototype pollution/injection. Presença confirmada por `npm ls`, sem import em `src`. | Remover `rechart` sem remover `recharts`; auditar novamente. **Baixo**, pacote não utilizado. |
| D5 **alto no advisory; exposição dependente do uso** | `frontend/package-lock.json` | Advisories em react-router, postcss, nanoid, browserslist, brace-expansion e baseline-browser-mapping. RSC não é usado nesta SPA; várias entradas atingem tooling e inputs não expostos. | Atualizações compatíveis e direcionadas do lockfile, sem `--force`; build/lint. **Médio**, ferramentas podem mudar. |
| D6 **médio no contexto auditado** | `Backend/requirements.txt`, requests 2.32.3 / Starlette 0.41.3 | Requests: advisories `.netrc` com URL maliciosa e extração ZIP; URLs vêm de configuração e extração não é usada. Starlette: forms, FileResponse/StaticFiles e HTTPEndpoint não são usados; avisos de parsing URL também exigem uso sensível da URL reconstruída. Não demonstrada exploração nessas rotas. | Atualizar requests ≥2.33.0; planejar FastAPI/Starlette compatíveis (FastAPI atual limita Starlette <0.42). **Médio/alto** para framework; não forçar versão incompatível. |
| D7 **médio** | `Backend/src/chatbot/sessions.py:79`, `router.py:154`, `service.py:304` | ID aleatório atua como credencial de conversa; quem obtiver ID pode continuar/apagar sessão. `store=True` mantém contexto no provedor; delete só remove estado local. | Vincular ao usuário e definir retenção/exclusão remota. **Alto**, depende de autenticação e política de dados. |

Verificações negativas: `.env` não rastreado; exemplo sem chave literal; SQL parametrizado; sem execução de comandos ou paths/URLs arbitrários de request; ReactMarkdown sem HTML cru. Nenhum secret identificado nas verificações realizadas. Isso não certifica ambiente externo nem toda a história de credenciais.

## E. Integração frontend/backend

| ID / severidade | Arquivo e trecho | Causa e impacto | Solução / risco |
|---|---|---|---|
| E1 **alto** | `frontend/.../ConsultaTrecho.jsx:65-80,146`; `Backend/src/api.py:468` | Consulta manual omite espécie obrigatória: HTTP 422. Envia `altura_inicial_cm/alinhar_com_mapa`, ignorados pela API, e apresenta reconsulta hipotética como resultado do mapa. | Seleção de espécie explícita; célula selecionada exibe seus próprios valores autoritativos; manual permanece hipótese. **Baixo/médio**, preservar API sem duplicar simulação. |
| E2 **alto** | `frontend/.../Mapa.jsx:259-263` | Legenda 0–10/11–30/>30 contradiz cores corretas do backend (15/25). | Corrigir somente rótulos para 1–15/16–25/>25. **Baixo**, thresholds não mudam. |
| E3 **alto** | `frontend/.../Mapa.jsx:172-218`, `DashboardPrincipal/index.jsx` | Falha de nova consulta deixa células antigas alimentando recomendações no pai. Seleção por coordenada ignora mudança de data/corte. | Invalidar consumidores ao carregar/falhar; sincronizar seleção à nova resposta; impedir sobrescrita por resposta antiga. **Médio**, testar atualização/falha. |
| E4 **alto** | `frontend/.../DashboardIndicadoresAmbientais/index.jsx:32-100` | Erro descartado; fallback numérico zero e NaN% parecem dados. Rótulo de média atual recebe média da janela. | Erro/indisponível explícito e rótulo da janela. **Baixo**, não inventar dados. |
| E5 **alto** | `Header.jsx:12-37`, `CardRecomendacaoSistema.jsx:6`, `EquipesDisponiveis.jsx`, `Exportacao.jsx` | Alertas/equipes/ETA fictícios, alocação só seleciona célula mas anuncia sucesso, PDF inclui execução de exemplo. | Remover alegações de execução, rotular exemplos e modelo de formulário; desativar ação não implementada. **Baixo/médio**, integração operacional real fica pendente. |
| E6 **médio** | Consumidores HTTP em `frontend/src`, `chatbotClient.js:16` | URL loopback fixa aponta para máquina do operador em deploy remoto; variável documentada não usada. | Base central por `VITE_ECOTRACK_API_URL`, default local compatível. **Baixo**. |
| E7 **médio** | `frontend/.../chatbotClient.js:150-156`, `Chatbot.jsx:53-99` | EOF sem done é aceito silenciosamente; decoder não faz flush; `sendChatMessage` existe mas não é usado. | Detectar stream incompleto; fallback só em falha explícita pré-processamento, evitando duplicar turno já executado. **Médio**; ausência de delta sozinha não prova que request não foi executado. |

## F. Performance e concorrência

| ID / severidade | Arquivo e trecho | Causa e impacto | Solução / risco |
|---|---|---|---|
| F1 **alto** | `Backend/src/api.py:413-447`, pipeline | Execuções caras sem autenticação, limite ou coordenação; repetição esgota CPU/rede e concorrência sobrescreve arquivos. | Controle administrativo, exclusão mútua entre processos e jobs com status. **Alto** se mudar síncrono para 202; decisão arquitetural. |
| F2 **médio** | `historico.py:128`, `forecast.py:114-126`, `train.py:127,151` | Escrita direta de CSV/joblib; leitores podem ver parcial. Cache LRU só invalida no processo escritor. | Publicação atômica/versionada e cache por versão. **Médio**, consistência do conjunto exige coordenação. |
| F3 **médio** | `Backend/src/mapa.py`, `historico.serie_historica`, `forecast.serie_prevista`, `db.resolver_cortes` | ~861 células padrão, cinco espécies; filtros de DataFrame e varredura de cortes repetidos, piora com datas de corte distintas e 0,1 km. | Medir latência, indexar por célula/data e cache com versão de cortes/artefatos. **Médio**, cache mal invalidado corrompe estado operacional. |
| F4 **médio** | `frontend/.../Mapa.jsx`, `MapaCortes.jsx`, bundle | Centenas de Circle/Popup/Tooltip e bundle inicial grande; sem medição de navegador não se quantifica latência. | Perfil de render, canvas/memoização/lazy loading onde medido. **Baixo/médio**. |
| F5 **médio** | `Backend/src/chatbot/router.py:25`, `sessions.py` | Rate limit e sessões locais por processo; buckets de IP não são removidos globalmente. Múltiplos workers divergem e memória cresce com IPs distintos. | Limpeza/limite de buckets e store compartilhado se multiprocessado. **Médio**. |

## G. Qualidade/manutenibilidade

| ID / severidade | Arquivo e trecho | Causa e impacto | Solução / risco |
|---|---|---|---|
| G1 **alto** | `Backend/.github/workflows/*.yml` | GitHub não descobre workflows fora de `.github/workflows` da raiz. Paths internos ainda presumem Backend na raiz. | Mover workflows e ajustar diretórios, cache e uploads; incluir validações frontend. **Baixo**, execução remota só comprovada após push. |
| G2 **baixo** | Componentes duplicados `GraficoLinha/VariaveisCards`, thresholds React, documentação | Duplicação facilita divergência; integrações documentadas `/pontos` e cartões não refletem composição atual. | Atualizar documentação e consolidar somente numa tarefa dedicada. **Médio** para refatoração, não necessária nesta correção. |
| G3 **médio** | `Backend/src/api.py:87`, `config.py`, artefatos | Import inicializa banco; joblib ausente impede runtime completo; data e altura seed são premissas operacionais fixas. | Isolar DB em testes, documentar inicialização e validar artefatos de deployment. **Médio** se alterar seed/startup; não inventar observação de campo. |

## H. Testes faltantes

| ID / severidade | Local/causa | Impacto | Solução / risco |
|---|---|---|---|
| H1 **alto** | `Backend/tests`: falta contrato das rotas principais | 47 testes passam apesar de mapa histórico falso, 500 esperado e health falso. | API com fixtures, 422/503, data-alvo, modelo ausente, espécie obrigatória; **baixo**. |
| H2 **alto** | `Backend/tests`: corte concorrente, relógio regressivo e janelas zero/N | Invariantes incompletamente protegidos. | Fixtures SQLite temporárias, testes determinísticos e concorrência controlada; **baixo**. |
| H3 **alto** | `frontend`: sem testes | Sem barreira para dados fictícios, reconsulta incompatível, races, erro e SSE truncado. | Testes de contrato/estado, SSE fragmentado e interação com componentes; **baixo/médio** se introduzir tooling. |
| H4 **alto** | `Backend/tests`: pipeline/forecast/confiança | Sem backtest recursivo, origem parcial, falhas de schema, publicação/cache concorrentes. | Fixtures sintéticas, testes de ingestão e avaliação por horizonte; **baixo** para testes, decisão científica para novos critérios. |

## I. Melhorias recomendadas e plano priorizado (antes das correções)

1. **P0 — segurança e integridade operacional:** retirar dependência não usada com advisory crítico; corrigir contrato da consulta, mapa histórico, legenda, dados inventados e sucesso falso. Testes pequenos e isolados por conjunto.
2. **P1 — backend:** corrigir desempate/remoção de cortes, validação climática, tratamento de erro e health. Convenção N dias será corrigida apenas com impacto numérico explicitado e testes zero/um/N; fórmula e parâmetros permanecem iguais.
3. **P1 — integração:** configurar URL, invalidar dados antigos, tratar SSE incompleto e lint. Preservar nomes/unidades e API existente.
4. **P1 — dependências/CI:** retirar pacote morto; aplicar somente atualizações compatíveis ligadas aos avisos, verificar lock/build/tests; reparar localização/paths dos workflows.
5. **Decisão arquitetural antes de implementar:** autenticação/RBAC e origens de produção; geração determinística de respostas operacionais do chatbot; publicação versionada de artefatos/jobs e invalidação após retreino. Não introduzir solução parcial apresentada como garantia.
6. **Decisão científica antes de implementar:** origem/incerteza climática, calibração e pressupostos agronômicos detalhados no complemento científico. Não alterar confiança, fórmula, thresholds ou parâmetros silenciosamente.
7. **Fechamento:** suíte completa, build/lint, imports, revisão de diff/secrets e segunda revisão de integração/segurança. Registrar abaixo o que foi corrigido, o que permanece e limitações de validação.

## Complemento científico (antes das correções)

| ID / severidade | Arquivo e função | Causa e impacto | Solução / risco de regressão |
|---|---|---|---|
| S1 **alto** | `Backend/src/ingest.py:63-103`, `predict.py:91-100` | Clima de hoje pode conter previsão parcial/total, mas a janela conta todo o dia como ao-vivo, std zero. Confiança fica artificialmente elevada. | Preservar origem e std por variável. **Alto**, modifica confiança publicada; requer política explícita. |
| S2 **alto** | `Backend/src/historico.py:114-121,143-167`, `train.py:98-119` | Interpolação usa dias futuros; origem é descartada na leitura. Pode haver leakage de imputação se lacuna atravessa split, e dados interpolados viram observações sem incerteza. | Imputação causal e máscara por variável; avaliação sem leakage. **Alto**, altera dataset/modelo e confiança; exige retreino. |
| S3 **alto** | `Backend/src/predict.py:161-175`, `forecast.py:92-111` | Dispersão das árvores não mede erro recursivo; extremos conjuntos não são bounds garantidos e divisão por sqrt(n) assume independência. Confiança não é probabilidade calibrada. | Backtest recursivo por horizonte, calibração e documentação da métrica. **Alto**, decisão científica e possível versionamento. |
| S4 **alto** | `Backend/src/growth.py:302,338`, `config.py`, `mapa.py:158` | Corte aceita 50 cm e Paspalum tem teto 40 cm. Dia do corte mostra 50; simulação seguinte faz clamp para 40. Viola monotonia entre horizontes. | Definir se rejeita corte ou preserva altura observada acima do teto. **Alto**, muda fórmula/bounds ou validação operacional; não alterar sem decisão. |
| S5 **alto** | `Backend/src/db.py:333`, `mapa.py:125-133` | Janela acima de 500 dias é truncada, mas altura inicial continua sendo a do corte antigo. Crescimento anterior é descartado silenciosamente. | Rejeitar horizonte fora da validade ou persistir estado intermediário. **Alto**, altera disponibilidade/estado; não extrapolar silenciosamente. |
| S6 **médio** | `Backend/src/mapa.py:146-153` | Clima ao vivo do centro regional é reutilizado para todos os grupos. Perde variação espacial do dia atual. | Consulta por grupo com cache/limite, ou documentar aproximação. **Médio**, muda custo e alturas. |
| S7 **médio** | `Backend/src/train.py:105-125`, `forecast.py:83-111` | MAE de um passo com contexto observado é reportado para modelo usado recursivamente até 365 dias. Não demonstra acurácia nesse horizonte. | Avaliação rolling-origin multihorizonte; **baixo** para avaliação, **alto** se recalibrar. |
| S8 **médio** | `Backend/src/clients.py:60`, `growth.py:119` | Ingestão usa máximo de vento a 10 m; ET0 trata valor convertido como velocidade a 2 m sem ajuste de altura nem média diária. Unidades km/h→m/s estão corretas, semântica física é aproximada. | Validar escolha de variável e conversão com responsável científico. **Alto**, muda balanço hídrico e requer reavaliação, não corrigir automaticamente. |

NASA POWER usa unidades dependentes da comunidade; o código seleciona AG. Não foi encontrada evidência suficiente para classificar a radiação como erro de conversão. Referência: [documentação oficial das comunidades NASA POWER](https://power.larc.nasa.gov/docs/methodology/communities/). As constantes empíricas de crescimento continuam exigindo validação de campo; testes matemáticos não demonstram acurácia agronômica.

## Execução das correções

As correções locais foram executadas depois da emissão das seções anteriores. Itens que exigem autenticação, protocolo novo do chatbot, mudança de fórmula/confiança ou ciclo transacional de artefatos permaneceram fora do lote porque dependem de decisão arquitetural ou científica.

### Correções realizadas

- **Backend:** B1/B2/B3/B4/B6/B7/B8 foram corrigidos. O mapa resolve cortes na data-alvo; `/variaveis-x` simula exatamente N dias (zero dias preserva altura, confiança 1 e std 0); health verifica o joblib consumido; a série converte indisponibilidade climática em 422; o desempate final usa ID; exclusão protege o último global dentro de `BEGIN IMMEDIATE`; clientes rejeitam JSON/shape/null/tipo/número não finito.
- **Frontend/integração:** E1/E2/E3/E4/E6/E7 e C1/C2 foram corrigidos. A espécie é explícita; célula do mapa usa seu resultado autoritativo; consulta manual permanece hipotética e apenas destaca a célula mais próxima; estados antigos são descartados; URL fica em `VITE_ECOTRACK_API_URL`; datas são civis locais; indicadores não fabricam zero; legenda usa 15/25; SSE trata CRLF/flush/EOF e só usa fallback quando a ausência de streaming é inequívoca.
- **Dados demonstrativos:** ações sem backend não anunciam sucesso. Alertas, usuário, equipes e ETAs são identificados como demonstração; PDF/CSV/compliance foram desativados enquanto não houver dados operacionais. A tela de acesso informa que ainda não autentica nem envia cadastro.
- **Dependências:** `rechart` (singular, não usado) e sua cadeia antiga com lodash foram removidos; `npm audit fix` sem `--force` atualizou apenas versões compatíveis. `requests` foi atualizado de 2.32.3 para 2.33.0.
- **CI/documentação:** workflows foram movidos para `.github/workflows`, com jobs backend e frontend; CodeQL cobre Python e JavaScript/TypeScript na branch `main`; rebuild usa caminhos `Backend/`. Documentação aponta para os caminhos reais e para `VITE_ECOTRACK_API_URL`.

### Arquivos modificados

- Backend: `src/api.py`, `clients.py`, `db.py`, `mapa.py`, `predict.py`, `tests/test_backend_correcoes.py`, `requirements.txt`, `README.md`, `COMO-INICIALIZAR.md`, `COMO-CONECTAR.md`.
- Frontend: `package.json`, `package-lock.json`, `src/api/client.js`, consumidores HTTP/datas em dashboard, gráficos e cortes, chatbot, login/header, consulta/mapa, recomendações/equipes/exportação.
- Repositório: `.github/workflows/{ci,codeql,rebuild-climate-model}.yml` (os equivalentes incorretos sob `Backend/.github` foram removidos) e este relatório.

### Testes e verificações finais

- Backend: `ECOTRACK_DB_PATH=/tmp/... /tmp/ecotrack-audit-venv/bin/python -m pytest -q` → **59 passed** (baseline: 47); testes novos cobrem data-alvo do mapa, zero/um/N dias, health, erro climático, desempate/remoção e respostas externas inválidas.
- `python -m compileall -q src scripts` e `python -m pip check` → passaram.
- Frontend: `npm run lint` → passou; `npm run build` → passou. Permanece aviso não bloqueante do chunk principal (~1,12 MB; ~354 kB gzip) e logo PNG de ~822 kB.
- `npm audit --json` → **0 vulnerabilidades** após as atualizações compatíveis.
- `pip-audit -r requirements-dev.txt` → requests deixou de aparecer; permanecem sete IDs únicos atribuídos a Starlette 0.41.3. Não há no repositório os caminhos afetados (`UploadFile`/forms, `FileResponse`/`StaticFiles`, `HTTPEndpoint` ou decisão com `request.url`), mas FastAPI/Starlette devem ser atualizados juntos numa etapa compatível.
- Workflows: três YAMLs parseados; `git diff --check` passou.
- Revisão final de segurança: sem secret, SQL interpolado, HTML cru/XSS, execução de comandos, upload/path externo controlado ou permissão excessiva nova. O scan encontrou somente a leitura de `GEMINI_API_KEY` do ambiente.
- O pipeline real não foi executado: depende de rede, reescreve artefatos e o joblib não está no checkout. O health agora relata corretamente esse estado degradado.

### Riscos que permanecem

1. **Decisão arquitetural:** D1/D2/D3/D7 e F1/F2 — autenticação/RBAC, origens CORS de produção, respostas operacionais determinísticas do chatbot, propriedade/retenção de sessões, jobs/locks e publicação versionada/atômica de artefatos.
2. **Decisão científica:** S1–S8 — origem e incerteza por variável, imputação causal, calibração recursiva, corte acima do teto de espécie, horizonte >500 dias, clima espacial atual, backtest multihorizonte e semântica do vento. Nenhuma fórmula, constante de espécie, threshold 15/25, escala de confiança ou feature do modelo foi alterada.
3. **Produto:** login, alertas, equipes, alocação e exportação ainda não têm backend operacional; agora estão claramente marcados/desativados. Não há testes automatizados frontend.
4. **Operação/performance:** previsão antiga após retreino (B5), cache/publicação entre processos, custo do mapa e bundle grande continuam pendentes.
5. **Dependências:** advisories indiretos de Starlette não são alcançáveis pelo código atual, mas continuam registrados até uma atualização coordenada do framework.
