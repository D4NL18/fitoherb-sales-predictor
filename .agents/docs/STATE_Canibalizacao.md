# STATE — FASE F6: Canibalização e Substituição (Orquestrador de Feature)

| Campo | Valor |
| :--- | :--- |
| **Feature** | F6: Canibalização e Substituição (`analytics-canibalizacao`) |
| **Branch** | `feature/analytics-canibalizacao` |
| **Worktree** | `C:\Users\danie\Documents\Github\fitoherb-analytics-canibalizacao` |
| **Faixa de Regras** | `P-128` a `P-138` |
| **Prefixo de Erros** | `CAN-XXX` (`CAN-001` a `CAN-005`) |
| **Etapa Atual** | Etapa 1 — Descoberta, Regras de Negócio e Especificação |
| **Status** | Em andamento (limite restrito até Checkpoint da Etapa 2) |
| **Bypasses Homologados** | DBA (somente leitura de agregados SQL Server existentes); Privacy Officer (conduz revisão de minimização/by design com bypass de RIPD completo pois opera no nível de SKU sem expor dados pessoais) |

---

## 1. Escopo e Diretrizes da Feature F6

- **Objetivo Central:** Identificar se uma ação sobre um SKU alvo (início de promoção `promo`, variação de preço `price` ou novo lançamento `launch`) provocou perda de volume em itens substitutos (`CANIBALIZACAO`), ganho conjunto (`COMPLEMENTO`) ou se o efeito é indistinguível de ruído (`SEM_EFEITO`), quantificando o **efeito líquido** em volume, receita e margem de contribuição.
- **Conexão com F5 (Elasticidade):** A arquitetura e contratos desenham a interface com a futura F5 para decompor a parcela da variação explicada por elasticidade cruzada $\epsilon_{ij} \times \Delta P_i$. A implementação de código (Etapas 3 e 4) fica suspensa até a entrega de F5.

---

## 2. Log de Progresso da Esteira

- **2026-11-12 (Início):** Inicialização do orquestrador de feature isolado em worktree própria.
- **2026-11-12 (Etapa 1 - analyst):** Mapeamento de P-128 a P-138 em `.agents/docs/business_rules/analytics-canibalizacao.md` e planejamento técnico em `.agents/docs/tasks/analytics-canibalizacao.md`.
