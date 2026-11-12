# STATE_Review — Etapa 4 (Quality Gate 360) · Fase 1 Analytics / F4 Cross-sell

**Agente:** `reviewer` · **Data:** 2026-11-10 · **Branch:** `feature/analytics-cross-sell` (sem commits; diff no working tree)
**Skills carregadas:** `clean-code-guard`, `code-reviewer` (git-expert sem objeto: não há commits a auditar).
**Regras aplicadas:** clean-code-anti-patterns, business-logic-isolation, error-handling, api-contract, security-anti-patterns, documentation-governance, git-commit.

## Veredito: APROVADO COM RESSALVAS

O código do módulo está limpo, isolado e com tratamento de erro correto. Três pontos precisam ser resolvidos antes da Etapa 5 (B-1 e B-2 pelo `developer`/`architect`; B-3 é decisão do usuário). Nenhum deles exige refatoração do domínio.

## Achados BLOQUEANTES (resolver antes da Etapa 5)

| # | Local | Problema | Correção sugerida |
|---|-------|----------|-------------------|
| B-1 | `src/modules/pricing/domain/basket_mining.py:67-69` | A docstring de `mine_association_rules` diz que o `analytics` usa `max_len=2`. Desde a revisão de DA-04 isso é falso. O parâmetro ficou sem chamador de produção (só T-06), o que viola YAGNI (clean-code-guard nº 14) e mantém uma mudança no módulo `pricing` sem motivo. | Preferível: reverter `max_len` em `basket_mining.py` e remover os 3 testes T-06 de `tests/test_basket_mining.py` (o arquivo volta ao estado da `main`). Alternativa mínima: manter o parâmetro e corrigir a docstring ("parâmetro opcional; nenhum chamador atual"), registrando o motivo em DA-04. |
| B-2 | `.agents/docs/api_contracts/analytics-cross-sell.md:11,59` e `src/modules/analytics/api/schemas.py:18` | Com a P-094, o comportamento observável das rotas `/cross-sell/product/{sku}` e `/cross-sell/customer/{customerCode}` mudou: (a) `totalItems` ≤ 10 e a paginação conta a lista curada; (b) a ordem deixa de ser a de P-061.1/P-064.2 pura e passa a ser por faixa (mesmo fornecedor → similar → resto); (c) variantes da origem e repetições de linha são omitidas. O contrato continua 1.0.0 e não descreve nada disso. | Subir para **1.1.0** (MINOR: o schema não muda e nenhum campo sai, mas a semântica documentada de ordenação e cardinalidade muda). No documento: cabeçalho e exemplos `version` para 1.1.0; changelog com P-094; em §3.3 e §3.4 trocar a regra de ordenação pela de P-094.2 e registrar o máximo de 10 itens, variantes omitidas e uma por linha; em §2.2/§2.3 dizer que `totalItems`/`totalPages` contam a lista curada (com o `limit` padrão de 50 a resposta cabe em uma página). No código: `ANALYTICS_CONTRACT_VERSION = "1.1.0"`, os exemplos de `schemas.py` e o comentário de versão do modelo TS (`frontend/.../models/cross-sell.model.ts`). Os testes que verificam `version` devem acompanhar. |
| B-3 | `.gitignore:83-85` | `.agents/` (e `AGENTS.md`/`agents.md`) estão no `.gitignore`. Toda a documentação da fase (regras P-058..P-094, ADR-002, contrato, design plan, privacy, tasks, STATE) **não pode ser versionada** e não entra no PR. Isso contraria o espírito de `workflow-documentation-governance-rules.md`: a memória do projeto fica só local. | **Decisão do usuário, sem alteração pelo reviewer.** Opções: (1) remover `.agents/` do `.gitignore` e versionar `.agents/docs/` (manter ignorados só arquivos efêmeros, se houver); (2) manter ignorado de propósito e registrar isso em ADR/STATE. Até haver decisão, a Etapa 5 não deve assumir que as docs vão no PR. |

## Achados NÃO BLOQUEANTES

### Curadoria (P-094) — `src/modules/analytics/domain/recommendation_curation.py`
- **N-1 (lógica, recomendo corrigir junto com B-1/B-2)** `:62-63, :83` — `_supplier` normaliza fornecedor vazio para `""`. Dois produtos **sem fornecedor** no cadastro passam a ser "mesmo fornecedor": o candidato sobe para a faixa 0 sem motivo e, se tiver a mesma 1ª palavra, é descartado como variante. Correção: tratar fornecedor vazio como desconhecido (`priority_tier` não devolve `SAME_SUPPLIER_TIER` e `is_variant` devolve falso quando o fornecedor é vazio), com um teste em `tests/analytics/test_recommendation_curation.py`.
- **N-2** `:62` — `_supplier` sem docstring (as demais funções têm). Trivial.
- **N-3** — O custo de `_significant_words` (regex) é recalculado por item em `priority_tier`, `is_variant` e `product_line_key`. Com listas de ~300 itens é irrelevante; registro apenas. Se as listas crescerem, pré-calcular as palavras no `CatalogEntry`/índice da carga.
- Positivo: funções curtas, constantes nomeadas, early return, genérico por `rule_of`, sem I/O. A heurística está documentada no topo do arquivo e na P-094.

### Mineração — `src/modules/analytics/domain/cross_sell.py`
- `mine_one_to_one_rules` / `_cooccurrence_counts` / `_rules_from_counts` (`:130-185`): corretos. Sem divisão por zero (as linhas fora da diagonal têm `item_orders ≥ pair_orders > 0`, e o retorno antecipado cobre a base vazia). `int32` basta para as contagens, e a pré-filtragem com `FLOAT_TOLERANCE` é coerente com o corte definitivo de `select_useful_rules`. O "porquê" está documentado.
- **N-4** `:205` — `haspair_orders` → `has_pair_orders` (prefixo booleano legível).
- **N-5** `:211` e `:51` — "Converte a saída do mlxtend" / "mesmo formato do `mine_association_rules`" ficaram desatualizados: hoje a entrada vem de `mine_one_to_one_rules`. Ajustar o texto. O mesmo vale para `tests/analytics/test_cross_sell_rules.py:11` ("`max_len=2`").
- **N-6** `:349` `recommend_for_product(snapshot_view, sku)`, `cross_sell_customer.py:113,160,208` (`view`), `api/mappers.py:381` (`catalog`) e `service/analytics_cache.py:323` (`valid_baskets`) estão sem anotação de tipo. Sugestão: um `Protocol` no domínio (DIP), consumido pelo `AnalyticsSnapshot` e pelo `CustomerSnapshotView`.

### Serviço, cache e backtest
- `service/analytics_service.py:192,201`: a curadoria entra depois do ranking e antes da paginação, como P-094 pede. `replace(result, items=...)` preserva `empty_reason`. Correto.
- `domain/cross_sell_backtest.py:168`: o backtest mede o top-5 da lista curada (P-094.5). Correto. A lambda `rule_of` duplica `_rule_of` do serviço; aceitável (2 ocorrências).
- **N-7** `service/analytics_service.py:142-148` — o serviço importa `api.mappers` e `api.schemas`, e `api/mappers.py:274` importa `service.analytics_cache`: a dependência vai de service para api e volta. Não há ciclo de import em runtime e o desenho segue DA-09, mas o ideal é o serviço devolver objetos de domínio e a rota chamar o mapper. Sem ação nesta fase.
- **N-8** `service/analytics_cache.py:337` — `force_reload` recarrega cestas e regras, mas reaproveita o catálogo em cache se ele tiver menos de 6 h (`get_catalog()`). Estoque e preço podem ficar até 6 h defasados depois de uma "recarga manual". Confirmar com o analista se P-068.3 espera também o catálogo novo; se sim, invalidar `_CATALOG` em `_get_or_reload`.
- **N-9** `get_snapshot(force_reload: bool)` e `recommend_for_customer(..., apply_stock_filter: bool)` são argumentos-bandeira (clean-code-guard nº 3). Estão documentados e têm motivo de negócio (P-068.3, P-071.5); fica como sugestão dividir em funções nomeadas no futuro.

### Repositório e segurança
- `repository/sales_repository.py`: único ponto com SQL; `is_readonly_query` antes de conectar; a data de corte vai como bind param `?`; conexão fechada no `finally`; o log registra só o tipo da exceção. Conforme LGPD-02/05.
- **N-10** `:43-61` — o texto da SQL é um f-string que interpola **constantes do módulo** (`SALE_OPERATION`, `ORDER_DAY_EPOCH`), nunca entrada do cliente. Não é injeção, mas a regra "jamais concatenar" é absoluta. Sugestão: deixar os literais no texto, ou passar `SALE_OPERATION` como `?`, e citar a fonte em comentário.
- **N-11** `:39` — `ValueError` em `_DATA_SOURCE_ERRORS` também captura `ValueError` lançado durante a leitura/conversão no bloco `with` do chamador (ex.: `np.array(..., dtype=int32)`), mascarando defeito de dado como `ANL-001` (503). Sugestão: restringir o `ValueError` à obtenção da connection string.
- Sem stacktrace nem `str(e)` nas respostas; sem `except` mudo; um único `try/except` no módulo, que relança como exceção tipada.

### Erros e contrato
- `api/error_handlers.py`: códigos XSL-001..004 e ANL-001/002 mapeados para 404/404/422/400/503/429; a validação devolve só os nomes dos campos; o 422 de pricing/inventory fica preservado por prefixo de path. Conforme.
- Rotas finas (`api/router.py`): só validação de tipo/faixa e chamada ao serviço; constantes nomeadas (`MAX_INT32`, `MIN_OFFSET`). Envelope `data`/`meta` e camelCase via alias em todas as respostas 2xx.
- **N-12** — A remoção da exibição de margem na UI (pedido do usuário) deixa a P-061.4 ("sinaliza margem não positiva") e o Design Plan D-10/§5.8 desatualizados: a API ainda devolve `margemNaoPositiva`, `margemUnitaria` e `custoEstimado`, mas a tela não mostra. Sincronizar a P-061.4 e o Design Plan (`analyst`/`designer`). Os campos podem seguir no contrato (não é breaking change). O subtítulo de `utils/cross-sell-view.ts:199` ("Só entram produtos com estoque e margem") descreve o filtro, não exibe valor; fica a critério do `ux-reviewer`.

### Frontend
- Sem `any` em `frontend/src/app/features/analytics/**`. O componente `recommendation-numbers` foi removido sem referências órfãs.
- `utils/cross-sell-view.ts:186-195`: os títulos "Principal produto / Principais produtos…" usam `plural()` e têm comentário de propósito referenciando P-094. Conforme.
- `app.routes.ts` com lazy-load e item da navbar com `aria-hidden` no SVG. Conforme.

### Governança e higiene
- Nenhum documento solto na raiz (raiz tem só `README.md` e `AGENTS.md`, preexistentes). Artefatos da fase em `.agents/docs/`: business_rules, api_contracts, adr, tasks, privacy, design/plans. Conforme, salvo B-3.
- **N-13** `.claude/launch.json` (untracked) é configuração local da sessão (portas 8000/4210). Não incluir no PR; sugerir `.claude/` no `.gitignore` (decisão do usuário/devops).
- **N-14** `STATE.md`, seção "Bypasses justificados": o texto do `ai-specialist` ainda diz que a fase "reaproveita a mineração FP-Growth". Atualizar para a contagem direta (DA-04 revisada).
- **N-15** `__pycache__/` aparece dentro de `src/modules/analytics` e `tests/analytics`, mas já está no `.gitignore`. Sem ação.
- Commits: nada a auditar. Na Etapa 5, seguir a ordem atômica da seção 4 do checklist, com Conventional Commits referenciando `P-0xx`. Se B-1 for revertido, `basket_mining.py` e `tests/test_basket_mining.py` saem do diff.

## Fora do escopo (dívida já registrada, não bloqueia)
`custom_404_handler` sem import de `Response`; `Encrypt=no`; `str(e)` em `test_db_connection`; Basic Auth com credencial única; devoluções em pricing/inventory.

## Próximos passos
1. `developer`: B-1 (reverter `max_len` + T-06, ou corrigir a docstring), B-2 (constante 1.1.0 e exemplos), N-1, N-4, N-5.
2. `architect`: contrato 1.1.0 com changelog P-094 (B-2); nota em DA-04 sobre o destino de `max_len`.
3. `analyst`/`designer`: sincronizar P-061.4 e o Design Plan D-10 (N-12).
4. Usuário: decidir B-3 (`.agents/` no `.gitignore`) e N-13.
5. Revalidação do reviewer: só diff dos itens acima (sem nova auditoria completa).

---

## Revalidação — 2026-11-10 (só o diff das correções)

### Veredito final: APROVADO

| Item | Verificação | Status |
|------|-------------|--------|
| B-1 | `git diff main -- src/modules/pricing tests/test_basket_mining.py` vazio: o `pricing` saiu do diff da fase. A nota de revisão de DA-04 (ADR-002:124) registra a reversão por YAGNI. | Resolvido |
| B-2 | Contrato 1.1.0 com changelog (P-094: variantes omitidas, ordem por faixa, uma por linha, máx. 10, `totalItems` da lista curada) e §3.3/§3.4 atualizados. `ANALYTICS_CONTRACT_VERSION = "1.1.0"`, exemplos de `schemas.py`, `test_analytics_api_foundation.py:80,131`, comentários e massas TS em 1.1.0. Nenhum "1.0.0" sobrou fora do changelog. | Resolvido |
| B-3 | `.gitignore:83` documenta a decisão: `.agents/` e `AGENTS.md` versionados, `.claude/` ignorado (N-13 junto). `git status` passa a listar `.agents/` e `AGENTS.md`. | Resolvido |
| N-1/N-2 | `_is_same_known_supplier` usado em `is_variant` e `priority_tier`. Fornecedor vazio deixa de contar como "mesmo fornecedor" e como variante. Docstring em `_supplier`. Teste `test_products_without_supplier_are_not_same_supplier_nor_variants`. | Resolvido |
| N-4/N-5 | `has_pair_orders`; comentários de `_RULE_COLUMNS` e `select_useful_rules` apontam para `mine_one_to_one_rules`. | Resolvido |
| N-14 | O bypass do `ai-specialist` no STATE agora cita a contagem direta. | Resolvido |
| Lint | `islice` em `cross_sell_backtest.py:138`, `zip(..., strict=True)` em `cross_sell_customer.py:51` (Python 3.12 no Dockerfile, compatível), imports ordenados. Sem mudança de comportamento. | Conforme |
| Testes | Reexecutado pelo reviewer: `pytest tests/analytics tests/test_basket_mining.py` → **267 passed**, 0 falhas. O teste de equivalência (`test_cross_sell_rules.py:317-354`) compara com `mine_association_rules` sem `max_len`, então não depende do parâmetro revertido. | Conforme |
| Frontend | Sem `any` em `features/analytics/**`. Karma 81/81 e revalidação de UX informados pelo Orquestrador (não reexecutados pelo reviewer). | Conforme |

### Observações finais (não bloqueantes)
- **R-1** ADR-002: DA-04 itens 2 e 3, e as linhas 114, 219, 237 e 251 (tabela de memória, alternativas, consequências, DC-3) ainda descrevem `max_len` como vigente. A nota de revisão no topo de DA-04 prevalece, mas convém marcar esses trechos como "superado pela revisão de 2026-11-09/10" para não confundir leitores futuros.
- **R-2** `navbar.component.html` solto na **raiz** (untracked) é de outra frente (Tendência de Vendas). Nada da fase depende dele: `navbar.component.ts:8` usa `templateUrl: './navbar.component.html'`, relativo à pasta do componente. O arquivo difere da versão da fase (15+/16-). **Não deve entrar nos commits da Fase 1.** Como é arquivo solto na raiz, a frente dona deve movê-lo ou removê-lo antes do PR dela.
- Seguem em aberto como dívida aceita: N-3, N-6, N-7, N-8, N-9, N-10, N-11 e N-12.

### Liberação para a Etapa 5
Liberado. Na Etapa 5, os commits devem ser atômicos, em Conventional Commits referenciando `P-0xx`, sem incluir `navbar.component.html` da raiz nem `.claude/`. Sugiro um commit `docs:` separado para `.agents/` + `AGENTS.md` + `.gitignore`.
