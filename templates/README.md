# Templates de Dados (Data Templates)

Este diretório contém arquivos de **template/amostra sanitizados e anonimizados** que ilustram a estrutura e os esquemas de dados utilizados pelo projeto **fitoherb-sales-predictor**, sem expor nenhuma informação sensível, confidencial ou pessoal (LGPD).

---

## 1. Arquivos Disponíveis

| Arquivo | Descrição | Formato / Delimitador |
|---|---|---|
| [`vendas_template.csv`](./vendas_template.csv) | Template do histórico de vendas por item de nota fiscal | CSV (delimitador vírgula `,`, strings com aspas duplas `"`, UTF-8) |
| [`lista_precos_template.csv`](./lista_precos_template.csv) | Template da lista de preços simplificada no formato de exportação de relatório do ERP (com cabeçalho/rodapé do sistema) | CSV (delimitador ponto e vírgula `;`, UTF-8) |
| [`lista_precos_limpa_template.csv`](./lista_precos_limpa_template.csv) | Versão tabular direta e limpa da lista de preços (ideal para importação direta em ferramentas de BI e bancos de dados) | CSV (delimitador ponto e vírgula `;`, UTF-8) |

---

## 2. Dicionário de Dados

### 2.1 Tabela de Vendas (`vendas_template.csv`)

| Campo | Tipo Sugerido | Descrição | Exemplo de Template |
|---|---|---|---|
| `Data` | `DATETIME` | Data e hora de emissão/registro da venda (`YYYY-MM-DD HH:MM:SS.000`) | `2025-01-10 00:00:00.000` |
| `Numero Nota` | `INTEGER` / `VARCHAR` | Número do documento fiscal emitido | `100001` |
| `Pedido` | `INTEGER` / `VARCHAR` | Número identificador do pedido comercial | `50001` |
| `Cod Cliente` | `INTEGER` | Identificador único do cliente | `101` |
| `Cliente` | `VARCHAR(255)` | Razão Social ou Nome Fantasia do cliente | `FARMACIA MODELO LTDA` |
| `Cidade` | `VARCHAR(100)` | Cidade do cliente | `SALVADOR` |
| `UF` | `CHAR(2)` | Estado / Unidade Federativa | `BA` |
| `Operação` | `VARCHAR(50)` | Tipo da operação comercial realizada | `VENDA` |
| `Cod Produto` | `INTEGER` | Código do produto vendido (chave de ligação com a Lista de Preços) | `500101` |
| `Produto` | `VARCHAR(255)` | Nome e descrição comercial do produto | `COLAGENO HIDROLISADO 300G` |
| `EAN` | `VARCHAR(14)` | Código de barras padrão EAN-13 | `7890000000011` |
| `Fornecedor` | `VARCHAR(100)` | Fabricante, fornecedor ou marca do produto | `FITONUTRI BRASIL` |
| `Cod Vendedor` | `INTEGER` | Código identificador do vendedor | `10` |
| `Vendedor` | `VARCHAR(100)` | Nome do vendedor | `CARLOS SILVA` |
| `Cod Promocao` | `INTEGER` | Código identificador da promoção (`0` indica venda sem promoção) | `0` |
| `Promoção` | `VARCHAR(100)` | Descrição da campanha ou promoção aplicada (ou vazio) | `CAMPANHA VERAO 2025` |
| `Valor Venda` | `DECIMAL(10,2)` | Valor total da venda do item faturado em R$ (ponto como separador decimal) | `49.90` |
| `Qtd Venda` | `DECIMAL(10,2)` | Quantidade de unidades faturadas | `1.0` |

---

### 2.2 Tabela de Lista de Preços (`lista_precos_template.csv` / `lista_precos_limpa_template.csv`)

| Campo | Tipo Sugerido | Descrição | Exemplo de Template |
|---|---|---|---|
| `Código` | `INTEGER` | Código identificador do produto (relaciona com `Cod Produto`) | `500101` |
| `Descrição` | `VARCHAR(255)` | Descrição detalhada do produto | `COLAGENO HIDROLISADO 300G` |
| `Fornec/Marca` | `VARCHAR(100)` | Fornecedor ou marca parceira | `FITONUTRI BRASIL` |
| `Und` | `VARCHAR(10)` | Unidade de comercialização (ex: `UN`, `CX`, `FR`) | `UN` |
| `Preço` | `DECIMAL(10,2)` | Preço unitário de tabela em R$ (vírgula como separador decimal no relatório ERP) | `49,90` |
| `Sit` | `CHAR(1)` | Situação do estoque (`A` = +30 dias, `B` = +15 dias, `C` = -15 dias) | `A` |
| `Tipo` | `VARCHAR(100)` | Linha ou agrupamento de catálogo do produto | `LINHA FITONUTRI` |

---

## 3. Como Carregar em Python (Pandas)

```python
import pandas as pd

# 1. Carregar histórico de vendas
df_vendas = pd.read_csv(
    "templates/vendas_template.csv",
    parse_dates=["Data"]
)

# 2. Carregar lista de preços (formato relatório ERP, ignorando cabeçalho de 4 linhas)
df_precos = pd.read_csv(
    "templates/lista_precos_template.csv",
    sep=";",
    skiprows=4,
    decimal=",",
    encoding="utf-8"
)
# Remover eventuais colunas em branco decorrentes do delimitador final
df_precos = df_precos.loc[:, ~df_precos.columns.str.contains('^Unnamed')]

# 3. Cruzar vendas com lista de preços
df_completo = pd.merge(
    df_vendas,
    df_precos,
    left_on="Cod Produto",
    right_on="Código",
    how="left"
)

print(df_completo.head())
```

> [!NOTE]
> Para arquivos de produção brutos gerados diretamente pelo ERP, utilize `encoding="latin1"` caso contenham caracteres com codificação Windows-1252/ISO-8859-1.
