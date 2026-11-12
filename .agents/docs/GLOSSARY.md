# Glossário de Domínio (Linguagem Ubíqua) — Fitoherb Sales Predictor

Este documento é a referência única de terminologia do projeto. Analista, Arquiteto, Designer, Desenvolvedor, Tester e Reviewer DEVEM usar estes termos em regras de negócio, contratos de API, nomes de variáveis, rótulos de tela e exportações.

- **Contexto delimitado:** Previsão de Estoque e Compras (módulo `inventory`).
- **Contexto delimitado:** Analytics Comercial (módulo `analytics`), seção 3.
- **Última atualização:** 2026-11-10 (feature P-053, Política Mín/Máx 30/60; feature P-058 a P-071, Analytics Cross-sell; feature P-072 a P-093, Tendência de Vendas, seção 4, com visão por fornecedor, só produtos ativos e independente das demais features).
- **Coluna "Identificador no código":** nome atual no contrato JSON ou nome sugerido para os conceitos novos. Os nomes dos campos novos foram confirmados pelo Arquiteto em `api_contracts/inventory.md` (contrato 2.0.0), mantendo `camelCase`.

---

## 1. Termos vigentes

| Termo | Definição | Fórmula / Regra | Identificador no código | Não usar |
| :--- | :--- | :--- | :--- | :--- |
| **VMD (Venda Média Diária)** | Unidades vendidas por dia, em média, na janela de vendas recente. Base de todo o cálculo de estoque. | `quantidade vendida na janela ÷ dias da janela` (P-041) | `vmd` | "giro" como sinônimo em regras (a tela pode exibir "Giro/Dia" como rótulo curto) |
| **Janela de Vendas** | Período recente de vendas usado para calcular a VMD. Padrão 60 dias, ajustável de 15 a 180. | P-041, P-053.1 | `historyWindowDays` | "histórico completo" |
| **Dias de Cobertura** | Quantos dias o estoque atual dura no ritmo atual de vendas. Também chamado de "Autonomia" na tela. | `estoque atual ÷ VMD` (1 casa); 999 ("∞") se VMD = 0 e estoque > 0; 0 se ambos forem 0 (P-055.1) | `diasCobertura` | "autonomia alvo" (conceito revogado) |
| **Dias Mínimo** | Parâmetro da política: quantos dias de venda o estoque deve cobrir, no mínimo, antes de se comprar. Padrão 30. | Inteiro ≥ 1, menor que Dias Máximo (P-053.2, P-053.3) | `minCoverageDays` (request, `/config`, `data.politica`) | "ponto de pedido", "ROP" |
| **Dias Máximo** | Parâmetro da política: até quantos dias de venda a compra deve levar o estoque. Padrão 60. | Inteiro, estritamente maior que Dias Mínimo (P-053.2, P-053.3) | `maxCoverageDays` (request, `/config`, `data.politica`) | "cobertura alvo", "target coverage" |
| **Estoque Mínimo** | Quantidade, em unidades, que corresponde aos Dias Mínimo de venda. Quando o estoque chega nela, compra-se. | `teto(VMD × Dias Mínimo)`; 0 se VMD = 0 (P-053.4) | `estoqueMinimo` (item; CSV "Estoque Mínimo (un)") | "estoque de segurança", "ROP", "ponto de reposição" |
| **Estoque Máximo** | Quantidade, em unidades, que corresponde aos Dias Máximo de venda. É o alvo da compra e o limite acima do qual há excesso. | `teto(VMD × Dias Máximo)`; 0 se VMD = 0 (P-053.5) | `estoqueMaximo` (item; CSV "Estoque Máximo (un)") | "estoque ideal", "estoque alvo" |
| **Política Mín/Máx 30/60** | Política de reposição da Fitoherb: manter entre 30 e 60 dias de estoque; ao chegar em 30 dias, comprar até 60. Os números são o padrão e podem ser ajustados por cálculo. | P-053 a P-056 | — | "modelo ROP", "reposição probabilística" |
| **Lead Time** | Prazo médio, em dias, entre o pedido ao fornecedor e a chegada no Centro de Distribuição. Padrão 15. Usado **apenas** para sinalizar Ruptura Iminente. | P-055.3 | `leadTimeDays` (request), `leadTime` (item) | — |
| **Quantidade Sugerida de Compra** | Unidades a comprar para levar o estoque ao Estoque Máximo, quando o gatilho é atingido. Sem cortes nem tetos. | `max(0, Estoque Máximo − estoque atual)`, arredondado para cima (P-054.2) | `qtdSugeridaCompra` | "demanda teórica", "compra limitada" |
| **Custo Unitário** | Custo de reposição de uma unidade. | Último custo; se ≤ 0, 60% do preço de venda (P-054.5) | `custoUnitario` | — |
| **Investimento Sugerido** | Valor, a preço de custo, da compra sugerida de um item ou do total. | Item: `Quantidade Sugerida × Custo Unitário`; total: soma dos itens (P-054.5, P-054.6) | `investimentoTotalItem`, `investimentoTotalSugerido` | "orçamento", "teto" |
| **Ruptura Iminente** | Status do produto com venda cujo estoque acaba antes de um novo pedido chegar. | `VMD > 0` e `Dias de Cobertura < Lead Time` (P-055.2) | `CRITICAL_STOCKOUT` | "ruptura crítica" em rótulos novos |
| **Abaixo do Mínimo** | Status do produto com venda que atingiu o Estoque Mínimo e precisa de compra (sem estar em ruptura iminente). | `VMD > 0`, `estoque ≤ Estoque Mínimo` e Quantidade Sugerida > 0 (P-055.2) | `REORDER_NEEDED` | "reposição necessária", "abaixo do ROP" |
| **Estoque Saudável** | Status do produto com estoque acima do mínimo e até o máximo. Inclui o SKU sem venda e sem estoque. | `Estoque Mínimo < estoque ≤ Estoque Máximo` e demais casos (P-055.2) | `HEALTHY` | — |
| **Acima do Máximo** | Status do produto com estoque maior que o Estoque Máximo. Inclui o SKU sem venda com estoque > 0. | `estoque > Estoque Máximo` (P-055.2) | `OVERSTOCK` | "excesso / overstock" em rótulos novos |
| **Capital Imobilizado** | Valor a preço de custo do estoque que excede o Estoque Máximo, somado nos itens Acima do Máximo. | `(estoque − Estoque Máximo) × Custo Unitário` (P-055.4) | `capitalImobilizadoOverstock` | "capital parado excedente sobre estoque ideal" |
| **Curva ABC** | Classificação global dos produtos pela receita acumulada na janela de vendas, independentemente do filtro de fornecedor. | A: até 80% da receita; B: até 95%; C: restante e SKUs sem venda | `curvaAbc` | — |
| **SKU** | Produto identificado pelo código interno do ERP. | — | `codigo` | "item", "artigo" em regras |
| **Fornecedor (Laboratório)** | Fabricante ou marca do produto, usado como filtro (P-047.1). A tela exibe "Laboratório / Fornecedor". | — | `fornecedor` | — |

---

## 2. Termos obsoletos (não usar em código, tela ou CSV novos)

| Termo | Situação | Substituto |
| :--- | :--- | :--- |
| Estoque de Segurança (`estoqueSeguranca`) | Removido com P-053 | Estoque Mínimo |
| Ponto de Reposição / ROP (`rop`) | Removido com P-053 | Estoque Mínimo |
| Estoque Ideal / Estoque Ideal Teórico (`estoqueIdeal`, `estoqueIdealTeorico`) | Removido com P-053 e P-056.1 | Estoque Máximo |
| Nível de Serviço / z-score (`serviceLevel`) | Removido com P-056.3 | — |
| Autonomia Alvo / Cobertura Alvo (`targetCoverageDays`) | Removido com P-056.3 | Dias Mínimo e Dias Máximo |
| Desvio-padrão da demanda (`desvioPadraoDemanda`) | Não participa mais de nenhuma regra (P-053.7); removido da resposta da API (ADR-001, DA-04) | — |
| Trava de Variação Física / Teto Físico / Limitado por Espaço (`maxPurchaseVariationPct`, `tetoCompraFisica`, `limitadoPorEspaco`, `qtdSugeridaTeorica`, `skusLimitadosPorEspaco`) | Revogado por P-056.1 | — |
| Teto Orçamentário (`budgetLimit`) | Revogado por P-056.2 | — |
| Reposição Necessária (rótulo) | Substituído | Abaixo do Mínimo |
| Excesso / Overstock (rótulo) | Substituído | Acima do Máximo |

---

## 3. Analytics Comercial — Cross-sell (módulo `analytics`, P-058 a P-071)

Termos já definidos na seção 1 (SKU, Custo Unitário, Fornecedor) valem também aqui com o mesmo significado. Identificadores em `camelCase` são sugestões; o Arquiteto confirma no contrato `api_contracts/analytics-cross-sell.md`.

| Termo | Definição | Fórmula / Regra | Identificador no código | Não usar |
| :--- | :--- | :--- | :--- | :--- |
| **Cliente** | Comprador identificado por um único `Cod Cliente`, sem agrupamento de filiais (D3). Nenhum nome ou documento é exposto. | P-070 | `customerCode` | "usuário", "conta", "loja" |
| **Pedido** | Número do pedido no ERP (`Pedido`). Unidade que forma a Cesta. | — | `pedido` / `orderId` | "venda" como sinônimo de pedido |
| **Venda (operação)** | Linha de `Externo01.Vendas` com `[Operação] = 'VENDA'`. Única operação que forma Cestas e conta como compra no cross-sell. | P-058 | `SALE_OPERATION` | — |
| **Devolução (operação)** | Linha com `[Operação] LIKE 'DEVOLU%'`, quantidade e valor negativos. Não é compra nem co-ocorrência no cross-sell; é abatida nas métricas de quantidade/faturamento das outras fases. | P-058.5; plano §2.3 | `RETURN_OPERATION_PATTERN` | "estorno", "cancelamento" |
| **Cesta** | Conjunto de SKUs distintos de um mesmo Pedido de Venda com quantidade > 0. | P-058.1, P-058.2 | `basket` | "carrinho" |
| **Cesta Válida** | Cesta com pelo menos 2 SKUs distintos; só ela entra na mineração. | P-058.3 (reaproveita P-005) | `validBaskets` | "cesta órfã" (é a descartada) |
| **Regra de Associação** | Afirmação "quem compra o Antecedente também leva o Consequente", medida por Suporte, Confiança e Lift. Nesta fase, sempre 1 → 1. | P-059 | `associationRule` | "correlação" |
| **Antecedente** | SKU que o cliente já leva na regra A → B (o "A"). | P-059.1 | `antecedente` / `antecedentSku` | "gatilho" |
| **Consequente** | SKU sugerido pela regra A → B (o "B"). | P-059.1 | `consequente` / `consequentSku` | "item recomendado" como sinônimo de regra |
| **Suporte** | Fração das Cestas Válidas que contêm A e B juntos. | `pedidos com A e B ÷ Cestas Válidas` (P-059.2) | `suporte` | — |
| **Pedidos em Comum** | Número absoluto de Cestas Válidas com A e B. Base de evidência exibida ao usuário. | P-059.3 (mínimo 10) | `pedidosEmComum` | — |
| **Confiança** | Fração dos pedidos com A que também têm B. Exibida como "em X% dos pedidos com A também há B". | `pedidos com A e B ÷ pedidos com A` (P-059.4) | `confianca` | "probabilidade de compra" |
| **Lift** | Quantas vezes B aparece mais nos pedidos com A do que em um pedido qualquer. 1,0 = sem associação. | `Confiança ÷ (pedidos com B ÷ Cestas Válidas)` (P-059.5) | `lift` | "força" sem qualificação |
| **Regra Útil** | Regra com lift ≥ 1,2, confiança ≥ 0,10 e Consequente que não é Item Trivial. Única usada em recomendações. | P-060 | `usefulRules` | — |
| **Item Trivial** | SKU presente em mais de 15% das Cestas Válidas ("quase todo pedido leva"). | `pedidos com o SKU ÷ Cestas Válidas > 0,15` (P-060.2) | `trivialItems` | "carro-chefe" em regras |
| **Par Trivial** | Regra cujo Consequente é Item Trivial; excluída de toda recomendação. | P-060.3 | — | — |
| **Recomendação por Produto** | Lista de Consequentes das Regras Úteis de um SKU, ordenada por lift. | P-061 | `productCrossSell` | — |
| **Recomendação por Cliente** | Lista de produtos a oferecer a um Cliente, derivada do seu Perfil de Compra, só com itens viáveis, ordenada pela Pontuação de Cross-sell. | P-062 a P-064 | `customerCrossSell` | "oferta automática" |
| **Perfil de Compra** | SKUs comprados pelo Cliente em pedidos de Venda nos últimos 365 dias; servem de Antecedentes. | P-062.1 | `customerProfile` | — |
| **Produto Dormente** | SKU que o Cliente já comprou, mas cuja última compra foi há mais de 90 dias (`DORMANT_DAYS`). | P-062.3 | `DORMENTE` (motivo), `diasDesdeUltimaCompra` | "produto perdido" (termo da Fase 5) |
| **Margem Unitária** | Ganho bruto por unidade vendida. | `Pc.Venda − Custo Unitário` (custo com fallback de 60%) (P-063.3) | `margemUnitaria`, `custoEstimado` | "lucro" |
| **Pontuação de Cross-sell** | Valor em R$ que ordena a Recomendação por Cliente. | `lift × confiança × Margem Unitária`; vários Antecedentes → máximo (P-064) | `pontuacao` | "score" em rótulos de tela |
| **Backtest Temporal** | Avaliação que treina com dados até o fim do mês N−1 e verifica o que aconteceu no mês N, sem vazamento. | P-071.1, P-071.2 | `backtest` | "validação cruzada" |
| **Hit rate@5** | Fração dos clientes avaliados que compraram, no mês N, ao menos um dos 5 primeiros produtos recomendados. | `clientes com acerto ÷ clientes avaliados` (P-071.4) | `hitRateAt5` | "acurácia" |
| **Data de Referência** | Data de corte da base em cache usada no cálculo. | P-066.1 | `dataReferencia` | — |

---

## 4. Analytics Comercial — Tendência de Vendas (módulo `analytics`, P-072 a P-093)

A Tendência de Vendas é uma feature **independente**: seus termos estão todos definidos nesta seção, sem depender das regras de outras features. `Externo01.Vendas`, `Externo01.Produto`, a Venda (`[Operação] = 'VENDA'`) e a Devolução (`[Operação] LIKE 'DEVOLU%'`, quantidade e valor negativos, abatida) são tratados só como fatos da base; SKU e Fornecedor têm o mesmo significado da seção 1. A tela é uma página própria (`/tendencia-vendas`), não uma aba. O usuário diz "item"; nas regras o termo é **SKU** (rótulo de tela sugerido: "Produto"). Identificadores `camelCase` são sugestões; o Arquiteto confirma em `api_contracts/analytics-sales-trend.md`.

| Termo | Definição | Fórmula / Regra | Identificador no código | Não usar |
| :--- | :--- | :--- | :--- | :--- |
| **Tendência de Vendas** | Comparação, por SKU, da venda de uma janela de X meses com a janela imediatamente anterior de mesmo tamanho, nas colunas 1, 3, 6 e 12 meses. | P-072, P-075 | `salesTrend` | "crescimento" sozinho (também há queda), "evolução" |
| **Mês-Base** | Mês civil (`AAAA-MM`) em que terminam todas as Janelas Atuais. Padrão: último mês completo. Pode ser o mês corrente (parcial) ou qualquer mês desde o primeiro com dados. | P-074 | `baseMonth`, `mesBase`, `mesBasePadrao`, `mesBaseMinimo`, `mesBaseMaximo` | "mês de referência" (confunde com Data de Referência), "mês atual" |
| **Janela de X meses** | Conjunto de X meses civis consecutivos, com X em {1, 3, 6, 12}. | P-075.1 | `meses` (1, 3, 6, 12) | "período", "últimos X meses" sem Mês-Base |
| **Janela Atual** | Os X meses que terminam no Mês-Base. | `[M − X + 1, M]` (P-075.1) | `atual` | "período novo" |
| **Janela Anterior** | Os X meses imediatamente anteriores à Janela Atual, de mesmo tamanho, independentemente do ano. É o denominador da variação. | `[M − 2X + 1, M − X]` (P-075.1) | `anterior` | "ano anterior", "mesmo período do ano passado" (a janela anterior NÃO é o ano passado, salvo X = 12) |
| **Quantidade Líquida** | Soma de `[Qtd Venda]` das linhas VENDA e das devoluções (negativas) no recorte. | P-073 (D4) | `quantity` | "quantidade vendida" (ignora devolução) |
| **Faturamento Líquido** | Soma de `[Valor Venda]` das linhas VENDA e das devoluções (negativas) no recorte, em R$ nominais. | P-073 (D4) | `revenue` | "receita", "vendas em R$" sem qualificar |
| **Métrica de Tendência** | Escolha entre Quantidade Líquida e Faturamento Líquido para o cálculo. Padrão: Faturamento Líquido. | P-073 | `metric` (`quantity`\|`revenue`), `metrica` | — |
| **% de Variação** | Variação percentual entre a Janela Atual e a Anterior. | `(atual − anterior) ÷ \|anterior\| × 100`, 1 casa, meio para cima; piso −100% (P-077) | `variacaoPct` | "crescimento %" (quando negativo), "delta" |
| **Piso Zero** | Regra que trata líquido negativo de uma janela (devoluções maiores que vendas) como 0 no cálculo, com selo. | P-077.1 | `devolucaoLiquida` | — |
| **Último Dia Coberto** | Último dia fechado da base: Data de Referência menos 1 dia. O dia corrente fica fora. | P-076.1 | `ultimoDiaCoberto` | "hoje" |
| **Primeira Data da Base** | Data da primeira venda registrada (hoje 2025-01-07). Define o Mês-Base mínimo e a cobertura. | P-074.2, P-076.1 | `primeiraData` | — |
| **Dias Cobertos / Cobertura** | Dias corridos da janela que caem entre a Primeira Data da Base e o Último Dia Coberto; cobertura = dias cobertos ÷ dias da janela. | P-076.2 | `diasCobertos`, `diasJanela` | — |
| **Média Diária da Janela** | Total líquido ÷ dias cobertos; usada quando alguma das janelas está incompleta. | P-076.4 | — | "média mensal" |
| **Base Parcial** | Célula em que a comparação usou média diária porque a Janela Atual (mês corrente) ou a Anterior (início da base) tem menos dias que o previsto. Exibida com selo "Base parcial". | P-076.4 | `baseParcial`, `mesBaseParcial` | "dado incompleto" |
| **Sem Base** | Célula cuja Janela Anterior tem cobertura inferior a 50% (inclui totalmente fora da base); exibida "—", nunca 0%. | P-076.6, P-078 | `SEM_BASE` | "sem dados", "0%" |
| **SKU Novo (Tendência)** | SKU sem venda líquida positiva na Janela Anterior e com venda líquida positiva na Atual (lançamento ou retomada). Variação indefinida; rótulo "Novo". Não confundir com o "produto novo hipotético" (viabilidade de um produto ainda não cadastrado, outra iniciativa). | P-078.1 | `NOVO` | "+∞%", "100%", "produto novo" |
| **Sem Movimento** | Célula com líquido 0 nas duas janelas; exibida "—". | P-078.3 | `SEM_MOVIMENTO` | "estável" (estável é 0,0% de variação) |
| **Catálogo Ativo (Tendência)** | Conjunto de produtos de `Externo01.Produto` com `Pc.Venda > 0`, no catálogo **atual**. Só os SKUs dele entram na tabela, nas buscas e nas somas de fornecedor. SKU fora dele (descontinuado, com `Pc.Venda ≤ 0`, ou sem registro em `Externo01.Produto`) é **excluído de tudo**, sem filtro e sem selo; por isso os totais históricos do fornecedor ignoram produtos descontinuados. | P-072.2 a P-072.4 | `Pc.Venda > 0` (`ACTIVE_PRODUCT_MIN_PRICE`) | "SKU inativo" (conceito removido da feature), "somente ativos" (não há filtro opcional) |
| **Data de Referência (Tendência)** | Data de negócio (UTC-3) do instante da carga do cache; o Último Dia Coberto é essa data menos 1 dia. Define o Mês-Base padrão e a cobertura. | P-074.1, P-083.3 | `dataReferencia` | — |
| **Recarga Manual** | Pedido explícito de recarga do cache (`force_reload`), recusado se a última carga foi há menos de 15 minutos. | P-083.2 | `MIN_RELOAD_INTERVAL_MINUTES`, `TND-005` | — |
| **Base Baixa** | Selo informativo quando a Janela Anterior tem pouco volume (< 10 un ou < R$ 500,00), pois o % exagera. Não altera cálculo nem ordenação. | P-079.1 | `baseBaixa`, `LOW_BASE_MIN_QUANTITY`, `LOW_BASE_MIN_REVENUE` | "dado ruim", "outlier" |
| **Volume Mínimo** | Filtro opcional (padrão 0) que remove células de variação com Janela Anterior abaixo do valor informado. | P-079.3 | `minVolume` (`DEFAULT_MIN_VOLUME`) | "corte", "threshold" na tela |
| **Visão (Tendência)** | Atalho de lista relativo à coluna de ordenação: Todos, Maiores altas (`rising`), Maiores quedas (`falling`), Novos (`new`). | P-080.4 | `view` | "top N" (a tabela traz todos os SKUs) |
| **Coluna de Ordenação** | Janela (1, 3, 6 ou 12) pela qual a tabela é ordenada; padrão 3, decrescente. | P-080.1 | `sortWindow`, `sortDir` | — |
| **TND-NNN** | Prefixo dos códigos de erro de domínio da Tendência de Vendas (`TND-001` 400 validação; `TND-002` 422 mês-base sem dias cobertos; `TND-003` 404 fornecedor não encontrado no detalhe; `TND-004` 503 base de vendas indisponível; `TND-005` 429 recarga manual antes de 15 min). | P-082, P-083.2 | `TND-001` a `TND-005` | — |
| **Agrupamento (Visão)** | Alternador da tabela de Tendência: **por produto** (padrão, uma linha por SKU) ou **por fornecedor** (uma linha por fornecedor, com os SKUs agrupados). Não confundir com a "Visão" de atalho (Todos/Altas/Quedas/Novos). | P-088 | `groupBy` (`product`\|`supplier`) | "agrupar por laboratório", "categoria" (outro eixo, fora do escopo) |
| **Grupo de Fornecedor** | Conjunto dos SKUs **ativos** que têm o mesmo `Fornecedor` no catálogo atual. Identidade por texto normalizado (maiúsculas, acentos e espaços); vale o fornecedor atual para todo o histórico do SKU. | P-089.1, P-089.7 | `fornecedor`, `fornecedorChave`, `qtdProdutos` | "marca", "laboratório" em regras (a tela pode exibir "Laboratório / Fornecedor", como em outras telas do projeto) |
| **Sem Fornecedor** | Grupo dos SKUs ativos com `Fornecedor` nulo, vazio ou só espaços no catálogo ativo. SKU fora do catálogo ativo não entra (fica fora de tudo). É uma linha normal da tabela. | P-089.2 | `NO_SUPPLIER_LABEL`, `NO_SUPPLIER_KEY` | "desconhecido", "outros" |
| **Soma do Fornecedor** | Total líquido, por janela, de todos os SKUs do grupo (líquido bruto, sem piso zero por SKU). O % de variação do fornecedor sai dessa soma, nunca da média dos % dos produtos. | P-089.3 | `atualF`/`anteriorF` (nomes de domínio sugeridos) | "média dos percentuais" |
| **Contribuição (do produto)** | Quanto um SKU puxou a alta ou a queda do fornecedor: em **pontos percentuais** (`(atual − anterior) ÷ anterior do fornecedor × 100`) e em **valor** (`atual − anterior`, em un ou R$; por dia quando Base Parcial). Soma dos filhos = variação do fornecedor. | P-090 | `contribuicaoPp`, `contribuicaoValor` | "participação" (é outra coisa: fatia do total), "impacto" |
| **Ponto Percentual (p.p.)** | Unidade da contribuição; 1 p.p. = 1% da base (anterior) do fornecedor. | P-090.1 | `contribuicaoPp` | "%" na contribuição |
| **Detalhe do Fornecedor** | Consulta paginada, sob demanda (ao expandir a linha), dos SKUs de um fornecedor com variação própria e contribuição. | P-092 | `supplierKey`, `sortBy` (`contribution`\|`variation`) | "filhos no payload" |
