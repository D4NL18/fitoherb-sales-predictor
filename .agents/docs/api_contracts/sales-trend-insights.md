# Contrato de API: Diagnóstico de Motivos da Tendência de Vendas com IA (`trend-insights`)

> **Localização Mandatória:** `.agents/docs/api_contracts/sales-trend-insights.md`
> **Responsável:** Arquiteto (`api-contract-expert`)
> **Referências de Regras:** `.agents/rules/backend-api-contract-rules.md`, `architecture-error-handling-rules.md`, `backend-db-performance-rules.md`, `security-anti-patterns.md`, `ai-llm-integration-rules.md`

| Campo | Valor |
| :--- | :--- |
| **Módulo backend** | `src/modules/trend_insights/` (FastAPI + Pydantic v2), ADR-009 |
| **Consumidor** | `frontend/src/app/features/sales-trend/` (painel "Por que?" da página `/tendencia-vendas`) |
| **Versão do contrato** | **1.2.0** (`meta.version`, constante `TREND_INSIGHTS_CONTRACT_VERSION`). Investigação externa v3 (radar externo compartilhado e checklist de 8 dimensões, ADR-009 DA-13), aditiva sobre a 1.1.x. Histórico na seção 0 |
| **Regras** | `P-150` a `P-188` (`business_rules/analytics-tendencia-ia.md`; revisões v2 de P-174..P-181 e P-183 e a nova P-188 a cargo do `analyst`); reaproveita `P-072..P-093` (Tendência) e `P-128..P-138` (Canibalização) |
| **Decisões** | `adr/ADR-009-diagnostico-tendencia-ia.md` (DA-01 a DA-12, CP-1 a CP-15) |
| **Camada de IA** | `architecture/trend-insights-llm.md` (`ai_specialist`): prompt, schema do LLM, grounding. Este contrato define só o que sai da API, já validado |
| **Autenticação** | HTTP Basic do middleware global (`src/core/auth.py`, P-033) em todas as rotas `/api/v1/...`. A rota interna `POST /internal/v1/affinity-index/sync` usa **token OIDC do Google** (3.5) |
| **Privacidade** | Zero `Cod Cliente`, nome, documento ou contato de cliente em qualquer campo (P-185). Contagens por UF abaixo de 3 clientes são agregadas em `"OUTRAS"` (P-167). Custos unitários do ERP não aparecem; margem só como `netMarginImpact` e mecanismo. **Custos de IA (dólares, tokens, consultas de busca, preços, tetos, livro de gastos) nunca saem da API** (4.4). O texto da IA não contém números |
| **Autor / Data** | Arquiteto (Etapa 2) — 2026-11-24 (revisão v2, mesma data) |

---

## 0. Histórico de versões

| Versão | Mudanças |
| :--- | :--- |
| 1.0.0 | Primeira versão do desenho (nunca implantada). |
| **1.1.0** | **Removidos:** `deep` no corpo do `POST`, `meta.tipoAnalise`, `meta.escalonadoAutomaticamente`, `meta.ia.escalonamentoPrevisto`, aviso `ESCALONAMENTO_NEGADO_POR_ORCAMENTO`, o modelo `gemini-4-neon`, o botão "Análise aprofundada", `diagnosticoIa.desatualizado`, aviso `DIAGNOSTICO_DESATUALIZADO`, `503 TIA-004` de IA (viram `200` com template), `credencialConfigurada` e valores em dólar de `meta.ia.orcamento` e de `health`. **Acrescentados:** `meta.origem` (`llm`\|`cache`\|`template`\|`fallback`) no `POST`, `diagnosticoIa.origem`, `meta.motivoTemplate`, `meta.ia.{geraComIa, motivoTemplate, podeForcar, diagnosticoVencido, orcamento.nivel}`, `diagnosticoIa.explicacao` (≤ 160), aviso `SEM_BUSCA_EXTERNA`, motivo `LIMITE_DIARIO` em `429 TIA-004`, códigos oficiais `TIA-006` (401) e `TIA-007` (409). **Alterados:** `modelo` ∈ {`gemini-4-hydrogen`, `gemini-3.8-flash`}; `promptVersion = "tia-v2"`; chave do diagnóstico com `evidenceHash` no lugar de `dataReferencia`; limites do diagnóstico (5 fatores, 2 fontes por fator, 3 hipóteses, 3 recomendações, `resumo` ≤ 400); texto da IA **sem números**; migração lida **sempre** com 4 datas. Mudança incompatível com a 1.0.0, que nunca teve consumidor. |
| **1.2.0** | **Investigação externa v3 (ADR-009 DA-13), aditiva e compatível com a 1.1.x. Acrescentados:** `diagnosticoIa.fatoresExternos[8]` (uma linha fixa por dimensão externa, com `direcao`, `confianca`, `relevanciaAoProduto`, `relacaoTemporal`, `rotulo`, `origemEvidencia`, `tema`, `notaRadar`, `nota` e `fontes` por id, incluindo o estado explícito `SEM_EVIDENCIA`); `diagnosticoIa.radar` (origem `GERADO_AGORA`\|`CACHE`, idade e `desatualizado`); `meta.ia.radar` (`estado`, `geradoEm`); `data.radarExterno` somente leitura (GET e `POST` em template, sem `direcao`); `fonte.id`; `fatores[].dimensao`; motivos de hipótese `POSTERIOR_AO_PERIODO` e `SEM_COERENCIA_DIRECIONAL`; `motivoNaoAvaliado` `SEM_RADAR`, `SEM_TERMO_BUSCA`, `DIMENSAO_OMITIDA_PELA_IA`; avisos `RADAR_DESATUALIZADO` e `SEM_RADAR_EXTERNO`; `health.radar` e `ia.modeloRadar`. **Alterados:** `promptVersion = "tia-v3"`; `SEM_BUSCA_EXTERNA` passa a significar "sem radar e sem busca do produto"; `origemData` aceita `SEM_DATA`; prazo de IA de 110 s para **125 s** (HTTP 150 s inalterado). **Inalterado:** custo, tokens, consultas e orçamento seguem fora da API (4.4); a chave do diagnóstico não inclui o radar. |
| 1.1.1 | **Renomeadas** as chaves que continham `preco` para nao colidir com a varredura de custos do 4.4 (T-7.2.9), sem expor preco de IA: `afins[].precoAtual` -> `valorVendaAtual`; `detalhe` do fator `PRECO`: `precoMedioAnterior`/`precoMedioAtual`/`variacaoPrecoPct` -> `valorMedioAnterior`/`valorMedioAtual`/`variacaoValorPct`. Sao preco de venda do produto (dado de negocio), nao custo de IA. Sem consumidor implantado. |

---

## 1. Visão Geral

- **Prefixo Base:** `/api/v1/sales-trend/insights` (rotas públicas) e `/internal/v1` (rota de máquina).
- **Protocolo:** HTTP/REST síncrono, `application/json; charset=utf-8`.
- **Convenção de Nomenclatura:** `camelCase` em query params, corpo e respostas (atributos Python em `snake_case` com `alias_generator=to_camel`). Campos de negócio em português, alinhados ao Glossário (seção 6) e às regras; os termos já públicos da F6 mantêm o nome original (`sameSupplier`, `affinityScore`, `netMarginImpact`). Enums de entrada em inglês minúsculo (`revenue`, `quantity`, `point`, `average`), enums de domínio em maiúsculas (`QUANTITATIVO`, `CANIBALIZACAO_OUTRO_FORNECEDOR`).
- **Princípio:** todo número vem do Motor de Evidências; **o texto da IA não contém números** (ficam nos campos numéricos). O LLM só é chamado por `POST .../generate`, nunca por `GET`, nunca automaticamente (P-174). O `POST` responde sempre `200` com diagnóstico de IA (`llm`/`fallback`/`cache`) ou **resumo por template** (`template`, sem LLM, custo zero); a IA indisponível, desligada ou sem orçamento não é erro.

| Método | Rota | Descrição | Chama o LLM? | Fase | Regras |
| :--- | :--- | :--- | :-: | :-: | :--- |
| `GET` | `/api/v1/sales-trend/insights/product/{sku}` | Cascata, grupo afim, diagnóstico de mercado e, se existir, o diagnóstico de IA já salvo | Não | 7.1 | P-150..P-174 |
| `POST` | `/api/v1/sales-trend/insights/product/{sku}/generate` | Gera (ou reutiliza) o diagnóstico com IA, ou devolve resumo por template | Só se não houver salvo (ou `force=true`) **e** os gates, o orçamento e o kill-switch liberarem | 7.2 | P-174..P-184, P-188 |
| `GET` | `/api/v1/sales-trend/insights/supplier/{supplierKey}` | Visão por fornecedor (soma das cascatas e canibalização interna do portfólio) | Não | **7.4** | P-172 |
| `GET` | `/api/v1/sales-trend/insights/health` | Modelos, IA ligada (booleano), nível do orçamento, índice de afinidade, cache de migração | Não | 7.1 (parte de IA em 7.2) | P-187 |
| `POST` | `/internal/v1/affinity-index/sync` | Sincroniza o índice de afinidade no GCS; chamada pelo Cloud Scheduler | Não | 7.0 (c) | P-130.4..P-130.12, ADR-009 DA-06 |

### 1.1 Ordem de avaliação (rotas de produto)

1. Formato e domínio dos parâmetros → `400 TIA-001`.
2. Snapshot da Tendência indisponível → `503 ANL-001`.
3. `baseMonth` futuro → `400 TIA-001` (`fields: ["baseMonth"]`); anterior à base ou sem dia coberto → `422 TIA-003`.
4. SKU fora do Catálogo Ativo → `404 TIA-002`.
5. Só no `POST`: modo `SEM_VARIACAO` → `422 TIA-003`; diagnóstico salvo (chave com `evidenceHash`) e `force=false` → `200` com `origem = "cache"` (pula 6 a 9); `force=true` acima de `FORCE_MAX_PER_USER_PER_DAY` ou com orçamento em `ALERTA`/`ESGOTADO` → `429 TIA-004` (`LIMITE_DIARIO`) ou ignora o `force` e devolve o salvo, conforme `meta.ia.podeForcar`.
6. Só no `POST`: kill-switch (`TREND_AI_ENABLED=false`) ou Vertex indisponível → `200` com `origem = "template"` (`IA_DESLIGADA`/`IA_INDISPONIVEL`).
7. Só no `POST`: gates de não chamada (P-188: variação ínfima, base insuficiente, delta financeiro < R$ 1.000, resíduo < 0,20 sem `REGIONAL` e sem diagnóstico de mercado) → `200` com `origem = "template"` (`GATE_*`).
8. Só no `POST`: rate limit (2/min, 10/dia por usuário) → `429 TIA-004`; reserva no livro de gastos negada (mês, dia ou saldo) ou livro indisponível → `200` com `origem = "template"` (`ORCAMENTO_ESGOTADO`).
9. Só no `POST`: dedup em voo (aguarda o resultado do pedido em curso para a mesma chave).
10. Só no `POST`: chamada ao Hydrogen; falha de infraestrutura após 2 tentativas → 1 chamada ao `gemini-3.8-flash` (`origem = "fallback"`); falha geral → `200` com `origem = "template"` e aviso `IA_FALHOU` (P-183.3). Nada é salvo em caso de falha (P-175.5).

Fontes internas que falham (afinidade, sazonalidade, elasticidade, churn, estoque, promoção, UF) **não** geram erro: a parcela fica `NAO_AVALIADO` (P-173).

---

## 2. Padrão de Envelope de Resposta

### 2.1 `meta` comum (`InsightMeta`)

| Campo | Tipo | Descrição | Regra |
| :--- | :--- | :--- | :--- |
| `timestamp` | string ISO-8601 UTC | Momento da resposta | — |
| `version` | string | `"1.2.0"` | P-186 |
| `dataReferencia` | string `AAAA-MM-DD` | Data de referência da snapshot da Tendência (UTC−3); entra na chave do diagnóstico | P-175, P-083.3 |
| `ultimoDiaCoberto` | string `AAAA-MM-DD` | `dataReferencia − 1 dia` | P-076.1 |
| `mesBase` | string `AAAA-MM` | Mês-Base efetivo | P-150 |
| `metrica` | `"revenue"` \| `"quantity"` | Métrica efetiva | P-150 |
| `janela` | `1` \| `3` \| `6` \| `12` | Tamanho da janela | P-150 |
| `modoComparacao` | `"point"` \| `"average"` | Modo efetivo | P-150, P-151 |
| `promptVersion` | string | Versão do prompt em vigor (`"tia-v3"`) | P-175 |
| `indiceAfinidade` | `{ disponivel: boolean, lastSyncAt: string \| null }` | Estado do índice usado no cálculo | P-173 |
| `avisos` | `InsightWarning[]` | Avisos não bloqueantes (2.2); lista vazia quando não há | P-173, P-186 |
| `ia` | `InsightAiState` (abaixo) | Estado do botão de IA, presente no `GET` e no `POST` das rotas de produto (Design Plan Q-D7) | P-152, P-175, P-176, P-178.5 |

**`meta.ia` (`InsightAiState`):**

| Campo | Tipo | Descrição |
| :--- | :--- | :--- |
| `podeGerar` | boolean | `false` apenas quando há `motivoBloqueio` ou `geracaoEmAndamento`. Orçamento esgotado, IA desligada e gates **não** bloqueiam o botão: o clique devolve o resumo por template |
| `motivoBloqueio` | `"SEM_VARIACAO"` \| `null` | Por que o botão está desabilitado (limites de pedidos só são conhecidos no `POST`) |
| `geraComIa` | boolean | `false` quando o clique devolveria template (gate, kill-switch, orçamento, IA indisponível): a tela troca o rótulo para "Gerar resumo automático" |
| `motivoTemplate` | `"GATE_VARIACAO"` \| `"GATE_RESIDUO_BAIXO"` \| `"GATE_VALOR_BAIXO"` \| `"ORCAMENTO_ESGOTADO"` \| `"IA_DESLIGADA"` \| `"IA_INDISPONIVEL"` \| `null` | Previsão do motivo quando `geraComIa = false` |
| `diagnosticoSalvo` | boolean | Existe diagnóstico salvo para a chave atual (botão vira "Atualizar"/"Gerar de novo") |
| `diagnosticoSalvoEm` | string ISO-8601 UTC \| `null` | Data da análise salva |
| `diagnosticoVencido` | boolean | TTL lógico de 30 dias (`INSIGHT_SOFT_TTL_DAYS`) vencido: a tela mostra "gerado há N dias" e oferece "Atualizar" (explícito) |
| `podeForcar` | boolean | `false` em orçamento `ALERTA`/`ESGOTADO` ou com `force` do dia esgotado: desabilita "Gerar de novo"/"Atualizar" |
| `geracaoEmAndamento` | boolean | Há lease de geração em voo para a chave (qualquer instância); a tela mostra "gerando" e refaz o `GET` em alguns segundos |
| `radar` | `{ estado, geradoEm }` | Estado do radar externo do assunto do produto para o mês-base: `estado` ∈ `FRESCO`, `DESATUALIZADO` (passou do prazo e foi usado como contexto), `AUSENTE` (não existe e não será gerado nesta resposta), `GERADO_AGORA` (só no `POST`); `geradoEm` ISO-8601 UTC ou `null`. O `GET` só **lê** o radar: nunca o gera (custo zero) |
| `orcamento` | `{ nivel }` | `nivel` ∈ `NORMAL`, `ALERTA` (≥ 80%), `ESGOTADO`. **Sem valores em dólar, percentuais, teto ou saldo** (4.4). Cache de até 60 s |

**Só no `POST /generate`** (`GenerateMeta`, estende `InsightMeta`):

| Campo | Tipo | Descrição | Regra |
| :--- | :--- | :--- | :--- |
| `origem` | `"cache"` \| `"template"` \| `"llm"` \| `"fallback"` | Como esta resposta foi obtida: `cache` = diagnóstico salvo reaproveitado (custo zero; inclui aguardar pedido em voo); `template` = resumo determinístico sem LLM (`diagnosticoIa = null`, tela rotula "Resumo automático (sem IA)"); `llm` = gerado agora pelo `gemini-4-hydrogen`; `fallback` = gerado agora pelo `gemini-3.8-flash` | P-174, P-175, P-177, P-188 |
| `motivoTemplate` | enum de `meta.ia.motivoTemplate` \| `null` | Preenchido só quando `origem = "template"` | P-188 |
| `modelo` | `"gemini-4-hydrogen"` \| `"gemini-3.8-flash"` \| `null` | Modelo que gerou o diagnóstico devolvido; `null` no `template`. Em `cache`, o modelo que o gerou | P-177 |
| `geradoEm` | string ISO-8601 UTC \| `null` | Momento da geração do diagnóstico devolvido; `null` no `template` | P-175.1 |
| `reutilizado` | boolean | `true` quando `origem = "cache"` (atalho de `origem` para a tela) | P-175.1, P-176.2 |

### 2.2 `InsightWarning`

```json
{ "codigo": "TIA-005", "mensagem": "Índice de produtos afins em atualização: canibalização e grupo afim não avaliados." }
```

| `codigo` | Quando | Mensagem fixa |
| :--- | :--- | :--- |
| `TIA-005` | Índice de afinidade indisponível (P-173) | "Índice de produtos afins em atualização: canibalização e grupo afim não avaliados." |
| `FORNECEDOR_NAO_INFORMADO` | SKU sem fornecedor no catálogo (P-154.2) | "Fornecedor do produto não informado." |
| `IA_FALHOU` | Só no `POST`: a tentativa de IA falhou e a resposta é template (P-183.3) | "Não foi possível gerar a análise com IA agora. Exibindo o resumo automático." |
| `SEM_BUSCA_EXTERNA` | Só no `POST`: a análise saiu **sem radar e sem busca do produto** (1.2.0; antes: fallback Flash sem *grounding*) | "Análise feita sem busca externa." |
| `RADAR_DESATUALIZADO` | Radar usado como contexto (ou exibido) passou do prazo de validade (`meta.ia.radar.estado = DESATUALIZADO`); a confiança externa é `BAIXA` | "Os fatores externos usam uma pesquisa desatualizada." |
| `SEM_RADAR_EXTERNO` | Só no `POST`: não havia radar utilizável e nenhum foi gerado (falha, limite de uso, orçamento ou assunto sem termo); as 8 dimensões saem `NAO_AVALIADA` | "Fatores externos não avaliados nesta análise." |

A tela decide pelo `codigo`, nunca pelo texto.

### 2.3 Precisão numérica

| Campo | Tipo | Precisão |
| :--- | :--- | :--- |
| Valores em R$ (`valor` com `metrica=revenue`, `valorReceita`, `receitaMigrada`, `netMarginImpact`, `totalInterno`, `totalConcorrentes`, `efeitoMercado`...) | number | 2 casas, meio para cima (P-169.6) |
| Valores em unidades (`metrica=quantity`) | number | 3 casas |
| Percentuais (`variacaoPct`, `variacaoMercadoPct`, `coberturaExplicacaoPct`, `participacao*Pct`) | number | 1 casa |
| Pontos percentuais (`variacaoParticipacaoPp`, `pontosPercentuais`) | number | 1 casa |
| `affinityScore` | number | 3 casas (0..1) |
| `fatorAjuste` | number | 6 casas (o cálculo usa `Fraction`) |

### 2.4 Enums

| Enum | Valores |
| :--- | :--- |
| `modoDiagnostico` | `QUANTITATIVO`, `QUALITATIVO`, `SEM_VARIACAO` (P-152) |
| `direcao` | `QUEDA`, `ALTA`, `null` (em `SEM_VARIACAO` e `SEM_BASE`) |
| `diagnosticoMercado.classificacao` | `MERCADO_EM_QUEDA`, `MERCADO_EM_ALTA`, `PERDA_DE_PARTICIPACAO`, `GANHO_DE_PARTICIPACAO`, `MISTO`, `SEM_GRUPO_AFIM`, `NAO_AVALIADO` (P-156) |
| `parcela.tipo` (cascata) | `SAZONALIDADE`, `PRECO`, `PRODUTO_NOVO`, `CANIBALIZACAO_MESMO_FORNECEDOR`, `CANIBALIZACAO_OUTRO_FORNECEDOR`, `CLIENTES_PERDIDOS` (P-157) |
| `indicador.tipo` | `RUPTURA`, `PROMOCAO`, `REGIONAL`, `PERDA_PARTICIPACAO_SEM_MIGRACAO` |
| `status` (parcela/indicador) | `AVALIADO`, `SEM_EFEITO`, `NAO_AVALIADO` |
| `motivoNaoAvaliado` | `JANELA_ANTERIOR_INCOMPLETA`, `INDICE_AFINIDADE_INDISPONIVEL`, `FONTE_INDISPONIVEL`, `MES_BASE_ANTIGO`, `SEM_PRECO_MEDIO`, `CONFIANCA_BAIXA_SAZONAL`, `MODO_QUALITATIVO`, `ANONIMIZACAO` |
| `clientesMigrados` / `clientesPerdidosQtd` | inteiro ≥ 3 ou `"<3"` (LGPD-TIA-06) |
| `fonte.origemData` | `MODELO`, `URL`, `SEM_DATA`, `null` |
| `dimensao` (`fatoresExternos[]`, `radarExterno.dimensoes[]`, `fatores[].dimensao`) | `POLITICA_REGULATORIO`, `CLIMA_SAFRA`, `CUSTO_MATERIA_PRIMA`, `OFERTA_DEMANDA_MATERIA_PRIMA`, `CAMBIO_LOGISTICA_IMPORTACAO`, `CONSUMO_MIDIA_SAUDE`, `CONCORRENCIA`, `EVENTOS_MERCADO` (8, ordem fixa) |
| `fatorExterno.status` | `AVALIADA`, `SEM_EVIDENCIA` (avaliada, nada relevante achado; **não** significa "não houve"), `NAO_AVALIADA` |
| `fatorExterno.direcao` | `PRESSAO_ALTA`, `PRESSAO_BAIXA`, `NEUTRA` (só com fonte que diga estabilidade), `INDETERMINADA` (padrão de `SEM_EVIDENCIA`/`NAO_AVALIADA`) |
| `fatorExterno.confianca` | `MEDIA`, `BAIXA` (**nunca `ALTA`**) |
| `fatorExterno.relevanciaAoProduto` | `ALTA`, `MEDIA`, `BAIXA`, `NENHUMA` |
| `fatorExterno.relacaoTemporal` | `ANTERIOR`, `CONTEMPORANEA`, `POSTERIOR`, `SEM_DATA`, `ANTIGA`, `null` (calculada pelo backend contra a Janela Atual) |
| `fatorExterno.rotulo` | `POSSIVEL`, `CONTEXTO` (`POSTERIOR`), `SEM_DATA`, `DESCARTADA` (`ANTIGA`), `SEM_EVIDENCIA` |
| `fatorExterno.origemEvidencia` | `RADAR`, `BUSCA_PRODUTO`, `NENHUMA` |
| `fatorExterno.motivoNaoAvaliado` | `SEM_RADAR`, `SEM_TERMO_BUSCA`, `DIMENSAO_OMITIDA_PELA_IA`, `null` |
| `radar.dimensoes[].movimento` | `SUBIU`, `CAIU`, `ESTAVEL`, `MUDOU`, `INDEFINIDO` |
| `radar.dimensoes[].intensidade` | `FORTE`, `MODERADA`, `FRACA`, `null` |
| `radar.dimensoes[].tema` | Lista fechada por dimensão (`RADAR_THEMES` do backend, inclui `OUTRO`); o texto exibido vem de frase fixa do backend (`notaRadar`), nunca do conteúdo da web |
| `radar.origem` | `GERADO_AGORA`, `CACHE` |
| `radar.assunto.tipo` | `MATERIA_PRIMA`, `CATEGORIA` |
| `meta.ia.radar.estado` | `FRESCO`, `DESATUALIZADO`, `AUSENTE`, `GERADO_AGORA` |
| `motivoSemEfeito` | `HISTORICO_CURTO`, `VENDA_ESPORADICA`, `FRACA`, `MESMOS_MESES`, `VARIACAO_PRECO_PEQUENA`, `SEM_PARES`, `NAO_SE_APLICA_A_ALTA`, `SEM_CLIENTES_PERDIDOS`, `SEM_RUPTURA`, `SEM_PROMOCAO`, `SEM_CONCENTRACAO` |
| `sentido` | `NEGATIVO`, `POSITIVO` |
| `confianca` | `ALTA`, `MEDIA`, `BAIXA` |
| `mecanismo` | `PRECO_MENOR_DESTROI_MARGEM`, `PRECO_MENOR_MARGEM_PRESERVADA`, `MIGRACAO_POR_VALOR` (F6) |
| `tipoImpacto` | `CANIBALIZACAO_INTERNA`, `GANHO_SOBRE_CONCORRENTE` (P-171) |
| `fator.tipo` (IA) | internos: os 6 da cascata + `PERDA_PARTICIPACAO_SEM_MIGRACAO`, `RUPTURA`, `PROMOCAO`, `REGIONAL`; externos: `CLIMA`, `POLITICO_REGULATORIO`, `MATERIA_PRIMA`, `CONCORRENCIA_MERCADO`, `OUTRO` (P-181) |
| `hipotese.motivo` | `SEM_FONTE`, `FONTE_NAO_CITADA`, `SEM_DATA`, `FORA_DO_PERIODO` (P-182.4), `SKU_FORA_DO_PACOTE` (`trend-insights-llm.md` CP-8), `POSTERIOR_AO_PERIODO` (fonte posterior à Janela Atual: contexto, nunca causa), `SEM_COERENCIA_DIRECIONAL` (direção do fator contrária ao sentido da variação) |
| `meta.ia.motivoBloqueio` | `SEM_VARIACAO`, `null` |
| `motivoTemplate` | `GATE_VARIACAO`, `GATE_RESIDUO_BAIXO`, `GATE_VALOR_BAIXO`, `ORCAMENTO_ESGOTADO`, `IA_DESLIGADA`, `IA_INDISPONIVEL` |
| `meta.origem` (`POST`) | `cache`, `template`, `llm`, `fallback` (minúsculas, exceção à convenção de enums de domínio por decisão do coordenador) |
| `diagnosticoIa.origem` | `llm`, `fallback` |
| `modelo` | `gemini-4-hydrogen`, `gemini-3.8-flash` (nunca `gemini-4-neon`) |
| `meta.ia.orcamento.nivel` | `NORMAL`, `ALERTA`, `ESGOTADO` |
| `hipotese.motivo` (inclui `SEM_DATA`) | ver linha acima; `SEM_DATA` = fonte sem data de publicação confiável, nunca vira fator |

---

## 3. Endpoints

### 3.1 `GET /api/v1/sales-trend/insights/product/{sku}`

- **Objetivo:** abrir o painel "Por que?" sem custo de token (P-174): célula, cascata, grupo afim, diagnóstico de mercado, impacto em outros produtos e o diagnóstico de IA salvo para a mesma chave, se houver.
- **Cache:** pacote de evidências em memória por chave completa (TTL 6 h); migração por `(modo, janela, mesBase, dataReferencia, geração do índice)` (ADR-009 DA-04/DA-05). A primeira abertura de uma janela sem cache pode levar alguns segundos (skeleton).

**Path Parameters:**

| Parâmetro | Tipo | Validação | Erro |
| :--- | :--- | :--- | :--- |
| `sku` | integer | `1..2147483647` | `400 TIA-001` (`fields: ["sku"]`); fora do Catálogo Ativo → `404 TIA-002` |

**Query Parameters (todos opcionais):**

| Parâmetro | Tipo | Default | Validação | Regra |
| :--- | :--- | :--- | :--- | :--- |
| `metric` | string | `revenue` | `revenue` \| `quantity` | P-150 |
| `window` | integer | `3` | `1`, `3`, `6`, `12` | P-150 |
| `baseMonth` | string | `mesBasePadrao` da Tendência | `^\d{4}-(0[1-9]\|1[0-2])$`; futuro → `400`; sem base → `422 TIA-003` | P-150, P-151 |
| `comparisonMode` | string | `point` | `point` \| `average` (`range` → `400 TIA-001`, ADR-009 CP-7) | P-150, P-151 |

Parâmetros desconhecidos são ignorados. Mensagens e logs nunca ecoam valores recebidos.

**Resposta `200` — `data` (`ProductInsight`):**

| Campo | Tipo | Descrição | Regra |
| :--- | :--- | :--- | :--- |
| `produto` | `{ sku, descricao, fornecedor \| null, categoriaGaleria \| null, funcaoPrimaria \| null }` | Identificação (catálogo ativo + índice de afinidade) | P-179 |
| `periodo` | `{ atual: Span, anterior: Span, fatorAjuste, baseParcial, contigua }` | Datas efetivas das janelas. `Span = { inicio, fim, diasJanela, diasCobertos }` (`fim` inclusivo). `contigua = false` no `point` com janela > 1 | P-151 |
| `celula` | `TrendCell` | **Mesma** célula do contrato `analytics-sales-trend.md` §4 (`meses`, `atual`, `anterior`, `variacaoPct`, `status`, `baseParcial`, `baseBaixa`, `devolucaoLiquida`, `atualPorDia`, `anteriorPorDia`) | P-152 |
| `modoDiagnostico` | enum | 2.4 | P-152 |
| `direcao` | enum \| `null` | Sinal de `deltaObservado` | P-171 |
| `resumoNumerico` | `{ baseAjustada, deltaObservado, somaParcelas, residuo, coberturaExplicacaoPct } \| null` | Na escala da Janela Atual e na métrica da célula. `null` fora do `QUANTITATIVO` | P-151.4, P-168, P-169.6 |
| `cascata` | `Parcela[6]` | Sempre as 6 parcelas na ordem de P-157 (3.1.1) | P-157..P-164, P-169 |
| `indicadores` | `Indicador[]` | `RUPTURA`, `PROMOCAO`, `REGIONAL`, `PERDA_PARTICIPACAO_SEM_MIGRACAO`, nesta ordem, fora da soma (3.1.2) | P-165..P-168 |
| `diagnosticoMercado` | `DiagnosticoMercado` (3.1.3) | Shift-share e classificação | P-155, P-156 |
| `grupoAfim` | `{ status, afins: AfimItem[] }` (3.1.4) | Até 25 vizinhos com score ≥ 0,50 do Catálogo Ativo | P-154 |
| `impactoEmOutrosProdutos` | `ImpactoEmOutrosProdutos \| null` (3.1.5) | Preenchido em `ALTA` e em `NOVO`; `null` em `QUEDA` | P-171 |
| `diagnosticoIa` | `DiagnosticoIa \| null` (3.1.6) | O salvo para a mesma chave; `null` se ainda não gerado | P-174, P-175 |
| `radarExterno` | `RadarExterno \| null` (3.1.6.2) | **Novo (1.2.0).** Radar externo existente (fresco ou desatualizado) do assunto do produto, somente leitura, **sem `direcao` nem `relevanciaAoProduto`**; `null` se não houver radar ou se `diagnosticoIa` estiver preenchido (a tela usa `fatoresExternos`). Exibido como "Radar externo de N dias (sem análise de IA para este produto)". Nunca dispara geração | P-174.1, P-180 |

O estado do botão de IA fica em `meta.ia` (2.1).

#### 3.1.1 `Parcela`

| Campo | Tipo | Descrição |
| :--- | :--- | :--- |
| `tipo` | enum | 2.4 |
| `status` | `AVALIADO` \| `SEM_EFEITO` \| `NAO_AVALIADO` | No `QUALITATIVO`, `AVALIADO` = fator presente, `SEM_EFEITO` = ausente |
| `valor` | number \| `null` | Na métrica da célula, escala da Janela Atual, com sinal. `null` fora de `AVALIADO` no `QUANTITATIVO` e sempre `null` no `QUALITATIVO` |
| `pontosPercentuais` | number \| `null` | `valor ÷ baseAjustada × 100`, com sinal, 1 casa (Design Plan Q-D1). A soma das parcelas mais o resíduo em pp reproduz o `variacaoPct` da célula (diferença só de arredondamento). `null` quando `valor` é `null` |
| `valorReceita` | number \| `null` | R$ antes da conversão, só com `metrica=quantity` nas parcelas de migração (P-163) |
| `sentido` | `NEGATIVO` \| `POSITIVO` \| `null` | |
| `explicativa` | boolean \| `null` | `true` quando tem o sentido de `deltaObservado`; `false` = compensatória (P-169.2) |
| `cortada` | boolean | P-169.2 |
| `confianca` | enum \| `null` | P-169.4 |
| `motivoNaoAvaliado` / `motivoSemEfeito` | enum \| `null` | 2.4 |
| `detalhe` | objeto \| `null` | Evidência da parcela: `SAZONALIDADE` → `{ indiceAtual, indiceAnterior, forca }`; `PRECO` → `{ valorMedioAnterior, valorMedioAtual, variacaoValorPct, elasticidade, observacoes[] }`; `CLIENTES_PERDIDOS` → `{ clientesPerdidosQtd }`; migração → `null` (ver `itens`) |
| `itens` | `MigracaoItem[]` | Só nas parcelas de migração (`PRODUTO_NOVO`, `CANIBALIZACAO_*`); lista vazia nas demais |

`MigracaoItem`: `{ sku, descricao, fornecedor, sameSupplier, affinityScore, lancamento, receitaMigrada, clientesMigrados, confianca, mecanismo, netMarginImpact }`. `receitaMigrada` é o `netRev` (R$) do par já ajustado por `k`; `null` no `QUALITATIVO` (só a contagem aparece). `clientesMigrados` = `netClients` como **inteiro quando ≥ 3** ou a faixa **`"<3"`** abaixo disso (LGPD-TIA-06; nunca o valor exato 1 ou 2). A mesma regra vale para `detalhe.clientesPerdidosQtd` de `CLIENTES_PERDIDOS` e para `clientesMigrados` em `impactoEmOutrosProdutos`.

#### 3.1.2 `Indicador`

`{ tipo, status, sentido, confianca, valor, motivoSemEfeito, motivoNaoAvaliado, evidencia }` com `valor` sempre `null`, exceto `PERDA_PARTICIPACAO_SEM_MIGRACAO` (leitura do resíduo, P-168.1). `evidencia` por tipo:
- `RUPTURA`: `{ estoqueAtual, statusEstoque, observacao }`.
- `PROMOCAO`: `{ produtoEmPromocaoAnterior, produtoEmPromocaoAtual, afinsEmPromocaoSoNaAtual: int[] }`.
- `REGIONAL`: `{ ufConcentradora, participacaoPct, porUf: [{ uf, delta, participacaoPct }] }`. Anonimização (P-167, LGPD-TIA-05): UF com menos de 3 clientes distintos na janela entra em `uf: "OUTRAS"`; `"OUTRAS"` **só aparece se somar pelo menos 3 clientes**, senão absorve a menor UF exibida até atingir o piso; se ainda assim não for possível, o indicador fica `NAO_AVALIADO` com `motivoNaoAvaliado = "ANONIMIZACAO"` e `evidencia = null`. `ufConcentradora` nunca é `"OUTRAS"`. Nenhuma contagem de clientes é exposta.
- `PERDA_PARTICIPACAO_SEM_MIGRACAO`: `{ afinsQueCresceramSemClientesDoProduto: int[] }`.

#### 3.1.3 `DiagnosticoMercado`

`{ classificacao, variacaoMercadoPct, efeitoMercado, efeitoParticipacao, participacaoAnteriorPct, participacaoAtualPct, variacaoParticipacaoPp, variacaoAfinsMesmoFornecedorPct, variacaoAfinsOutroFornecedorPct }`. Todos os números `null` quando `classificacao ∈ { SEM_GRUPO_AFIM, NAO_AVALIADO }`.

#### 3.1.4 `AfimItem`

`{ sku, descricao, fornecedor, sameSupplier, affinityScore, categoriaGaleria, valorVendaAtual, celula: TrendCell, ganhouClientesDoProduto, lancamento }`. `celula` é a **mesma** `TrendCell` do contrato `analytics-sales-trend.md` §4 (mesma janela, métrica e modo), para a tela reusar o componente de célula da Tendência (Design Plan Q-D3). `grupoAfim.status`: `AVALIADO`, `SEM_GRUPO_AFIM`, `NAO_AVALIADO`.

#### 3.1.5 `ImpactoEmOutrosProdutos`

`{ totalInterno, totalConcorrentes, itens: [{ sku, descricao, fornecedor, sameSupplier, affinityScore, tipoImpacto, receitaMigrada, clientesMigrados, confianca, mecanismo, netMarginImpact, estoqueZerado }] }`, até 10 itens por `receitaMigrada` decrescente. `mecanismo`/`netMarginImpact` vêm de `calculate_price_equilibrium(victim = item, cannibal = produto)`.

#### 3.1.6 `DiagnosticoIa`

| Campo | Tipo | Origem |
| :--- | :--- | :--- |
| `direcao`, `diagnosticoMercado` | enum | Backend (cópia do motor) |
| `resumo` | string ≤ 400 | LLM; **texto puro sem números** (nenhum dígito, valor, percentual ou código de SKU); cita produtos por descrição e as grandezas ficam nos campos numéricos do motor (P-182.1 revisada) |
| `fatores[]` | ≤ 5 `{ tipo, sentido, parcelaEstimada, confianca, rotulo, explicacao, evidenciaInterna, skusCitados[], fontes[] }` | `parcelaEstimada` copiada da cascata (`null` em externos e no `QUALITATIVO`); `rotulo = "POSSIVEL"` em fatores externos (teto `MEDIA`, P-182.5), `"EVIDENCIA"` nos internos; `explicacao` ≤ 160 caracteres, texto do LLM **sem números**, mesmas restrições do `resumo`; `fontes[]` ≤ 2 por fator; `skusCitados` são ids do pacote (a tela mostra nome e célula do produto) |
| `fonte` | `{ url, dominio, titulo, dataPublicacao, origemData }`. `titulo` vem da citação da fonte (não é texto da IA e pode conter dígitos) | `dataPublicacao` (`AAAA-MM-DD`) é **anulável**: o *grounding* não devolve data; ela vem da leitura do modelo (`origemData = "MODELO"`) ou do caminho da URL (`"URL"`). Fontes de fatores aceitos sempre têm data válida (P-182.4); fontes com data nula só aparecem em hipóteses |
| `hipotesesNaoConfirmadas[]` | ≤ 3 `{ tipo, descricao ≤ 120, motivo, fontes[] }` | P-182.4; `fontes[]` pode vir vazio ou com fontes rejeitadas (`SEM_DATA`, `FORA_DO_PERIODO`) para o usuário conferir. `descricao` sem números |
| `recomendacoes[]` | ≤ 3 strings (≤ 120 caracteres cada) | LLM, mesmas restrições do `resumo` (sem números) |
| `fatoresExternos` | `FatorExterno[8]` (3.1.6.1) | **Novo (1.2.0).** Sempre 8 itens na ordem fixa de `dimensao`; dimensão nunca omitida |
| `radar` | `RadarRef \| null` (3.1.6.2) | **Novo (1.2.0).** Origem e idade do radar usado; `null` quando as dimensões saíram `NAO_AVALIADA` por `SEM_RADAR` |
| `sugestoesBuscaHtml` | string \| `null` | **Opcional e pendente do checkpoint (ADR-009 CP-10).** HTML das *Search Suggestions* exigido pelos Termos do *grounding*. Se o checkpoint aprovar, a tela o renderiza **só** em `<iframe sandbox>` (sem `allow-scripts` do nosso domínio, sem `innerHTML` na página); caso contrário, o campo vem sempre `null` |
| `origem`, `modelo`, `geradoEm`, `promptVersion` | | Backend. `origem` ∈ `llm`, `fallback`; `modelo` ∈ `gemini-4-hydrogen`, `gemini-3.8-flash` |

#### 3.1.6.1 `FatorExterno` (`diagnosticoIa.fatoresExternos[8]`)

| Campo | Tipo | Descrição | Origem |
| :--- | :--- | :--- | :--- |
| `dimensao` | enum | 2.4 | Backend (ordem fixa) |
| `status` | enum | `AVALIADA`, `SEM_EVIDENCIA`, `NAO_AVALIADA` | Backend (dimensão omitida pela IA vira `NAO_AVALIADA` com `DIMENSAO_OMITIDA_PELA_IA`) |
| `direcao` | enum | Pressão sobre as **vendas do produto**; `INDETERMINADA` em `SEM_EVIDENCIA` e `NAO_AVALIADA` | LLM, validada |
| `confianca` | `MEDIA` \| `BAIXA` | Nunca `ALTA`; `BAIXA` com data só do modelo, fonte única ou radar desatualizado | Backend |
| `relevanciaAoProduto` | enum | `ALTA`, `MEDIA`, `BAIXA`, `NENHUMA` | LLM |
| `relacaoTemporal` | enum \| `null` | 2.4; `null` sem fonte | **Backend** |
| `rotulo` | enum | 2.4; só `POSSIVEL` pode ser promovido a `fatores[]` | **Backend** |
| `origemEvidencia` | enum | `RADAR`, `BUSCA_PRODUTO`, `NENHUMA` | Backend |
| `motivoNaoAvaliado` | enum \| `null` | Só em `NAO_AVALIADA` | Backend |
| `tema` | enum \| `null` | Tema fechado do radar para a dimensão | Radar |
| `notaRadar` | string \| `null` | Frase fixa pt-BR do backend a partir de `tema` (nunca texto livre da web) | Backend |
| `nota` | string \| `null` | ≤ 100 caracteres, **sem dígitos**, só em relevância `ALTA`/`MEDIA`; `null` nos demais | LLM |
| `fontes` | `FonteExterna[]` | ≤ 1 por dimensão (≤ 2 em intensidade `FORTE`); vazia em `SEM_EVIDENCIA`/`NAO_AVALIADA` | Backend |

`FonteExterna` = `{ id, url, dominio, titulo, dataPublicacao, origemData }`, com `id` ∈ `^[FP][0-9]{1,2}$` (`F1..F16` do radar, `P1` da busca do produto); `dataPublicacao` anulável; `origemData` ∈ `MODELO`, `URL`, `SEM_DATA`. O modelo só referencia a fonte por `id`: url, título, domínio e data são preenchidos pelo backend. `fatores[]` (≤ 5) pode conter **no máximo 3 externos**, só de itens `AVALIADA` com `rotulo = POSSIVEL`, relevância `ALTA`/`MEDIA` e coerência direcional; o item não promovido continua em `fatoresExternos`. Fator externo promovido tem `fatores[].dimensao` preenchido (`null` nos internos), nunca `parcelaEstimada` e confiança ≤ `MEDIA`. Fonte `POSTERIOR`, `SEM_DATA` ou `ANTIGA` nunca é causa (vira contexto ou hipótese com `POSTERIOR_AO_PERIODO`, `SEM_DATA` ou `FORA_DO_PERIODO`).

```json
"fatoresExternos": [
  { "dimensao": "POLITICA_REGULATORIO", "status": "SEM_EVIDENCIA", "direcao": "INDETERMINADA",
    "confianca": "BAIXA", "relevanciaAoProduto": "NENHUMA", "relacaoTemporal": null, "rotulo": "SEM_EVIDENCIA",
    "origemEvidencia": "NENHUMA", "motivoNaoAvaliado": null, "tema": null,
    "notaRadar": "Nenhuma evidência encontrada nesta dimensão na pesquisa feita.", "nota": null, "fontes": [] },
  { "dimensao": "CUSTO_MATERIA_PRIMA", "status": "AVALIADA", "direcao": "PRESSAO_BAIXA",
    "confianca": "MEDIA", "relevanciaAoProduto": "ALTA", "relacaoTemporal": "ANTERIOR", "rotulo": "POSSIVEL",
    "origemEvidencia": "RADAR", "motivoNaoAvaliado": null, "tema": "INSUMO_MAIS_CARO",
    "notaRadar": "O insumo ficou mais caro na pesquisa do período.",
    "nota": "Pode ter pressionado o valor de venda do produto.",
    "fontes": [ { "id": "F3", "url": "https://exemplo.gov.br/noticia", "dominio": "exemplo.gov.br", "titulo": "Cotação do insumo sobe", "dataPublicacao": "2026-07-14", "origemData": "MODELO" } ] }
]
```

(Exemplo abreviado: a resposta real traz sempre os 8 itens. Os exemplos 3.1.7 a 3.2.1 abaixo foram escritos na 1.1.x e omitem os campos novos por brevidade; na 1.2.0 todo `diagnosticoIa` os traz.)

#### 3.1.6.2 `RadarRef` e `RadarExterno`

`diagnosticoIa.radar` (`RadarRef`): `{ assunto: { termo, tipo }, mesBase, geradoEm, diasDesdeGeracao, desatualizado, origem }`. `assunto.termo` é o termo de matéria-prima ou categoria (nunca nome comercial, SKU ou cliente); `origem` ∈ `GERADO_AGORA` (este pedido gerou a pesquisa) ou `CACHE` (reaproveitada de outro produto, usuário ou dia, sem nova chamada); `desatualizado = true` quando passou do prazo de validade e foi usada como contexto (aviso `RADAR_DESATUALIZADO`). Os campos de idade se repetem em `meta.ia.radar`.

`data.radarExterno` (`RadarExterno`): `{ assunto, mesBase, geradoEm, diasDesdeGeracao, desatualizado, dimensoes[8] }`, com `dimensoes[i] = { dimensao, status, movimento, intensidade, tema, notaRadar, fontes[] }`. **Sem** `direcao`, `relevanciaAoProduto` e `confianca`: a leitura da pesquisa é independente do produto (o radar é gerado sem dado da empresa e sem a variação). Presente no `GET` e no `POST` com `origem = "template"` quando há radar (fresco ou desatualizado); essas respostas nunca o criam.

`sugestoesBuscaHtml` do radar segue o regime do CP-10: guardado no GCS e **anulado na resposta pública** até a decisão do checkpoint.

`impactoEmOutrosProdutos` **não** se repete dentro de `diagnosticoIa`: a tela usa o bloco de topo (P-181 marca o campo como do backend).

#### 3.1.7 Exemplo `200` — produto com variação e base baixa, IA ainda não gerada (`QUALITATIVO`)

`GET /api/v1/sales-trend/insights/product/5102?metric=quantity&window=1&baseMonth=2026-10`

```json
{
  "data": {
    "produto": { "sku": 5102, "descricao": "CHÁ DE HIBISCO 100G", "fornecedor": "ERVAS DELTA", "categoriaGaleria": "Chás e Infusões", "funcaoPrimaria": "cha_infusao" },
    "periodo": {
      "atual":    { "inicio": "2026-10-01", "fim": "2026-10-31", "diasJanela": 31, "diasCobertos": 31 },
      "anterior": { "inicio": "2026-09-01", "fim": "2026-09-30", "diasJanela": 30, "diasCobertos": 30 },
      "fatorAjuste": 1.0, "baseParcial": false, "contigua": true
    },
    "celula": { "meses": 1, "atual": 3.0, "anterior": 6.0, "variacaoPct": -50.0, "status": "VARIACAO",
                "baseParcial": false, "baseBaixa": true, "devolucaoLiquida": false, "atualPorDia": null, "anteriorPorDia": null },
    "modoDiagnostico": "QUALITATIVO",
    "direcao": "QUEDA",
    "resumoNumerico": null,
    "cascata": [
      { "tipo": "SAZONALIDADE", "status": "SEM_EFEITO", "valor": null, "pontosPercentuais": null, "valorReceita": null, "sentido": null, "explicativa": null, "cortada": false, "confianca": null, "motivoNaoAvaliado": null, "motivoSemEfeito": "HISTORICO_CURTO", "detalhe": null, "itens": [] },
      { "tipo": "PRECO", "status": "SEM_EFEITO", "valor": null, "pontosPercentuais": null, "valorReceita": null, "sentido": null, "explicativa": null, "cortada": false, "confianca": null, "motivoNaoAvaliado": null, "motivoSemEfeito": "VARIACAO_PRECO_PEQUENA", "detalhe": null, "itens": [] },
      { "tipo": "PRODUTO_NOVO", "status": "SEM_EFEITO", "valor": null, "pontosPercentuais": null, "valorReceita": null, "sentido": null, "explicativa": null, "cortada": false, "confianca": null, "motivoNaoAvaliado": null, "motivoSemEfeito": "SEM_PARES", "detalhe": null, "itens": [] },
      { "tipo": "CANIBALIZACAO_MESMO_FORNECEDOR", "status": "SEM_EFEITO", "valor": null, "pontosPercentuais": null, "valorReceita": null, "sentido": null, "explicativa": null, "cortada": false, "confianca": null, "motivoNaoAvaliado": null, "motivoSemEfeito": "SEM_PARES", "detalhe": null, "itens": [] },
      { "tipo": "CANIBALIZACAO_OUTRO_FORNECEDOR", "status": "AVALIADO", "valor": null, "pontosPercentuais": null, "valorReceita": null, "sentido": "NEGATIVO", "explicativa": null, "cortada": false, "confianca": "BAIXA", "motivoNaoAvaliado": null, "motivoSemEfeito": null, "detalhe": null,
        "itens": [
          { "sku": 5140, "descricao": "CHÁ DE HIBISCO COM CANELA 80G", "fornecedor": "NATURAL ÔMEGA", "sameSupplier": false, "affinityScore": 0.712, "lancamento": false,
            "receitaMigrada": null, "clientesMigrados": "<3", "confianca": "BAIXA", "mecanismo": "MIGRACAO_POR_VALOR", "netMarginImpact": null }
        ] },
      { "tipo": "CLIENTES_PERDIDOS", "status": "SEM_EFEITO", "valor": null, "pontosPercentuais": null, "valorReceita": null, "sentido": null, "explicativa": null, "cortada": false, "confianca": null, "motivoNaoAvaliado": null, "motivoSemEfeito": "SEM_CLIENTES_PERDIDOS", "detalhe": null, "itens": [] }
    ],
    "indicadores": [
      { "tipo": "RUPTURA", "status": "SEM_EFEITO", "sentido": null, "confianca": null, "valor": null, "motivoSemEfeito": "SEM_RUPTURA", "motivoNaoAvaliado": null,
        "evidencia": { "estoqueAtual": 42, "statusEstoque": "OK", "observacao": null } },
      { "tipo": "PROMOCAO", "status": "SEM_EFEITO", "sentido": null, "confianca": null, "valor": null, "motivoSemEfeito": "SEM_PROMOCAO", "motivoNaoAvaliado": null,
        "evidencia": { "produtoEmPromocaoAnterior": false, "produtoEmPromocaoAtual": false, "afinsEmPromocaoSoNaAtual": [] } },
      { "tipo": "REGIONAL", "status": "SEM_EFEITO", "sentido": null, "confianca": null, "valor": null, "motivoSemEfeito": "SEM_CONCENTRACAO", "motivoNaoAvaliado": null, "evidencia": null },
      { "tipo": "PERDA_PARTICIPACAO_SEM_MIGRACAO", "status": "NAO_AVALIADO", "sentido": null, "confianca": null, "valor": null, "motivoSemEfeito": null, "motivoNaoAvaliado": "MODO_QUALITATIVO", "evidencia": null }
    ],
    "diagnosticoMercado": {
      "classificacao": "PERDA_DE_PARTICIPACAO",
      "variacaoMercadoPct": 10.0, "efeitoMercado": 0.6, "efeitoParticipacao": -3.6,
      "participacaoAnteriorPct": 13.0, "participacaoAtualPct": 6.4, "variacaoParticipacaoPp": -6.7,
      "variacaoAfinsMesmoFornecedorPct": null, "variacaoAfinsOutroFornecedorPct": 10.0
    },
    "grupoAfim": {
      "status": "AVALIADO",
      "afins": [
        { "sku": 5140, "descricao": "CHÁ DE HIBISCO COM CANELA 80G", "fornecedor": "NATURAL ÔMEGA", "sameSupplier": false, "affinityScore": 0.712,
          "categoriaGaleria": "Chás e Infusões", "valorVendaAtual": 18.9, "celula": { "meses": 1, "atual": 26.0, "anterior": 22.0, "variacaoPct": 18.2, "status": "VARIACAO", "baseParcial": false, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": null, "anteriorPorDia": null },
          "ganhouClientesDoProduto": true, "lancamento": false },
        { "sku": 5188, "descricao": "CHÁ MISTO EMAGRECEDOR 60G", "fornecedor": "NATURAL ÔMEGA", "sameSupplier": false, "affinityScore": 0.534,
          "categoriaGaleria": "Chás e Infusões", "valorVendaAtual": 15.5, "celula": { "meses": 1, "atual": 18.0, "anterior": 18.0, "variacaoPct": 0.0, "status": "VARIACAO", "baseParcial": false, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": null, "anteriorPorDia": null },
          "ganhouClientesDoProduto": false, "lancamento": false }
      ]
    },
    "impactoEmOutrosProdutos": null,
    "diagnosticoIa": null
  },
  "meta": {
    "timestamp": "2026-11-24T14:02:11.204Z", "version": "1.2.0",
    "dataReferencia": "2026-11-24", "ultimoDiaCoberto": "2026-11-23", "mesBase": "2026-10",
    "metrica": "quantity", "janela": 1, "modoComparacao": "point", "promptVersion": "tia-v3",
    "indiceAfinidade": { "disponivel": true, "lastSyncAt": "2026-11-24T03:00:41.512Z" },
    "avisos": [],
    "ia": { "podeGerar": true, "motivoBloqueio": null, "diagnosticoSalvo": false, "diagnosticoSalvoEm": null, "geracaoEmAndamento": false, "diagnosticoVencido": false, "geraComIa": true, "motivoTemplate": null, "podeForcar": true, "orcamento": { "nivel": "NORMAL" } }
  }
}
```

#### 3.1.8 Exemplo `200` — alta com `impactoEmOutrosProdutos` e corte da cascata

`GET /api/v1/sales-trend/insights/product/3301?metric=revenue&window=3&baseMonth=2026-10&comparisonMode=point` (`CUR = out/26`, `PRE = jul/26`, `k = 1`). Δ = +1.800,00; sazonalidade compensatória −720,00; orçamento das explicativas = 1.800 + 720 = 2.520; preço (119,04) + mesmo fornecedor (480,00) + outro fornecedor (3.400,00) passariam do orçamento, então a parcela de outro fornecedor é cortada para 1.920,96 (P-169.2) e o resíduo é zero.

```json
{
  "data": {
    "produto": { "sku": 3301, "descricao": "CREATINA PURA 300G", "fornecedor": "VITA GAMA", "categoriaGaleria": "Suplementos", "funcaoPrimaria": "creatina" },
    "periodo": {
      "atual":    { "inicio": "2026-10-01", "fim": "2026-10-31", "diasJanela": 31, "diasCobertos": 31 },
      "anterior": { "inicio": "2026-07-01", "fim": "2026-07-31", "diasJanela": 31, "diasCobertos": 31 },
      "fatorAjuste": 1.0, "baseParcial": false, "contigua": false
    },
    "celula": { "meses": 3, "atual": 13800.0, "anterior": 12000.0, "variacaoPct": 15.0, "status": "VARIACAO",
                "baseParcial": false, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": null, "anteriorPorDia": null },
    "modoDiagnostico": "QUANTITATIVO",
    "direcao": "ALTA",
    "resumoNumerico": { "baseAjustada": 12000.0, "deltaObservado": 1800.0, "somaParcelas": 1800.0, "residuo": 0.0, "coberturaExplicacaoPct": 100.0 },
    "cascata": [
      { "tipo": "SAZONALIDADE", "status": "AVALIADO", "valor": -720.0, "pontosPercentuais": -6.0, "valorReceita": null, "sentido": "NEGATIVO", "explicativa": false, "cortada": false, "confianca": "MEDIA",
        "motivoNaoAvaliado": null, "motivoSemEfeito": null, "detalhe": { "indiceAtual": 0.94, "indiceAnterior": 1.0, "forca": "MODERADA" }, "itens": [] },
      { "tipo": "PRECO", "status": "AVALIADO", "valor": 119.04, "pontosPercentuais": 1.0, "valorReceita": null, "sentido": "POSITIVO", "explicativa": true, "cortada": false, "confianca": "MEDIA",
        "motivoNaoAvaliado": null, "motivoSemEfeito": null,
        "detalhe": { "valorMedioAnterior": 150.0, "valorMedioAtual": 144.0, "variacaoValorPct": -4.0, "elasticidade": -1.3, "observacoes": [] }, "itens": [] },
      { "tipo": "PRODUTO_NOVO", "status": "SEM_EFEITO", "valor": null, "pontosPercentuais": null, "valorReceita": null, "sentido": null, "explicativa": null, "cortada": false, "confianca": null,
        "motivoNaoAvaliado": null, "motivoSemEfeito": "NAO_SE_APLICA_A_ALTA", "detalhe": null, "itens": [] },
      { "tipo": "CANIBALIZACAO_MESMO_FORNECEDOR", "status": "AVALIADO", "valor": 480.0, "pontosPercentuais": 4.0, "valorReceita": null, "sentido": "POSITIVO", "explicativa": true, "cortada": false, "confianca": "MEDIA",
        "motivoNaoAvaliado": null, "motivoSemEfeito": null, "detalhe": null,
        "itens": [
          { "sku": 3305, "descricao": "CREATINA PURA 150G", "fornecedor": "VITA GAMA", "sameSupplier": true, "affinityScore": 0.861, "lancamento": false,
            "receitaMigrada": 480.0, "clientesMigrados": 5, "confianca": "MEDIA", "mecanismo": "MIGRACAO_POR_VALOR", "netMarginImpact": -35.0 }
        ] },
      { "tipo": "CANIBALIZACAO_OUTRO_FORNECEDOR", "status": "AVALIADO", "valor": 1920.96, "pontosPercentuais": 16.0, "valorReceita": null, "sentido": "POSITIVO", "explicativa": true, "cortada": true, "confianca": "ALTA",
        "motivoNaoAvaliado": null, "motivoSemEfeito": null, "detalhe": null,
        "itens": [
          { "sku": 2045, "descricao": "CREATINA MONOHIDRATADA 300G", "fornecedor": "LABORATÓRIO ALFA", "sameSupplier": false, "affinityScore": 0.804, "lancamento": false,
            "receitaMigrada": 3400.0, "clientesMigrados": 12, "confianca": "ALTA", "mecanismo": "PRECO_MENOR_DESTROI_MARGEM", "netMarginImpact": -680.0 }
        ] },
      { "tipo": "CLIENTES_PERDIDOS", "status": "SEM_EFEITO", "valor": null, "pontosPercentuais": null, "valorReceita": null, "sentido": null, "explicativa": null, "cortada": false, "confianca": null,
        "motivoNaoAvaliado": null, "motivoSemEfeito": "NAO_SE_APLICA_A_ALTA", "detalhe": null, "itens": [] }
    ],
    "indicadores": [
      { "tipo": "RUPTURA", "status": "SEM_EFEITO", "sentido": null, "confianca": null, "valor": null, "motivoSemEfeito": "SEM_RUPTURA", "motivoNaoAvaliado": null,
        "evidencia": { "estoqueAtual": 310, "statusEstoque": "OK", "observacao": null } },
      { "tipo": "PROMOCAO", "status": "AVALIADO", "sentido": "POSITIVO", "confianca": "BAIXA", "valor": null, "motivoSemEfeito": null, "motivoNaoAvaliado": null,
        "evidencia": { "produtoEmPromocaoAnterior": false, "produtoEmPromocaoAtual": true, "afinsEmPromocaoSoNaAtual": [] } },
      { "tipo": "REGIONAL", "status": "SEM_EFEITO", "sentido": null, "confianca": null, "valor": null, "motivoSemEfeito": "SEM_CONCENTRACAO", "motivoNaoAvaliado": null, "evidencia": null },
      { "tipo": "PERDA_PARTICIPACAO_SEM_MIGRACAO", "status": "SEM_EFEITO", "sentido": null, "confianca": null, "valor": null, "motivoSemEfeito": "SEM_CONCENTRACAO", "motivoNaoAvaliado": null, "evidencia": null }
    ],
    "diagnosticoMercado": {
      "classificacao": "MISTO",
      "variacaoMercadoPct": -23.8, "efeitoMercado": -2857.14, "efeitoParticipacao": 4657.14,
      "participacaoAnteriorPct": 22.2, "participacaoAtualPct": 30.1, "variacaoParticipacaoPp": 7.9,
      "variacaoAfinsMesmoFornecedorPct": 20.0, "variacaoAfinsOutroFornecedorPct": -26.0
    },
    "grupoAfim": {
      "status": "AVALIADO",
      "afins": [
        { "sku": 3305, "descricao": "CREATINA PURA 150G", "fornecedor": "VITA GAMA", "sameSupplier": true, "affinityScore": 0.861, "categoriaGaleria": "Suplementos", "valorVendaAtual": 79.9,
          "celula": { "meses": 3, "atual": 2400.0, "anterior": 2000.0, "variacaoPct": 20.0, "status": "VARIACAO", "baseParcial": false, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": null, "anteriorPorDia": null }, "ganhouClientesDoProduto": false, "lancamento": false },
        { "sku": 2045, "descricao": "CREATINA MONOHIDRATADA 300G", "fornecedor": "LABORATÓRIO ALFA", "sameSupplier": false, "affinityScore": 0.804, "categoriaGaleria": "Suplementos", "valorVendaAtual": 159.9,
          "celula": { "meses": 3, "atual": 26000.0, "anterior": 40000.0, "variacaoPct": -35.0, "status": "VARIACAO", "baseParcial": false, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": null, "anteriorPorDia": null }, "ganhouClientesDoProduto": false, "lancamento": false },
        { "sku": 3120, "descricao": "CREATINA CREAPURE 250G", "fornecedor": "NUTRI BETA", "sameSupplier": false, "affinityScore": 0.655, "categoriaGaleria": "Suplementos", "valorVendaAtual": 189.0,
          "celula": { "meses": 3, "atual": 3600.0, "anterior": 0.0, "variacaoPct": null, "status": "NOVO", "baseParcial": false, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": null, "anteriorPorDia": null }, "ganhouClientesDoProduto": false, "lancamento": true }
      ]
    },
    "impactoEmOutrosProdutos": {
      "totalInterno": 480.0,
      "totalConcorrentes": 3400.0,
      "itens": [
        { "sku": 2045, "descricao": "CREATINA MONOHIDRATADA 300G", "fornecedor": "LABORATÓRIO ALFA", "sameSupplier": false, "affinityScore": 0.804,
          "tipoImpacto": "GANHO_SOBRE_CONCORRENTE", "receitaMigrada": 3400.0, "clientesMigrados": 12, "confianca": "ALTA",
          "mecanismo": "PRECO_MENOR_DESTROI_MARGEM", "netMarginImpact": -680.0, "estoqueZerado": false },
        { "sku": 3305, "descricao": "CREATINA PURA 150G", "fornecedor": "VITA GAMA", "sameSupplier": true, "affinityScore": 0.861,
          "tipoImpacto": "CANIBALIZACAO_INTERNA", "receitaMigrada": 480.0, "clientesMigrados": 5, "confianca": "MEDIA",
          "mecanismo": "MIGRACAO_POR_VALOR", "netMarginImpact": -35.0, "estoqueZerado": false }
      ]
    },
    "diagnosticoIa": null
  },
  "meta": {
    "timestamp": "2026-11-24T14:05:42.870Z", "version": "1.2.0",
    "dataReferencia": "2026-11-24", "ultimoDiaCoberto": "2026-11-23", "mesBase": "2026-10",
    "metrica": "revenue", "janela": 3, "modoComparacao": "point", "promptVersion": "tia-v3",
    "indiceAfinidade": { "disponivel": true, "lastSyncAt": "2026-11-24T03:00:41.512Z" },
    "avisos": [],
    "ia": { "podeGerar": true, "motivoBloqueio": null, "diagnosticoSalvo": false, "diagnosticoSalvoEm": null, "geracaoEmAndamento": false, "diagnosticoVencido": false, "geraComIa": false, "motivoTemplate": "GATE_RESIDUO_BAIXO", "podeForcar": true, "orcamento": { "nivel": "NORMAL" } }
  }
}
```

#### 3.1.9 Exemplo `200` — índice de afinidade indisponível (cold start sem objeto no GCS)

Mesma forma; as parcelas e blocos que dependem de afinidade ficam `NAO_AVALIADO`:

```json
{
  "data": {
    "produto": { "sku": 2045, "descricao": "CREATINA MONOHIDRATADA 300G", "fornecedor": "LABORATÓRIO ALFA", "categoriaGaleria": null, "funcaoPrimaria": null },
    "periodo": {
      "atual":    { "inicio": "2026-10-01", "fim": "2026-10-31", "diasJanela": 31, "diasCobertos": 31 },
      "anterior": { "inicio": "2026-07-01", "fim": "2026-07-31", "diasJanela": 31, "diasCobertos": 31 },
      "fatorAjuste": 1.0, "baseParcial": false, "contigua": false
    },
    "celula": { "meses": 3, "atual": 26000.0, "anterior": 40000.0, "variacaoPct": -35.0, "status": "VARIACAO",
                "baseParcial": false, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": null, "anteriorPorDia": null },
    "modoDiagnostico": "QUANTITATIVO",
    "direcao": "QUEDA",
    "resumoNumerico": { "baseAjustada": 40000.0, "deltaObservado": -14000.0, "somaParcelas": -3561.6, "residuo": -10438.4, "coberturaExplicacaoPct": 25.4 },
    "cascata": [
      { "tipo": "SAZONALIDADE", "status": "AVALIADO", "valor": -2400.0, "pontosPercentuais": -6.0, "valorReceita": null, "sentido": "NEGATIVO", "explicativa": true, "cortada": false, "confianca": "MEDIA",
        "motivoNaoAvaliado": null, "motivoSemEfeito": null, "detalhe": { "indiceAtual": 0.94, "indiceAnterior": 1.0, "forca": "MODERADA" }, "itens": [] },
      { "tipo": "PRECO", "status": "AVALIADO", "valor": -1161.6, "pontosPercentuais": -2.9, "valorReceita": null, "sentido": "NEGATIVO", "explicativa": true, "cortada": false, "confianca": "MEDIA",
        "motivoNaoAvaliado": null, "motivoSemEfeito": null,
        "detalhe": { "valorMedioAnterior": 150.0, "valorMedioAtual": 159.0, "variacaoValorPct": 6.0, "elasticidade": -1.4, "observacoes": [] }, "itens": [] },
      { "tipo": "PRODUTO_NOVO", "status": "NAO_AVALIADO", "valor": null, "pontosPercentuais": null, "valorReceita": null, "sentido": null, "explicativa": null, "cortada": false, "confianca": null,
        "motivoNaoAvaliado": "INDICE_AFINIDADE_INDISPONIVEL", "motivoSemEfeito": null, "detalhe": null, "itens": [] },
      { "tipo": "CANIBALIZACAO_MESMO_FORNECEDOR", "status": "NAO_AVALIADO", "valor": null, "pontosPercentuais": null, "valorReceita": null, "sentido": null, "explicativa": null, "cortada": false, "confianca": null,
        "motivoNaoAvaliado": "INDICE_AFINIDADE_INDISPONIVEL", "motivoSemEfeito": null, "detalhe": null, "itens": [] },
      { "tipo": "CANIBALIZACAO_OUTRO_FORNECEDOR", "status": "NAO_AVALIADO", "valor": null, "pontosPercentuais": null, "valorReceita": null, "sentido": null, "explicativa": null, "cortada": false, "confianca": null,
        "motivoNaoAvaliado": "INDICE_AFINIDADE_INDISPONIVEL", "motivoSemEfeito": null, "detalhe": null, "itens": [] },
      { "tipo": "CLIENTES_PERDIDOS", "status": "NAO_AVALIADO", "valor": null, "pontosPercentuais": null, "valorReceita": null, "sentido": null, "explicativa": null, "cortada": false, "confianca": null,
        "motivoNaoAvaliado": "INDICE_AFINIDADE_INDISPONIVEL", "motivoSemEfeito": null, "detalhe": null, "itens": [] }
    ],
    "indicadores": [
      { "tipo": "RUPTURA", "status": "SEM_EFEITO", "sentido": null, "confianca": null, "valor": null, "motivoSemEfeito": "SEM_RUPTURA", "motivoNaoAvaliado": null,
        "evidencia": { "estoqueAtual": 85, "statusEstoque": "OK", "observacao": null } },
      { "tipo": "PROMOCAO", "status": "SEM_EFEITO", "sentido": null, "confianca": null, "valor": null, "motivoSemEfeito": "SEM_PROMOCAO", "motivoNaoAvaliado": null,
        "evidencia": { "produtoEmPromocaoAnterior": false, "produtoEmPromocaoAtual": false, "afinsEmPromocaoSoNaAtual": [] } },
      { "tipo": "REGIONAL", "status": "AVALIADO", "sentido": "NEGATIVO", "confianca": "MEDIA", "valor": null, "motivoSemEfeito": null, "motivoNaoAvaliado": null,
        "evidencia": { "ufConcentradora": "PE", "participacaoPct": 64.0,
                       "porUf": [ { "uf": "PE", "delta": -8960.0, "participacaoPct": 64.0 }, { "uf": "CE", "delta": -3100.0, "participacaoPct": 22.1 }, { "uf": "OUTRAS", "delta": -1940.0, "participacaoPct": 13.9 } ] } },
      { "tipo": "PERDA_PARTICIPACAO_SEM_MIGRACAO", "status": "NAO_AVALIADO", "sentido": null, "confianca": null, "valor": null, "motivoSemEfeito": null, "motivoNaoAvaliado": "INDICE_AFINIDADE_INDISPONIVEL", "evidencia": null }
    ],
    "diagnosticoMercado": { "classificacao": "NAO_AVALIADO", "variacaoMercadoPct": null, "efeitoMercado": null, "efeitoParticipacao": null,
                            "participacaoAnteriorPct": null, "participacaoAtualPct": null, "variacaoParticipacaoPp": null,
                            "variacaoAfinsMesmoFornecedorPct": null, "variacaoAfinsOutroFornecedorPct": null },
    "grupoAfim": { "status": "NAO_AVALIADO", "afins": [] },
    "impactoEmOutrosProdutos": null,
    "diagnosticoIa": null
  },
  "meta": {
    "timestamp": "2026-11-24T08:01:03.117Z", "version": "1.2.0",
    "dataReferencia": "2026-11-24", "ultimoDiaCoberto": "2026-11-23", "mesBase": "2026-10",
    "metrica": "revenue", "janela": 3, "modoComparacao": "point", "promptVersion": "tia-v3",
    "indiceAfinidade": { "disponivel": false, "lastSyncAt": null },
    "avisos": [ { "codigo": "TIA-005", "mensagem": "Índice de produtos afins em atualização: canibalização e grupo afim não avaliados." } ],
    "ia": { "podeGerar": true, "motivoBloqueio": null, "diagnosticoSalvo": false, "diagnosticoSalvoEm": null, "geracaoEmAndamento": false, "diagnosticoVencido": false, "geraComIa": true, "motivoTemplate": null, "podeForcar": true, "orcamento": { "nivel": "NORMAL" } }
  }
}
```

---

### 3.2 `POST /api/v1/sales-trend/insights/product/{sku}/generate`

- **Objetivo:** gerar o diagnóstico com IA para a chave `(sku, metric, window, baseMonth, comparisonMode, promptVersion, evidenceHash)`, devolver o já salvo, ou devolver o resumo por template quando a IA não deve ou não pode ser chamada (P-174..P-184, P-188). `evidenceHash` é interno e nunca exposto: carga nova do ERP com evidência igual reaproveita o salvo.
- **Quem chama:** só os botões "Gerar análise com IA", "Gerar resumo automático" (quando `meta.ia.geraComIa = false`), "Atualizar" (diagnóstico vencido) e "Gerar de novo". Não existe mais "Análise aprofundada". Nada chama sozinho. A tela desabilita os botões enquanto o pedido está em voo (P-176.1) e usa timeout HTTP de **150 s** (a camada de IA tem prazo total de 125 s, `LLM_TOTAL_DEADLINE_SECONDS`, e a trava de voo de 150 s; ADR-009 DA-08 e DA-13).
- **Headers:** `Content-Type: application/json`.

**Corpo (`GenerateRequest`):**

| Campo | Tipo | Default | Validação | Descrição | Regra |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `metric`, `window`, `baseMonth`, `comparisonMode` | | como em 3.1 | como em 3.1 | Identificam a célula | P-150 |
| `force` | boolean | `false` | — | `true` = "Gerar de novo"/"Atualizar": ignora o salvo e **custa dinheiro**; a tela só envia `true` depois da confirmação "Gerar de novo consome créditos de IA. Continuar?". Limitado a 3 por usuário por dia e desabilitado com orçamento em `ALERTA`/`ESGOTADO` (`meta.ia.podeForcar`) | P-175.2, P-176 |

```json
{ "metric": "revenue", "window": 3, "baseMonth": "2026-10", "comparisonMode": "point", "force": false }
```

Campo `deep` enviado por cliente antigo é ignorado (parâmetros desconhecidos), nunca escalona modelo.

**Comportamento:**

| Situação | Resposta |
| :--- | :--- |
| Diagnóstico salvo para a chave e `force = false` | `200`, `meta.origem = "cache"`, `reutilizado = true`, sem LLM, sem contar no rate limit, custo zero |
| Outro pedido em voo para a mesma chave (qualquer instância) | Aguarda e devolve o mesmo resultado (`origem = "cache"`) |
| Geração bem-sucedida no Hydrogen | `200`, `origem = "llm"`, `diagnosticoIa` preenchido, salvo no GCS |
| Falha de infraestrutura do Hydrogen e sucesso do `gemini-3.8-flash` | `200`, `origem = "fallback"`, `modelo = "gemini-3.8-flash"`, `diagnosticoIa` preenchido e salvo |
| Gate de não chamada (variação ínfima, base insuficiente, delta < R$ 1.000, resíduo < 0,20 sem região/mercado) | `200`, `origem = "template"`, `motivoTemplate = GATE_*`, `diagnosticoIa = null`; nada é salvo |
| Kill-switch ligado, Vertex indisponível desde o início | `200`, `origem = "template"`, `motivoTemplate = IA_DESLIGADA` ou `IA_INDISPONIVEL` |
| Orçamento do mês ou do dia sem saldo, ou livro de gastos indisponível | `200`, `origem = "template"`, `motivoTemplate = ORCAMENTO_ESGOTADO` |
| Hydrogen e Flash falham (schema ou prazo total de 125 s) | `200`, `origem = "template"`, aviso `IA_FALHOU`; nada é salvo (P-175.5); o custo já consumido é acertado no livro |
| Radar do assunto fresco no GCS | Usado como contexto do diagnóstico; `diagnosticoIa.radar.origem = "CACHE"`; sem nova pesquisa. `force` **não** renova o radar |
| Radar ausente ou vencido e a geração é permitida | O backend gera o radar (única chamada com busca, sem dado da empresa) e depois o diagnóstico: `radar.origem = "GERADO_AGORA"`. Pedidos simultâneos do mesmo assunto compartilham a geração |
| Radar vencido e a geração não é permitida (limite de uso, orçamento em `ALERTA`, limite diário de radares) | Usa o radar desatualizado: `meta.ia.radar.estado = "DESATUALIZADO"`, aviso `RADAR_DESATUALIZADO`, confiança externa `BAIXA` |
| Sem radar utilizável (falha da pesquisa, limite, assunto sem termo) | O diagnóstico segue com os fatores internos; as 8 dimensões saem `NAO_AVALIADA` (`SEM_RADAR` ou `SEM_TERMO_BUSCA`) e o aviso é `SEM_RADAR_EXTERNO`; a falha do radar **não** gera `IA_FALHOU` |
| Orçamento esgotado, IA desligada ou gate, com radar existente | `origem = "template"` com `data.radarExterno` somente leitura (sem nova pesquisa) |
| `SEM_VARIACAO` | `422 TIA-003` ("Não há variação relevante para analisar.") |
| Mais de 2 pedidos que chamam o LLM no minuto | `429 TIA-004` `motivo = LIMITE_DE_PEDIDOS`, header `Retry-After` (segundos) |
| Mais de 10 pedidos que chamam o LLM no dia, ou 3 com `force`, por usuário | `429 TIA-004` `motivo = LIMITE_DIARIO`, header `Retry-After` |

**Resposta `200` — `data`:** o mesmo `ProductInsight` de 3.1 (com `diagnosticoIa` preenchido em `llm`/`fallback`/`cache`, `null` em `template`); `meta` é `GenerateMeta` (2.1); `meta.ia.diagnosticoSalvo = true` após geração bem-sucedida. O resumo por template é devolvido em `data.resumoAutomatico` (string ≤ 400, sem números, só quando `origem = "template"`; `null` nos demais casos), para a tela exibi-lo rotulado "Resumo automático (sem IA)".

#### 3.2.1 Exemplo `200` — queda com canibalização de mesmo e de outro fornecedor e lançamento afim

`POST /api/v1/sales-trend/insights/product/2045/generate` com o corpo acima. SKU caiu 35,0% (R$ 40.000,00 → R$ 26.000,00) em `point`, X = 3 (`CUR = out/26`, `PRE = jul/26`, `k = 1`). Afins cresceram 21% (mercado em alta) enquanto a participação do SKU caiu 15,4 pp: `PERDA_DE_PARTICIPACAO`.

```json
{
  "data": {
    "produto": { "sku": 2045, "descricao": "CREATINA MONOHIDRATADA 300G", "fornecedor": "LABORATÓRIO ALFA", "categoriaGaleria": "Suplementos", "funcaoPrimaria": "creatina" },
    "periodo": {
      "atual":    { "inicio": "2026-10-01", "fim": "2026-10-31", "diasJanela": 31, "diasCobertos": 31 },
      "anterior": { "inicio": "2026-07-01", "fim": "2026-07-31", "diasJanela": 31, "diasCobertos": 31 },
      "fatorAjuste": 1.0, "baseParcial": false, "contigua": false
    },
    "celula": { "meses": 3, "atual": 26000.0, "anterior": 40000.0, "variacaoPct": -35.0, "status": "VARIACAO",
                "baseParcial": false, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": null, "anteriorPorDia": null },
    "modoDiagnostico": "QUANTITATIVO",
    "direcao": "QUEDA",
    "resumoNumerico": { "baseAjustada": 40000.0, "deltaObservado": -14000.0, "somaParcelas": -12411.6, "residuo": -1588.4, "coberturaExplicacaoPct": 88.7 },
    "cascata": [
      { "tipo": "SAZONALIDADE", "status": "AVALIADO", "valor": -2400.0, "pontosPercentuais": -6.0, "valorReceita": null, "sentido": "NEGATIVO", "explicativa": true, "cortada": false, "confianca": "MEDIA",
        "motivoNaoAvaliado": null, "motivoSemEfeito": null, "detalhe": { "indiceAtual": 0.94, "indiceAnterior": 1.0, "forca": "MODERADA" }, "itens": [] },
      { "tipo": "PRECO", "status": "AVALIADO", "valor": -1161.6, "pontosPercentuais": -2.9, "valorReceita": null, "sentido": "NEGATIVO", "explicativa": true, "cortada": false, "confianca": "MEDIA",
        "motivoNaoAvaliado": null, "motivoSemEfeito": null,
        "detalhe": { "valorMedioAnterior": 150.0, "valorMedioAtual": 159.0, "variacaoValorPct": 6.0, "elasticidade": -1.4, "observacoes": [] }, "itens": [] },
      { "tipo": "PRODUTO_NOVO", "status": "AVALIADO", "valor": -3100.0, "pontosPercentuais": -7.8, "valorReceita": null, "sentido": "NEGATIVO", "explicativa": true, "cortada": false, "confianca": "MEDIA",
        "motivoNaoAvaliado": null, "motivoSemEfeito": null, "detalhe": null,
        "itens": [
          { "sku": 3120, "descricao": "CREATINA CREAPURE 250G", "fornecedor": "NUTRI BETA", "sameSupplier": false, "affinityScore": 0.655, "lancamento": true,
            "receitaMigrada": 3100.0, "clientesMigrados": 7, "confianca": "MEDIA", "mecanismo": "PRECO_MENOR_MARGEM_PRESERVADA", "netMarginImpact": 210.0 }
        ] },
      { "tipo": "CANIBALIZACAO_MESMO_FORNECEDOR", "status": "AVALIADO", "valor": -1450.0, "pontosPercentuais": -3.6, "valorReceita": null, "sentido": "NEGATIVO", "explicativa": true, "cortada": false, "confianca": "MEDIA",
        "motivoNaoAvaliado": null, "motivoSemEfeito": null, "detalhe": null,
        "itens": [
          { "sku": 2046, "descricao": "CREATINA MONOHIDRATADA 150G", "fornecedor": "LABORATÓRIO ALFA", "sameSupplier": true, "affinityScore": 0.902, "lancamento": false,
            "receitaMigrada": 1450.0, "clientesMigrados": 4, "confianca": "MEDIA", "mecanismo": "MIGRACAO_POR_VALOR", "netMarginImpact": -120.0 }
        ] },
      { "tipo": "CANIBALIZACAO_OUTRO_FORNECEDOR", "status": "AVALIADO", "valor": -3400.0, "pontosPercentuais": -8.5, "valorReceita": null, "sentido": "NEGATIVO", "explicativa": true, "cortada": false, "confianca": "ALTA",
        "motivoNaoAvaliado": null, "motivoSemEfeito": null, "detalhe": null,
        "itens": [
          { "sku": 3301, "descricao": "CREATINA PURA 300G", "fornecedor": "VITA GAMA", "sameSupplier": false, "affinityScore": 0.804, "lancamento": false,
            "receitaMigrada": 3400.0, "clientesMigrados": 12, "confianca": "ALTA", "mecanismo": "PRECO_MENOR_DESTROI_MARGEM", "netMarginImpact": -680.0 }
        ] },
      { "tipo": "CLIENTES_PERDIDOS", "status": "AVALIADO", "valor": -900.0, "pontosPercentuais": -2.2, "valorReceita": null, "sentido": "NEGATIVO", "explicativa": true, "cortada": false, "confianca": "MEDIA",
        "motivoNaoAvaliado": null, "motivoSemEfeito": null, "detalhe": { "clientesPerdidosQtd": 4 }, "itens": [] }
    ],
    "indicadores": [
      { "tipo": "RUPTURA", "status": "SEM_EFEITO", "sentido": null, "confianca": null, "valor": null, "motivoSemEfeito": "SEM_RUPTURA", "motivoNaoAvaliado": null,
        "evidencia": { "estoqueAtual": 85, "statusEstoque": "OK", "observacao": null } },
      { "tipo": "PROMOCAO", "status": "AVALIADO", "sentido": "NEGATIVO", "confianca": "BAIXA", "valor": null, "motivoSemEfeito": null, "motivoNaoAvaliado": null,
        "evidencia": { "produtoEmPromocaoAnterior": false, "produtoEmPromocaoAtual": false, "afinsEmPromocaoSoNaAtual": [3301] } },
      { "tipo": "REGIONAL", "status": "AVALIADO", "sentido": "NEGATIVO", "confianca": "MEDIA", "valor": null, "motivoSemEfeito": null, "motivoNaoAvaliado": null,
        "evidencia": { "ufConcentradora": "PE", "participacaoPct": 64.0,
                       "porUf": [ { "uf": "PE", "delta": -8960.0, "participacaoPct": 64.0 }, { "uf": "CE", "delta": -3100.0, "participacaoPct": 22.1 }, { "uf": "OUTRAS", "delta": -1940.0, "participacaoPct": 13.9 } ] } },
      { "tipo": "PERDA_PARTICIPACAO_SEM_MIGRACAO", "status": "AVALIADO", "sentido": "NEGATIVO", "confianca": "BAIXA", "valor": -1588.4, "motivoSemEfeito": null, "motivoNaoAvaliado": null,
        "evidencia": { "afinsQueCresceramSemClientesDoProduto": [3415] } }
    ],
    "diagnosticoMercado": {
      "classificacao": "PERDA_DE_PARTICIPACAO",
      "variacaoMercadoPct": 21.0, "efeitoMercado": 8400.0, "efeitoParticipacao": -22400.0,
      "participacaoAnteriorPct": 57.1, "participacaoAtualPct": 41.7, "variacaoParticipacaoPp": -15.4,
      "variacaoAfinsMesmoFornecedorPct": 5.0, "variacaoAfinsOutroFornecedorPct": 31.7
    },
    "grupoAfim": {
      "status": "AVALIADO",
      "afins": [
        { "sku": 2046, "descricao": "CREATINA MONOHIDRATADA 150G", "fornecedor": "LABORATÓRIO ALFA", "sameSupplier": true, "affinityScore": 0.902, "categoriaGaleria": "Suplementos", "valorVendaAtual": 89.9,
          "celula": { "meses": 3, "atual": 10200.0, "anterior": 9000.0, "variacaoPct": 13.3, "status": "VARIACAO", "baseParcial": false, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": null, "anteriorPorDia": null }, "ganhouClientesDoProduto": true, "lancamento": false },
        { "sku": 3301, "descricao": "CREATINA PURA 300G", "fornecedor": "VITA GAMA", "sameSupplier": false, "affinityScore": 0.804, "categoriaGaleria": "Suplementos", "valorVendaAtual": 144.0,
          "celula": { "meses": 3, "atual": 13800.0, "anterior": 12000.0, "variacaoPct": 15.0, "status": "VARIACAO", "baseParcial": false, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": null, "anteriorPorDia": null }, "ganhouClientesDoProduto": true, "lancamento": false },
        { "sku": 3120, "descricao": "CREATINA CREAPURE 250G", "fornecedor": "NUTRI BETA", "sameSupplier": false, "affinityScore": 0.655, "categoriaGaleria": "Suplementos", "valorVendaAtual": 189.0,
          "celula": { "meses": 3, "atual": 3600.0, "anterior": 0.0, "variacaoPct": null, "status": "NOVO", "baseParcial": false, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": null, "anteriorPorDia": null }, "ganhouClientesDoProduto": true, "lancamento": true },
        { "sku": 3415, "descricao": "CREATINA 100% 500G", "fornecedor": "NUTRI BETA", "sameSupplier": false, "affinityScore": 0.588, "categoriaGaleria": "Suplementos", "valorVendaAtual": 219.0,
          "celula": { "meses": 3, "atual": 6300.0, "anterior": 6000.0, "variacaoPct": 5.0, "status": "VARIACAO", "baseParcial": false, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": null, "anteriorPorDia": null }, "ganhouClientesDoProduto": false, "lancamento": false },
        { "sku": 2210, "descricao": "CREATINA CAPS 120", "fornecedor": "LABORATÓRIO ALFA", "sameSupplier": true, "affinityScore": 0.531, "categoriaGaleria": "Suplementos", "valorVendaAtual": 99.0,
          "celula": { "meses": 3, "atual": 2400.0, "anterior": 3000.0, "variacaoPct": -20.0, "status": "VARIACAO", "baseParcial": false, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": null, "anteriorPorDia": null }, "ganhouClientesDoProduto": false, "lancamento": false }
      ]
    },
    "impactoEmOutrosProdutos": null,
    "diagnosticoIa": {
      "direcao": "QUEDA",
      "diagnosticoMercado": "PERDA_DE_PARTICIPACAO",
      "resumo": "A categoria de creatina cresceu no período, mas este produto perdeu espaço. A maior parte da queda vem de clientes que passaram a comprar o concorrente de menor preço de outro fornecedor, do lançamento recente e da versão menor do próprio fornecedor. A época do ano também pesou. A queda se concentrou em Pernambuco.",
      "fatores": [
        { "tipo": "CANIBALIZACAO_OUTRO_FORNECEDOR", "sentido": "NEGATIVO", "parcelaEstimada": -3400.0, "confianca": "ALTA", "rotulo": "EVIDENCIA",
          "explicacao": "Clientes deste produto reduziram a compra e passaram a comprar o concorrente de menor preço.",
          "evidenciaInterna": "CANIBALIZACAO_OUTRO_FORNECEDOR", "skusCitados": [3301], "fontes": [] },
        { "tipo": "PRODUTO_NOVO", "sentido": "NEGATIVO", "parcelaEstimada": -3100.0, "confianca": "MEDIA", "rotulo": "EVIDENCIA",
          "explicacao": "O lançamento atraiu clientes deste produto logo nos primeiros meses de venda.",
          "evidenciaInterna": "PRODUTO_NOVO", "skusCitados": [3120], "fontes": [] },
        { "tipo": "SAZONALIDADE", "sentido": "NEGATIVO", "parcelaEstimada": -2400.0, "confianca": "MEDIA", "rotulo": "EVIDENCIA",
          "explicacao": "O mês atual costuma vender menos que o mês de comparação para este produto.",
          "evidenciaInterna": "SAZONALIDADE", "skusCitados": [], "fontes": [] },
        { "tipo": "CANIBALIZACAO_MESMO_FORNECEDOR", "sentido": "NEGATIVO", "parcelaEstimada": -1450.0, "confianca": "MEDIA", "rotulo": "EVIDENCIA",
          "explicacao": "Parte dos clientes trocou para a embalagem menor do mesmo fornecedor.",
          "evidenciaInterna": "CANIBALIZACAO_MESMO_FORNECEDOR", "skusCitados": [2046], "fontes": [] },
        { "tipo": "MATERIA_PRIMA", "sentido": "NEGATIVO", "parcelaEstimada": null, "confianca": "MEDIA", "rotulo": "POSSIVEL",
          "explicacao": "Notícias do setor relatam alta no custo da creatina importada, o que pode ter pressionado o preço de reposição.",
          "evidenciaInterna": null, "skusCitados": [],
          "fontes": [ { "url": "https://www.exemplo-noticias-setor.com.br/2026/08/creatina-importada-alta-custo", "dominio": "exemplo-noticias-setor.com.br",
                        "titulo": "Custo da creatina importada sobe com câmbio", "dataPublicacao": "2026-08-14", "origemData": "URL" } ] }
      ],
      "hipotesesNaoConfirmadas": [
        { "tipo": "CLIMA", "descricao": "Período mais frio no Nordeste pode ter reduzido a procura por suplementos de treino.", "motivo": "SEM_FONTE", "fontes": [] },
        { "tipo": "CONCORRENCIA_MERCADO", "descricao": "Redes de farmácia ampliaram marcas próprias de creatina.", "motivo": "SEM_DATA",
          "fontes": [ { "url": "https://www.exemplo-varejo.com.br/marcas-proprias-suplementos", "dominio": "exemplo-varejo.com.br",
                        "titulo": "Marcas próprias ganham espaço em suplementos", "dataPublicacao": null, "origemData": null } ] }
      ],
      "recomendacoes": [
        "Comparar o preço deste produto com o do concorrente de menor preço antes de novas compras.",
        "Avaliar ação comercial em Pernambuco, onde a queda se concentrou."
      ],
      "sugestoesBuscaHtml": null,
      "origem": "llm",
      "modelo": "gemini-4-hydrogen",
      "geradoEm": "2026-11-24T14:10:27.530Z",
      "promptVersion": "tia-v3"
    }
  },
  "meta": {
    "timestamp": "2026-11-24T14:10:27.611Z", "version": "1.2.0",
    "dataReferencia": "2026-11-24", "ultimoDiaCoberto": "2026-11-23", "mesBase": "2026-10",
    "metrica": "revenue", "janela": 3, "modoComparacao": "point", "promptVersion": "tia-v3",
    "indiceAfinidade": { "disponivel": true, "lastSyncAt": "2026-11-24T03:00:41.512Z" },
    "avisos": [],
    "ia": { "podeGerar": true, "motivoBloqueio": null, "diagnosticoSalvo": true, "diagnosticoSalvoEm": "2026-11-24T14:10:27.530Z", "geracaoEmAndamento": false, "diagnosticoVencido": false, "geraComIa": true, "motivoTemplate": null, "podeForcar": true, "orcamento": { "nivel": "NORMAL" } },
    "origem": "llm", "motivoTemplate": null, "reutilizado": false, "modelo": "gemini-4-hydrogen", "geradoEm": "2026-11-24T14:10:27.530Z"
  }
}
```

Conferência dos números (para o `tester`): `Σ parcelas = −2.400 − 1.161,60 − 3.100 − 1.450 − 3.400 − 900 = −12.411,60`; `resíduo = −14.000 − (−12.411,60) = −1.588,40`; cobertura `= (1 − 1.588,40 ÷ 14.000) × 100 = 88,7`. Grupo afim sem o SKU: `G_pre = 30.000`, `G_cur = 36.300`, `V = 21,0%`, `efeitoMercado = 8.400`, `efeitoParticipacao = −22.400`, `m = 0,273 ≤ 0,30` → `PERDA_DE_PARTICIPACAO`. `semMigracao = −22.400 + 7.950 = −14.450` (≥ 20% de 14.000) → indicador com `min(14.450; 1.588,40)`. Preço: `(1,06 × (1 − 1,4 × 0,06)) − 1 = −0,02904` × 40.000.

---

### 3.3 `GET /api/v1/sales-trend/insights/supplier/{supplierKey}` — **fase 7.4**

> Rota reservada no 1.1.0 e **não implementada** até a fase 7.4. Até lá responde `404` do FastAPI (rota inexistente). O detalhamento final pode acrescentar campos (versão `1.3.0`, compatível).

- **Path:** `supplierKey` = chave opaca `fornecedorChave` da Tendência (`"f:<nome normalizado>"` ou `"sem-fornecedor"`), 1..200 caracteres; inexistente no universo → `404 TIA-002`.
- **Query:** os mesmos de 3.1.
- **`data` previsto (`SupplierInsight`):** `{ fornecedor, fornecedorChave, qtdProdutos, celula, modoDiagnostico, direcao, resumoNumerico, cascata (soma parcela a parcela dos SKUs, P-172), canibalizacaoInternaPortfolio: { receitaMovida, netMarginImpact, pares: [{ vitima: {sku, descricao}, canibalizador: {sku, descricao}, receitaMigrada, clientesMigrados, mecanismo }] }, diagnosticoMercado (fornecedor × afins de outros fornecedores), produtosQueMaisContribuiram: [{ sku, descricao, deltaObservado, principalParcela }] (até 10), diagnosticoIa, ia }`.
- **Geração com IA do fornecedor:** `POST /api/v1/sales-trend/insights/supplier/{supplierKey}/generate`, mesmo corpo e regras de 3.2 (P-174), também na fase 7.4.

---

### 3.4 `GET /api/v1/sales-trend/insights/health`

- **Objetivo (P-187):** estado operacional sem chamar o LLM e sem ler o banco. Lê o nível do livro de gastos (cache de 60 s) e os metadados do índice. **Não expõe custo**: sem dólares, tokens, consultas de busca, preços ou teto (4.4); quem precisa dos números consulta o Cloud Billing e o livro no GCS.
- **Resposta `200`:**

```json
{
  "data": {
    "ia": {
      "ligada": true,
      "modeloPadrao": "gemini-4-hydrogen",
      "modeloFallback": "gemini-3.8-flash",
      "promptVersion": "tia-v3",
      "modeloRadar": "gemini-4-hydrogen"
    },
    "radar": { "radarVersion": "radar-v1", "radaresEmCache": 11, "radaresGeradosMes": 7 },
    "orcamento": { "mes": "2026-11", "nivel": "NORMAL" },
    "indiceAfinidade": {
      "disponivel": true,
      "lastSyncAt": "2026-11-24T03:00:41.512Z",
      "totalActiveSkus": 1339,
      "origem": "GCS"
    },
    "cacheMigracao": [
      { "modoComparacao": "point", "janela": 3, "mesBase": "2026-10", "carregadoEm": "2026-11-24T13:58:02.100Z", "expiraEm": "2026-11-24T19:58:02.100Z", "duracaoCargaMs": 4210, "pares": 3812 },
      { "modoComparacao": "average", "janela": 12, "mesBase": "2026-10", "carregadoEm": "2026-11-24T14:00:40.022Z", "expiraEm": "2026-11-24T20:00:40.022Z", "duracaoCargaMs": 9870, "pares": 9144 }
    ]
  },
  "meta": { "timestamp": "2026-11-24T14:12:00.000Z", "version": "1.2.0", "dataReferencia": "2026-11-24" }
}
```

`radar` traz só a versão do prompt do radar e contagens de objetos (sem valores, consultas ou assuntos). `ia.ligada` é o kill-switch `TREND_AI_ENABLED` (booleano); não existe campo de credencial (Vertex AI usa a conta de serviço). `orcamento.nivel` ∈ `NORMAL`, `ALERTA`, `ESGOTADO`. `indiceAfinidade.origem` ∈ `GCS`, `LOCAL`. `cacheMigracao` não traz SKUs nem clientes, só contagem de pares. **Erros:** nenhum específico.

---

### 3.5 `POST /internal/v1/affinity-index/sync` (rota de máquina, tarefa 7.0 c)

- **Objetivo:** sincronizar o Índice de Afinidade (mesma rotina de `sync_product_affinity_index`) e gravar o resultado no GCS (ADR-009 DA-06). Substitui o laço 00:00 dentro do processo.
- **Quem chama:** Cloud Scheduler, `0 0 * * *` `America/Sao_Paulo`. **A tela nunca chama.** Uso manual: `gcloud scheduler jobs run <job>`; a rota existente `POST /api/v1/analytics/affinity/sync` (Basic) continua para uso operacional.
- **Autenticação:** `Authorization: Bearer <ID token OIDC do Google>`. Validados: assinatura, `aud = AFFINITY_SYNC_AUDIENCE`, `email = AFFINITY_SYNC_INVOKER_SA`, `email_verified = true`. O Basic Auth global é dispensado **só** para este método e caminho. Fora do Cloud Run de produção (sem as variáveis), a rota responde `401`.
- **Query:** `force` (boolean, default `false`): reconstrução completa mesmo sem mudança de hash.
- **Corpo:** nenhum.
- **Resposta `200`:**

```json
{
  "data": {
    "lastSyncAt": "2026-11-24T03:00:41.512Z",
    "recomputed": true,
    "totalActiveSkus": 1339,
    "galleryProductsFetched": 1180,
    "galleryMatchedSkus": 1021,
    "addedCount": 3,
    "updatedCount": 1,
    "removedCount": 2,
    "unchangedCount": 1335,
    "durationMs": 38215,
    "geracaoObjeto": "1764039641512000"
  },
  "meta": { "timestamp": "2026-11-24T03:00:41.900Z", "version": "1.2.0" }
}
```

- **Erros:**

| HTTP | `code` | Quando |
| :--- | :--- | :--- |
| `401` | `TIA-006` | Token ausente, inválido, expirado, audiência ou chamador diferente (a resposta não diz qual) |
| `409` | `TIA-007` | Outra sincronização em andamento (lease `locks/affinity-sync.lock`) |
| `503` | `ANL-001` | Catálogo do ERP ou galeria indisponível; o índice anterior no GCS permanece |

---

## 4. Matriz de Erros HTTP Mapeados

### 4.1 Corpo único de erro (`InsightErrorResponse`)

```json
{
  "error": { "code": "TIA-001", "message": "Parâmetros inválidos para o diagnóstico.", "fields": ["window", "comparisonMode"], "motivo": null },
  "meta": { "timestamp": "2026-11-24T14:00:00.000Z", "version": "1.2.0" }
}
```

| Campo | Tipo | Descrição |
| :--- | :--- | :--- |
| `error.code` | string | Código interno; a tela decide sempre por ele |
| `error.message` | string | Mensagem fixa em PT-BR, sem valor recebido, sem SQL, sem stacktrace |
| `error.fields` | string[] | Nomes dos campos inválidos (`TIA-001`, e `["baseMonth"]` em `TIA-003` quando o mês foi informado); lista vazia nos demais |
| `error.motivo` | string \| `null` | Só em `TIA-004` (`429`): `LIMITE_DE_PEDIDOS`, `LIMITE_DIARIO` |

### 4.2 Códigos

| HTTP | `code` | Quando | `message` (fixa) | Regra |
| :--- | :--- | :--- | :--- | :--- |
| `400` | `TIA-001` | `sku` não inteiro/≤ 0; `metric`, `window`, `comparisonMode` fora do domínio; `baseMonth` fora do formato ou futuro; corpo do `POST` inválido (`force` não booleano, JSON malformado) | "Parâmetros inválidos para o diagnóstico." | P-150 |
| `404` | `TIA-002` | SKU fora do Catálogo Ativo; `supplierKey` inexistente (7.4) | "Produto ou fornecedor não encontrado no catálogo ativo." | P-150 |
| `422` | `TIA-003` | Mês-Base anterior à base ou sem dia coberto | "Não há base de vendas suficiente para diagnosticar esta janela." | P-151 |
| `422` | `TIA-003` | `POST /generate` em modo `SEM_VARIACAO` | "Não há variação relevante para analisar." | P-152 |
| `429` | `TIA-004` | `motivo = LIMITE_DE_PEDIDOS` (2/min) ou `LIMITE_DIARIO` (10/dia por usuário; `force` 3/dia); header `Retry-After` | "Limite de análises com IA atingido. A parte numérica continua disponível." | P-176 |
| `200` | — | **Não é mais erro:** IA desligada, indisponível, orçamento esgotado ou gate de não chamada → resumo por template (`meta.origem = "template"`, `meta.motivoTemplate`) | — | P-178.5, P-183.3, P-188 |
| `200` + aviso | `TIA-005` | Índice de afinidade indisponível (em `meta.avisos`, nunca como erro) | "Índice de produtos afins em atualização: canibalização e grupo afim não avaliados." | P-173 |
| `503` | `ANL-001` | Base de vendas (SQL Server) indisponível para a célula da Tendência | "Base de vendas indisponível no momento. Tente novamente em instantes." | P-173 |
| `401` | — | Produção sem credencial Basic (middleware global) | Comportamento existente (`WWW-Authenticate: Basic`) | P-033 |
| `401` / `409` | `TIA-006` / `TIA-007` | Só na rota interna (3.5): token OIDC ausente/inválido/chamador não autorizado (a resposta não diz qual) / sincronização já em andamento | "Não autorizado." / "Sincronização já em andamento." | ADR-009 DA-06, CP-3 |
| `500` | — | Erro não previsto | Corpo genérico, sem stacktrace | `security-anti-patterns` |

Exemplos:

```json
{ "error": { "code": "TIA-002", "message": "Produto ou fornecedor não encontrado no catálogo ativo.", "fields": [], "motivo": null },
  "meta": { "timestamp": "2026-11-24T14:00:00.000Z", "version": "1.2.0" } }
```

```json
{ "error": { "code": "TIA-003", "message": "Não há variação relevante para analisar.", "fields": [], "motivo": null },
  "meta": { "timestamp": "2026-11-24T14:00:00.000Z", "version": "1.2.0" } }
```

```json
{ "error": { "code": "TIA-004", "message": "Limite de análises com IA atingido. A parte numérica continua disponível.", "fields": [], "motivo": "LIMITE_DE_PEDIDOS" },
  "meta": { "timestamp": "2026-11-24T14:00:00.000Z", "version": "1.2.0" } }
```

```json
{ "error": { "code": "ANL-001", "message": "Base de vendas indisponível no momento. Tente novamente em instantes.", "fields": [], "motivo": null },
  "meta": { "timestamp": "2026-11-24T14:00:00.000Z", "version": "1.2.0" } }
```

- A validação do FastAPI é convertida pela classe de rota do módulo (`InsightsAPIRoute`), sem handler global (ADR-009 DA-11).
- `sku`, `baseMonth` e `supplierKey` nunca aparecem na mensagem nem nos logs.

### 4.3 Conformidade com privacidade (P-185)

| Bloco | Contém dado pessoal? | Observação |
| :--- | :--- | :--- |
| `cascata[].itens`, `impactoEmOutrosProdutos` | Não | Só SKU, fornecedor (marca) e contagens/somas de clientes |
| `CLIENTES_PERDIDOS.detalhe` | Não | Só `clientesPerdidosQtd` |
| `REGIONAL.evidencia.porUf` | Não | UF com < 3 clientes agregada em `"OUTRAS"`; nenhuma contagem de clientes exposta |
| `diagnosticoIa` | Não | Gerado a partir do pacote sem cliente (P-179); validado antes de salvar |
| `health` | Não | Só contagens agregadas, booleano `ia.ligada` e nível do orçamento |

---

### 4.4 Campos de custo e orçamento que NÃO são expostos ao cliente

Nenhuma resposta (rotas de produto, fornecedor, `health`, erros) nem objeto salvo devolvido à tela contém:

| Dado | Onde fica |
| :--- | :--- |
| Valores em dólar (gasto do mês/dia, teto, saldo, reserva, custo por diagnóstico) | Livro `ai-budget/AAAA-MM.json` no GCS, logs estruturados e Cloud Billing |
| Percentual do orçamento usado | Idem (a API só devolve o `nivel`) |
| Tokens de entrada/saída/*thinking* | Log estruturado da etapa (sem prompt) |
| Consultas de busca executadas e cota de *grounding* | Livro e log |
| Tabela de preços (`TREND_AI_PRICING_JSON`) e constantes de orçamento | Variáveis de ambiente |
| `evidenceHash`, chave de cache, caminhos e gerações do GCS, `radarRef` do `StoredInsight` | Interno (DA-07). O `StoredInsight` gravado guarda custo, tokens e consultas, mas o mapper da API os descarta |
| Consultas de busca do radar, teto de busca do mês, `radarHash`, chave e caminho `radar/...` no GCS, gasto e contadores de radar no livro, texto bruto das páginas | Objeto do radar, livro e log. A API só devolve dimensões, tema, frase fixa, fontes validadas e idade. Atingir o teto de busca aparece ao cliente apenas como radar `AUSENTE`/`DESATUALIZADO` e `SEM_RADAR_EXTERNO`, sem citar limite ou custo |
| Credenciais (não há chave de API; o Vertex usa ADC) | — |

Teste de contrato: serializar todas as respostas e falhar se aparecer qualquer chave `usd`, `custo`, `token`, `consultas`, `preco`, `teto`, `gasto`, `saldo`, `evidenceHash` (T-7.2.9).

---

## 5. Diretrizes de Integração no Frontend

- **Serviço:** `features/sales-trend/services/trend-insights.service.ts` (`getProductInsight`, `generateProductInsight`, `getInsightsHealth`). Estado do painel num store com Signals próprio do painel (`loading`, `success`, `generating`, `error`).
- **Botões (P-175, P-176, P-188):** "Gerar análise com IA" quando `meta.ia.geraComIa = true` e não há salvo; "Gerar resumo automático" quando `geraComIa = false` (a resposta vem rotulada "Resumo automático (sem IA)", com o motivo em linguagem simples); "Atualizar" quando `diagnosticoVencido`; "Gerar de novo" quando há salvo (confirmação antes de `force = true`). **Não existe "Análise aprofundada".** Desabilitar durante o pedido, quando `meta.ia.podeGerar = false` e, no caso de `force`, quando `podeForcar = false`. Com `geracaoEmAndamento = true`, mostrar "gerando" e refazer o `GET` a cada 5 s até 150 s. A tela **não mostra** valores de custo ou orçamento; no nível `ALERTA` pode exibir um aviso genérico e no `ESGOTADO`, o rótulo de resumo automático.
- **Timeout HTTP do `POST`:** 150 s.
- **Link para a Canibalização (Design Plan Q-D2, Q-D8):** `/analytics/canibalizacao?periodo=90&busca={sku}`; quando a F6 aceitar `abrir` (tarefa 7.3-F6), `&abrir={sku}` abre direto o drawer de equilíbrio de preço. O painel exibe a nota "A Canibalização usa períodos em dias (90 dias); os números podem diferir das janelas em meses desta análise".
- **Sugestões de busca (`sugestoesBuscaHtml`):** só em `<iframe sandbox>` e só se o checkpoint aprovar (ADR-009 CP-10); nunca `innerHTML` na página.
- **Erros:** decidir por `error.code` e `error.motivo`; `TIA-004` mantém o painel numérico visível.
- **Fontes (P-184.5):** link externo com `rel="noopener noreferrer"` e `dominio` visível; `resumo`, `recomendacoes` e `descricao` das hipóteses renderizados como texto puro (sem `innerHTML`).
- **Tipagem (TypeScript, sem `any`):**

```typescript
export type DiagnosisMode = 'QUANTITATIVO' | 'QUALITATIVO' | 'SEM_VARIACAO';
export type ParcelType = 'SAZONALIDADE' | 'PRECO' | 'PRODUTO_NOVO' | 'CANIBALIZACAO_MESMO_FORNECEDOR' | 'CANIBALIZACAO_OUTRO_FORNECEDOR' | 'CLIENTES_PERDIDOS';
export type EvaluationStatus = 'AVALIADO' | 'SEM_EFEITO' | 'NAO_AVALIADO';
export type Confidence = 'ALTA' | 'MEDIA' | 'BAIXA';
export type MarketDiagnosis = 'MERCADO_EM_QUEDA' | 'MERCADO_EM_ALTA' | 'PERDA_DE_PARTICIPACAO' | 'GANHO_DE_PARTICIPACAO' | 'MISTO' | 'SEM_GRUPO_AFIM' | 'NAO_AVALIADO';

export interface MigrationItem {
  sku: number; descricao: string; fornecedor: string | null; sameSupplier: boolean; affinityScore: number; lancamento: boolean;
  receitaMigrada: number | null; clientesMigrados: number | '<3'; confianca: Confidence;
  mecanismo: 'PRECO_MENOR_DESTROI_MARGEM' | 'PRECO_MENOR_MARGEM_PRESERVADA' | 'MIGRACAO_POR_VALOR' | null; netMarginImpact: number | null;
}

export interface CascadeParcel {
  tipo: ParcelType; status: EvaluationStatus; valor: number | null; pontosPercentuais: number | null; valorReceita: number | null;
  sentido: 'NEGATIVO' | 'POSITIVO' | null; explicativa: boolean | null; cortada: boolean; confianca: Confidence | null;
  motivoNaoAvaliado: string | null; motivoSemEfeito: string | null; detalhe: Record<string, unknown> | null; itens: MigrationItem[];
}

export interface InsightWarning { codigo: string; mensagem: string; }

export type TemplateReason = 'GATE_VARIACAO' | 'GATE_RESIDUO_BAIXO' | 'GATE_VALOR_BAIXO' | 'ORCAMENTO_ESGOTADO' | 'IA_DESLIGADA' | 'IA_INDISPONIVEL';
export type GenerationOrigin = 'cache' | 'template' | 'llm' | 'fallback';
export type AiModel = 'gemini-4-hydrogen' | 'gemini-3.8-flash';

export interface InsightMeta {
  timestamp: string; version: string; dataReferencia: string; ultimoDiaCoberto: string; mesBase: string;
  metrica: 'revenue' | 'quantity'; janela: 1 | 3 | 6 | 12; modoComparacao: 'point' | 'average'; promptVersion: string;
  indiceAfinidade: { disponivel: boolean; lastSyncAt: string | null }; avisos: InsightWarning[];
  ia: {
    podeGerar: boolean; motivoBloqueio: 'SEM_VARIACAO' | null;
    geraComIa: boolean; motivoTemplate: TemplateReason | null;
    diagnosticoSalvo: boolean; diagnosticoSalvoEm: string | null; diagnosticoVencido: boolean;
    podeForcar: boolean; geracaoEmAndamento: boolean;
    orcamento: { nivel: 'NORMAL' | 'ALERTA' | 'ESGOTADO' };
  };
}

export interface GenerateMeta extends InsightMeta {
  origem: GenerationOrigin; motivoTemplate: TemplateReason | null; reutilizado: boolean;
  modelo: AiModel | null; geradoEm: string | null;
}

export interface ProductInsightResponse { data: ProductInsight; meta: InsightMeta; }
export interface GenerateInsightResponse { data: ProductInsight; meta: GenerateMeta; }
export interface InsightErrorResponse {
  error: { code: string; message: string; fields: string[]; motivo: 'LIMITE_DE_PEDIDOS' | 'LIMITE_DIARIO' | null };
  meta: { timestamp: string; version: string };
}
export interface SourceRef {
  url: string; dominio: string; titulo: string; dataPublicacao: string | null; origemData: 'MODELO' | 'URL' | null;
}
// ProductInsight, AffineItem (celula: TrendCell do contrato da Tendência), Indicator, MarketDiagnosisBlock,
// ImpactBlock e AiDiagnosis (inclui explicacao, origem, hipoteses com fontes, sugestoesBuscaHtml): espelham 3.1.1 a 3.1.6.
// ProductInsight acrescenta resumoAutomatico: string | null (só em origem = 'template'). Nenhum tipo carrega custo, tokens ou orçamento em dólar.
```

### 5.1 Respostas às dúvidas do Design Plan (`design/plans/analytics-tendencia-ia.md` §13)

| # | Resposta | Onde |
| :-: | :--- | :--- |
| Q-D1 | **Aceito.** Cada parcela traz `pontosPercentuais` (`valor ÷ baseAjustada × 100`, 1 casa) | 3.1.1 |
| Q-D2 | **Aceito como tarefa da F6 na fase 7.3** (`?abrir={sku}` na página de Canibalização). Até lá, link só com `busca={sku}` | §5, tasks 7.3 |
| Q-D3 | **Aceito.** `AfimItem.celula` é a `TrendCell` completa da Tendência | 3.1.4 |
| Q-D4, Q-D5, Q-D9 | Fora do contrato (frontend). Q-D4 e Q-D5 aceitos como refatorações sem mudança de comportamento na 7.3; Q-D9 fica como T7 separada | tasks 7.3 |
| Q-D6 | **Aceito.** `impactoEmOutrosProdutos` vem no `GET` (é do motor, P-171) | 3.1.5 |
| Q-D7 | **Aceito com ajuste (v1.1.0):** `meta.ia` traz o **nível** do orçamento (`NORMAL`/`ALERTA`/`ESGOTADO`), geração em andamento e data da análise salva; **valores usado/restante/teto saíram por decisão de custo e privacidade operacional (4.4)** | 2.1 |
| Q-D8 | **Aceito.** Link com `periodo=90` e nota de que os números podem diferir | §5 |

---

## 6. Padrão de documentação no código (obrigatório para o Desenvolvedor)

| Camada | Padrão |
| :--- | :--- |
| Python: topo de arquivo | Docstring do módulo com objetivo e as regras atendidas (`P-15X`) |
| Python: constantes | Em `trend_insights/domain/constants.py`, cada uma com comentário de intenção e a regra; as marcadas "(reuso)" são **importadas** do módulo de origem |
| Python: funções públicas | Docstring Google (Args/Returns/Raises) com `Regra: P-1XX` e o porquê quando não óbvio |
| Pydantic / OpenAPI | `Field(description=...)` em PT-BR; `Literal[...]` nos enums; `responses={400, 404, 422, 429, 503}` com `model=InsightErrorResponse` (o `503` só vale para `ANL-001`); `json_schema_extra` com os exemplos 3.1.7, 3.1.8 e 3.2.1; `TREND_INSIGHTS_CONTRACT_VERSION = "1.1.0"`; a rota interna com `include_in_schema=False` |
| TypeScript | Comentário de topo por arquivo; TSDoc nas exportações com a regra; proibido `any` |
| Logs | Só etapa, latência, modelo, tokens, custo, status, tamanhos e `PROMPT_VERSION` (P-185.2); nunca pacote, prompt, resposta, SKU+cliente ou a chave de API |
