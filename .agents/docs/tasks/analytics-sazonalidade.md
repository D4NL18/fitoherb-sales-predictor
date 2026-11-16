# Entidade / Feature: Analytics Comercial — F1 Detecção de Sazonalidade por Produto

| Campo | Valor |
| :--- | :--- |
| **Branch** | `feature/analytics-sazonalidade` |
| **Plano Mestre** | `.agents/docs/tasks/ia-analytics-vendas.md` (§2, §6) |
| **Regras de Negócio** | `.agents/docs/business_rules/analytics-sazonalidade.md` (P-106 a P-116) |
| **Contrato de API** | `.agents/docs/api_contracts/analytics-sazonalidade.md` (versão 1.0.0) |
| **ADR** | `.agents/docs/adr/ADR-005-sazonalidade-produto.md` |
| **Design Plan** | `.agents/docs/design/plans/analytics-sazonalidade.md` |
| **Privacidade** | Bypass justificado (sem dados de cliente; somente SKU/Produto) |
| **Prefixo de Erros** | `SEA-XXX` |
| **Status** | Etapa 4 concluída — Quality Gate 360 aprovado |

**User Story (US-F1):** *Como comprador ou gestor comercial da Fitoherb, quero consultar a sazonalidade histórica de qualquer produto e visualizar rankings de sazonalidade, identificando com clareza os meses de pico e vale de demanda, a força do padrão e o nível de confiança estatística de cada mês, para planejar compras, produção e estoques sem ser induzido a erro por dados escassos.*

---

## 1. Dúvidas Resolvidas (Especificação)

- **Dúvida:** A base tem apenas ~23 meses; como calcular sazonalidade sem decomposição clássica de 36+ meses?
  - **Decisão:** Uso do método ano a ano de razão sobre média anual com remoção prévia de tendência linear (detrending), declarando explicitamente a confiança do mês (`ALTA`, `MEDIA`, `BAIXA`).
- **Dúvida:** Como tratar meses com apenas uma observação (novembro e dezembro na base de 2025/2026)?
  - **Decisão:** Calculam-se com a observação disponível, mas recebem classificação de confiança `BAIXA` e selo visual de advertência se coincidirem com pico ou vale.
- **Dúvida:** Devoluções devem ser abatidas?
  - **Decisão:** Sim (Decisão D4). Agregado calcula quantidade e faturamento líquidos de devoluções (`[Operação] LIKE 'DEVOLU%'`), truncando saldo negativo mensal em zero.
- **Dúvida:** Quais produtos entram no ranking de mais sazonais?
  - **Decisão:** Apenas produtos elegíveis com força `FORTE` ou `MODERADA` e participação de faturamento $\ge MIN\_REVENUE\_SHARE$ (0,05% da receita total), evitando distorções com itens insignificantes.

---

## 2. Checklist Técnico e Tarefas de Desenvolvimento

### Tarefa 1: Testes Automatizados TDD First (`tests/analytics/`)
- [x] **T-01:** `test_seasonality_domain.py` — Teste com série sintética de 23 meses com pico em março nos dois anos: recupera pico em março com confiança `ALTA` e força `FORTE` (P-106, P-109..P-112).
- [x] **T-02:** `test_seasonality_domain.py` — Teste com série sintética plana (vendas constantes): amplitude ~0, força `FRACA` (P-111).
- [x] **T-03:** `test_seasonality_domain.py` — Teste de elegibilidade: série com 10 meses cai em `INSUFICIENTE` com motivo `HISTORICO_CURTO`; série com 23 meses mas vendas em apenas 4 meses cai em `VENDA_ESPORADICA` (P-107).
- [x] **T-04:** `test_seasonality_domain.py` — Teste de confiança por mês: pico em dezembro (apenas 1 observação) recebe confiança `BAIXA` (P-112).
- [x] **T-05:** `test_seasonality_domain.py` — Teste de devoluções: mês com vendas e devoluções calcula volume líquido abatido; saldo negativo trunca em zero (P-106).
- [x] **T-06:** `test_seasonality_domain.py` — Teste da interface exportada `get_seasonality_index`: valida retorno estruturado reutilizável para F6/F2 (P-109, P-113).
- [x] **T-07:** `test_seasonality_api.py` — Teste dos endpoints: `GET /analytics/seasonality/{sku}` (200, 404 `SEA-001`), `GET /analytics/seasonality/ranking?order=most|least` (200, 400 `SEA-002`, paginação, envelope padronizado).
- [x] **T-08:** `test_seasonality_repository.py` — Teste da query de vendas mensais líquidas: valida `is_readonly_query`, agregação por SKU e ano/mês, abatimento de `DEVOLU%`, ausência de interpolação não segura.

### Tarefa 2: Backend — Repositório, Domínio, Schemas e API
- [x] **B-01:** `repository/sales_repository.py` — Adicionar a consulta agregada de vendas mensais líquidas `fetch_monthly_sales(cutoff: date) -> pd.DataFrame` (`sku`, `sale_year`, `sale_month`, `net_quantity`, `net_revenue`), filtrando `VENDA` e `DEVOLU%`, excluindo mês corrente.
- [x] **B-02:** `domain/seasonality.py` — Criar motor determinístico completo: constantes de negócio, dataclasses, remoção de tendência linear, razões ano a ano, correlação YoY, agrupamento de pico/vale, classificações de força e confiança, e ranking.
- [x] **B-03:** `domain/exceptions.py` e `api/error_handlers.py` — Adicionar exceções `SeasonalityProductNotFoundError` (`SEA-001`), `SeasonalityInvalidParametersError` (`SEA-002`), `SeasonalityInsufficientBaseError` (`SEA-003`) e mapear no `ERROR_STATUS_BY_CODE`.
- [x] **B-04:** `api/schemas.py` — Adicionar schemas da sazonalidade: `MonthlySeasonalityPoint`, `SeasonalityData`, `SeasonalityResponse`, `SeasonalityRankingItem`, `SeasonalityRankingResponse` (herdando de `CamelModel`).
- [x] **B-05:** `service/analytics_cache.py` e `service/analytics_service.py` — Integrar dados mensais no snapshot/cache em memória com lock e TTL, orquestrando `get_product_seasonality(sku)` e `get_seasonality_ranking(order, page_request)`.
- [x] **B-06:** `api/router.py` — Adicionar endpoints `GET /analytics/seasonality/{sku}` e `GET /analytics/seasonality/ranking` com validações via Pydantic/Annotated.

### Tarefa 3: Frontend Angular — Aba Sazonalidade
- [x] **F-01:** `features/analytics/models/seasonality.model.ts` — Interfaces e tipos TypeScript correspondentes aos contratos da API, sem `any`.
- [x] **F-02:** `features/analytics/services/seasonality.service.ts` — Serviço Angular injetável com métodos `getSeasonality(sku)` e `getRanking(order, pageRequest)`.
- [x] **F-03:** `features/analytics/pages/seasonality-page/` — Componente principal da aba: busca rápida de produto com autocomplete, cards de indicadores principais (pico, vale, força, confiança), gráfico interativo de 12 meses e alternador de tabelas de ranking (Mais sazonais / Pouco mensuráveis).
- [x] **F-04:** Gráfico mensal acessível com baseline 1.0, barras destacando pico e vale, e selos de confiança por mês.
- [x] **F-05:** Integração nas rotas e navegação — Adicionar aba "Sazonalidade" em `ANALYTICS_SECTIONS` de `analytics-shell.component.ts` e registrar rota filha em `analytics.routes.ts`.
- [x] **F-06:** Testes unitários do frontend — Specs Jasmine testando carregamento, exibição de pico/vale, estados vazio e erro (100 specs aprovados).

### Tarefa 4: Quality Gate 360 e Finalização
- [x] **Q-01:** Auditoria Clean Code (`reviewer`): aderência às regras do projeto, funções curtas, comentários explicando o porquê, sem código morto nem `any`.
- [x] **Q-02:** Auditoria de UX (`ux_reviewer`): conformidade com o Design System, 8 estados interativos, acessibilidade WCAG AA nos gráficos e paleta de cores.
- [x] **Q-03:** Execução completa da suíte da feature (`tester`): `python -m pytest tests/analytics/test_seasonality_*.py` 100% aprovada (17/17).
- [x] **Q-04:** Commits atômicos no padrão Conventional Commits com rastreamento `P-XXX`.
- [x] **Q-05:** Emissão de relatório executivo ao Orquestrador via `send_message`.
