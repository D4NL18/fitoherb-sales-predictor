# Review Radar externo v3.1 (revisao amostral)

Testes: `pytest tests/trend_insights tests/sales_trend tests/analytics -q` = 1061 passed.
Escopo da leitura: budget_ledger, constants, radar_runner/service (logs); demais arquivos NAO lidos linha a linha.

## Bloqueante
- Nenhum encontrado.

## Importante
- src/modules/trend_insights/domain/constants.py:115 RADAR_RESERVED_MONTHLY_USD=0.22 nao ratificado. Nao estoura o teto de US$ 2:
  budget_ledger.py:163 soma headroom na checagem mensal do diagnostico e o radar passa por reserve() com o mesmo teto (:163) + fatia 25% (:126).
  Risco real e de disponibilidade: diagnosticos negados (BudgetDenied) antes do fim do mes. Falta ratificacao do PO/arquiteto e registro em ADR-009 DA-13.
- budget_ledger.py:141: headroom = 0 ate o 1o radar do mes (mes sem radar usa o teto inteiro); o diagnostico pode consumir o teto antes do 1o radar. Confirmar que e intencional.
- constants.py:105 RADAR_PROMPT_VERSION="radar-v1" vs "tia-v3": confirmar versao em docs/contrato 1.2.0.
- Testes superados (test_gates_template, test_llm_orchestrator, test_hard_cap_is_invisible_to_the_client): justificativa esta em tasks (commit 7e35129); nao reconferi o diff de cada um.

## Nit
- radar_runner.py:155 loga so model/status/contagem/custo (sem PII/payload). OK. radar_service.py:219 idem.
- budget_ledger.py:123-143: _check_radar_caps e _radar_headroom poderiam sair para domain/budget.py (SRP; o ledger tem 249 linhas).
- pytest: marca `slow` nao registrada (tests/sales_trend/test_performance.py:20).
