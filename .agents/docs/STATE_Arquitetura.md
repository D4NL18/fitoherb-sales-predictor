# STATE_Arquitetura — Etapa 2 (Arquiteto), Fase 1 Analytics Cross-sell

**Branch:** `feature/analytics-cross-sell` · **Data:** 2026-11-05 · **Status:** concluído, aguardando checkpoint

## Artefatos
- `.agents/docs/adr/ADR-002-modulo-analytics-cross-sell.md` (DA-01 a DA-12, DC-1 a DC-5)
- `.agents/docs/api_contracts/analytics-cross-sell.md` (v1.0.0, Apêndice A = variante POST)
- `.agents/docs/tasks/analytics-cross-sell.md` (T-01..T-16, B-01..B-18, F-01..F-11, ordem de commits)

## Decisões-chave
- Agregado `order_baskets` único em `int32` (`DENSE_RANK` do pedido, `DATEDIFF` desde 2000-01-01, `HAVING SUM(Qtd) > 0`, data de corte por bind parameter), lido com `fetchmany(50_000)`. ~13 MB; pico de carga estimado 150–250 MB; residente < 30 MB.
- Reuso de `filter_orphan_baskets`/`build_basket_matrix` sem mudança; `mine_association_rules` ganha `max_len` opcional (única mudança no `pricing`).
- Cache por snapshot imutável, lock de voo único, TTL 6 h, troca atômica, sem cache por cliente, carga preguiçosa (sem `lifespan`).
- Erros: `XSL-001..004` (domínio) + `ANL-001` (503, banco) e `ANL-002` (429, reload recente); handler de validação escopado a `/api/v1/analytics` (400), demais módulos seguem com 422.
- Explicação P-065 montada no domínio.
- A-11: proposta GET com path (alinhada ao Privacy Officer); POST especificado como alternativa.

## Pendências para o checkpoint (Orquestrador)
- DC-1 (A-11), DC-2 (rota de reload e códigos `ANL-*`), DC-3 (`max_len` no `pricing`), DC-4 (premissa A-13: pedido com cliente único), DC-5 (busca só por código).
- Dívidas observadas fora de escopo: `Response` não importado em `custom_404_handler` (`src/api.py`); `test_db_connection` devolve `str(e)`.

## Revisão após Design Plan e parecer de privacidade (2026-11-05)
- Q-1: `GET /products/search` opcional (contrato §3.6, DC-5; ~0,5 dia de backend + ~1 dia de frontend).
- Q-2: `data.produto` sempre presente. Q-3: `explicacao { frequencia, intensidade, evidencia, motivo }`. Q-4: `pedidosEmComum` no modo cliente (DC-6). Q-5: `meta.parametros`. Q-6: `error { code, message, fields[] }`. Q-7: health com `estadoCache` e `duracaoUltimaCargaMs`.
- Allowlist LGPD-03 revisada no contrato §4.1. `customerCode` continua sem eco; GET com path mantido como proposta.

## Dependências novas
- Nenhuma.
