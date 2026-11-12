# Contrato de API REST: Viabilidade de Produto Novo (`analytics-produto-novo`)

> **Localização Mandatória:** `.agents/docs/api_contracts/analytics-produto-novo.md`  
> **Status:** Versão 1.0.0 (Etapa 2 - Checkpoint de Arquitetura)  
> **Responsável:** Arquiteto de Software (`architect.md` / `api-contract-expert`)  
> **Prefixo de Rota:** `/api/v1/analytics/new-product`  
> **Regras Associadas:** `P-139` a `P-149` (em `.agents/docs/business_rules/analytics-produto-novo.md`)  
> **ADR Associada:** `ADR-008` (em `.agents/docs/adr/ADR-008-produto-novo.md`)

---

## 1. Padrões Globais e Envelope de Comunicação

### 1.1 Convenções de Formato
- **Notação:** Todas as propriedades trafegadas em JSON (payload de envio e resposta) utilizam **`camelCase`**.
- **Datas:** Padrão ISO 8601 UTC (`YYYY-MM-DDTHH:mm:ssZ`).
- **Valores Monetários e Percentuais:** Números decimais de dupla precisão (`float` / `number`), arredondados para 2 casas decimais na camada de apresentação (percentuais representados como fração decimal: $0.35$ = $35,0\%$).
- **Quantidades:** Números inteiros (`integer`), representando unidades físicas.

### 1.2 Envelope Padrão de Sucesso (`200 OK`)
```json
{
  "data": { ... },
  "meta": {
    "timestamp": "2026-11-12T10:00:00Z",
    "version": "1.0.0",
    "dataReferencia": "2026-11-11"
  }
}
```
> Nota: `meta.dataReferencia` (`string YYYY-MM-DD | null`) segue o padrão `AnalyticsMeta` do módulo `analytics`, informando o último dia de pedidos considerado no cache (`null` antes da carga inicial).

### 1.3 Envelope Padrão de Erro (`4xx` / `5xx`)
Segue o mesmo contrato do handler global de erros do módulo `analytics` (`src/modules/analytics/api/error_handlers.py` e `utils/analytics-error.ts`), utilizando `fields: string[]` para mapeamento determinístico de erros por campo (sem ecoar valores recebidos, conforme LGPD-05):
```json
{
  "error": {
    "code": "NEW-XXX",
    "message": "Descrição amigável em português para o usuário.",
    "fields": ["precoVendaPrevisto"]
  },
  "meta": {
    "timestamp": "2026-11-12T10:00:00Z",
    "version": "1.0.0"
  }
}
```
> Para erros não vinculados a um campo específico (`NEW-001`, `NEW-005`), `fields` retorna lista vazia `[]`. Para erros de campo (`NEW-002` → `["tipo"]`, `NEW-003` → `["fornecedor"]`, `NEW-004` → campos infratores), `fields` contém os nomes exatos dos parâmetros em `camelCase`.

---

## 2. Catálogo de Erros Específicos da Feature (`NEW-XXX`)

| Código | HTTP Status | Causa / Cenário | Mensagem Amigável Padronizada |
| :--- | :---: | :--- | :--- |
| `NEW-001` | `422` | Quantidade de lançamentos similares elegíveis no tipo informado é menor que `MIN_SIMILARS = 3` | `"Base de lançamentos similares insuficiente para o tipo selecionado (mínimo de 3 lançamentos necessários; encontrados: {count})."` |
| `NEW-002` | `400` | Tipo de produto informado não existe no catálogo de produtos ativos | `"O tipo de produto informado não foi encontrado no catálogo ativo."` |
| `NEW-003` | `400` | Fornecedor informado não existe no catálogo de produtos ativos | `"O fornecedor informado não foi encontrado no catálogo ativo."` |
| `NEW-004` | `400` | Inconsistência matemática nos atributos numéricos (preço $\le 0$, custo $>$ preço, margem fora de $[0, 1]$) | `"Parâmetros comerciais inconsistentes: {motivo}."` |
| `NEW-005` | `503` | Indisponibilidade temporária de conexão ou timeout na leitura do banco de dados | `"Serviço de análise de produtos temporariamente indisponível. Tente novamente em instantes."` |

---

## 3. Endpoints da Feature

### 3.1 `GET /api/v1/analytics/new-product/options`
Obtém as listas consolidadas e deduplicadas de `tipos` e `fornecedores` existentes no catálogo ativo de produtos (`Pc.Venda > 0`), utilizadas para popular os componentes de seleção na interface.

- **Método:** `GET`
- **Autenticação:** HTTP Basic Auth (padrão da aplicação)
- **Cache:** TTL de 6 horas em memória (servidor)

#### Resposta de Sucesso (`200 OK`)
```json
{
  "data": {
    "tipos": [
      "Capsulas",
      "Comprimidos",
      "Extratos",
      "Florais",
      "Oleos Essenciais",
      "Pomadas",
      "Solucoes Gotas",
      "Tinturas"
    ],
    "fornecedores": [
      "BIO ERVAS IND E COM LTDA",
      "BOTANICA NUTRACEUTICA SA",
      "FITOHERB LABORATORIOS",
      "HERBAL BRASIL DISTRIBUICAO",
      "LABORATORIO NATURALIS",
      "PHYTOS DO BRASIL LTDA"
    ]
  },
  "meta": {
    "timestamp": "2026-11-12T10:00:00Z",
    "version": "1.0.0"
  }
}
```

---

### 3.2 `POST /api/v1/analytics/new-product/forecast`
Executa o motor estatístico híbrido de similaridade e projeta a estimativa conservadora de vendas, faixas de incerteza, teto maduro de mercado e análise de viabilidade financeira de margem para o produto hipotético informado.

- **Método:** `POST`
- **Headers Requeridos:** `Content-Type: application/json`
- **Autenticação:** HTTP Basic Auth

#### Corpo da Requisição (`NewProductForecastRequest`)
| Campo | Tipo | Obrigatório | Restrições / Validações | Descrição |
| :--- | :---: | :---: | :--- | :--- |
| `tipo` | `string` | **Sim** | Não vazio, existente em `options.tipos` | Categoria de produto do catálogo. |
| `fornecedor` | `string` | **Sim** | Não vazio, existente em `options.fornecedores` | Fabricante / parceiro comercial pretendido. |
| `descricao` | `string` | **Sim** | 3 a 120 caracteres | Descrição livre do item em linguagem natural. |
| `precoVendaPrevisto` | `number` | **Sim** | `> 0.00` | Preço de venda planejado para o produto (R$). |
| `custoUnitario` | `number` | Não | Se informado: `> 0.00` e `<= precoVendaPrevisto` (quando igual, margem bruta = `0.00`) | Custo de aquisição unitário do item (R$). |
| `margemMinimaDesejada` | `number` | Não | Se informado: entre `0.00` e `1.00` ($0\%$ a $100\%$) | Margem bruta percentual mínima almejada. |
| `horizonMonths` | `integer` | Não | $\{1, 2, 3\}$, padrão: `3` | Horizonte de projeção em meses civis. |

#### Exemplo de Requisição (com parâmetros de viabilidade completos)
```json
{
  "tipo": "Tinturas",
  "fornecedor": "FITOHERB LABORATORIOS",
  "descricao": "Tintura Mae de Melissa Officinalis 50ml Frasco Vidro Conta-Gotas",
  "precoVendaPrevisto": 42.50,
  "custoUnitario": 19.10,
  "margemMinimaDesejada": 0.50,
  "horizonMonths": 3
}
```

#### Resposta de Sucesso (`200 OK`)
```json
{
  "data": {
    "inputSummary": {
      "tipo": "Tinturas",
      "fornecedor": "FITOHERB LABORATORIOS",
      "descricao": "Tintura Mae de Melissa Officinalis 50ml Frasco Vidro Conta-Gotas",
      "precoVendaPrevisto": 42.50,
      "custoUnitario": 19.10,
      "margemMinimaDesejada": 0.50,
      "horizonMonths": 3
    },
    "monthlyForecast": [
      {
        "month": 1,
        "calendarMonth": 11,
        "quantity": 38,
        "revenue": 1615.00,
        "grossMargin": 889.20,
        "p10Quantity": 22,
        "conservativeQuantity": 38,
        "p50Quantity": 64,
        "similarP25Quantity": 54,
        "seasonalityFactor": 1.00,
        "seasonalityConfidence": "BAIXA"
      },
      {
        "month": 2,
        "calendarMonth": 12,
        "quantity": 44,
        "revenue": 1870.00,
        "grossMargin": 1029.60,
        "p10Quantity": 26,
        "conservativeQuantity": 44,
        "p50Quantity": 72,
        "similarP25Quantity": 63,
        "seasonalityFactor": 1.00,
        "seasonalityConfidence": "BAIXA"
      },
      {
        "month": 3,
        "calendarMonth": 1,
        "quantity": 51,
        "revenue": 2167.50,
        "grossMargin": 1193.40,
        "p10Quantity": 31,
        "conservativeQuantity": 51,
        "p50Quantity": 85,
        "similarP25Quantity": 73,
        "seasonalityFactor": 1.00,
        "seasonalityConfidence": "PADRAO"
      }
    ],
    "seasonalityStatus": "FALLBACK_NEUTRAL",
    "aggregatedTotals": {
      "totalQuantity": 133,
      "totalRevenue": 5652.50,
      "totalGrossMargin": 3112.20,
      "averageMonthlyQuantity": 44,
      "averageMonthlyRevenue": 1884.17
    },
    "financialViability": {
      "precoVenda": 42.50,
      "custoUnitario": 19.10,
      "margemBrutaUnitaria": 23.40,
      "margemBrutaPercentual": 0.5506,
      "margemMinimaDesejada": 0.50,
      "viavel": true,
      "parecer": "Produto viavel: margem bruta projetada de 55,1% supera a margem minima de 50,0%."
    },
    "marketCeiling": {
      "tetoMaduroP75": 210,
      "descricao": "Percentil 75 das vendas mensais de produtos maduros do tipo Tinturas (referencial de mercado pleno; nao representa meta de lancamento)."
    },
    "similarsUsed": [
      {
        "sku": "1042",
        "descricao": "Tintura de Passiflora Incarnata 50ml",
        "fornecedor": "FITOHERB LABORATORIOS",
        "primeiraVenda": "2025-05-10",
        "precoHistorico": 39.90,
        "scoreFinal": 0.9125,
        "scoreFornecedor": 1.00,
        "scorePreco": 0.9388,
        "scoreTfidf": 0.8350,
        "quantidadesPrimeirosMeses": [58, 65, 80]
      },
      {
        "sku": "1089",
        "descricao": "Tintura Mae de Valeriana Officinalis 50ml",
        "fornecedor": "FITOHERB LABORATORIOS",
        "primeiraVenda": "2025-06-01",
        "precoHistorico": 44.00,
        "scoreFinal": 0.8940,
        "scoreFornecedor": 1.00,
        "scorePreco": 0.9659,
        "scoreTfidf": 0.7650,
        "quantidadesPrimeirosMeses": [52, 60, 75]
      },
      {
        "sku": "1150",
        "descricao": "Tintura de Camomila Matricaria 50ml Gotas",
        "fornecedor": "HERBAL BRASIL DISTRIBUICAO",
        "primeiraVenda": "2025-04-18",
        "precoHistorico": 38.00,
        "scoreFinal": 0.6845,
        "scoreFornecedor": 0.00,
        "scorePreco": 0.8941,
        "scoreTfidf": 0.9288,
        "quantidadesPrimeirosMeses": [45, 50, 68]
      }
    ],
    "methodologyNotice": "Estimativa calculada sob criterio conservador (Percentil 25 dos similares com haircut de 0,70). Historicamente, mais de 80% dos lancamentos reais superam estes volumes."
  },
  "meta": {
    "timestamp": "2026-11-12T10:00:00Z",
    "version": "1.0.0",
    "dataReferencia": "2026-11-11"
  }
}
```

---

## 4. Definições de Tipos (TypeScript / Angular)

```typescript
import { AnalyticsMeta } from './analytics.model';

export type SeasonalityConfidence = 'ALTA' | 'MEDIA' | 'BAIXA' | 'INSUFICIENTE' | 'PADRAO';

export type SeasonalityStatus = 'APPLIED' | 'FALLBACK_NEUTRAL' | 'UNAVAILABLE';

export interface NewProductOptions {
  tipos: string[];
  fornecedores: string[];
}

export interface NewProductForecastRequest {
  tipo: string;
  fornecedor: string;
  descricao: string;
  precoVendaPrevisto: number;
  custoUnitario?: number | null;
  margemMinimaDesejada?: number | null;
  horizonMonths?: number;
}

export interface MonthlyForecastItem {
  month: number;
  calendarMonth?: number;
  quantity: number;
  revenue: number;
  grossMargin: number | null;
  p10Quantity: number;
  conservativeQuantity: number;
  p50Quantity: number;
  similarP25Quantity: number;
  seasonalityFactor: number;
  seasonalityConfidence?: SeasonalityConfidence;
}

export interface AggregatedTotals {
  totalQuantity: number;
  totalRevenue: number;
  totalGrossMargin: number | null;
  averageMonthlyQuantity: number;
  averageMonthlyRevenue: number;
}

export interface FinancialViability {
  precoVenda: number;
  custoUnitario: number | null;
  margemBrutaUnitaria: number | null;
  margemBrutaPercentual: number | null;
  margemMinimaDesejada: number | null;
  viavel: boolean | null;
  parecer: string | null;
}

export interface MarketCeiling {
  tetoMaduroP75: number;
  descricao: string;
}

export interface SimilarProductItem {
  sku: string;
  descricao: string;
  fornecedor: string;
  primeiraVenda: string;
  precoHistorico: number;
  scoreFinal: number;
  scoreFornecedor: number;
  scorePreco: number;
  scoreTfidf: number;
  quantidadesPrimeirosMeses: number[];
}

export interface NewProductForecastData {
  inputSummary: NewProductForecastRequest;
  monthlyForecast: MonthlyForecastItem[];
  seasonalityStatus?: SeasonalityStatus;
  aggregatedTotals: AggregatedTotals;
  financialViability: FinancialViability;
  marketCeiling: MarketCeiling;
  similarsUsed: SimilarProductItem[];
  methodologyNotice: string;
}

export interface ApiResponse<T> {
  data: T;
  meta: AnalyticsMeta;
}

export interface NewProductApiErrorResponse {
  error: {
    code: 'NEW-001' | 'NEW-002' | 'NEW-003' | 'NEW-004' | 'NEW-005' | 'ANL-001' | 'ANL-002';
    message: string;
    fields: string[];
  };
  meta: {
    timestamp: string;
    version: string;
  };
}
```

---

## 5. Interface de Integração com Sazonalidade (Fase F1)

Para consumo desacoplado e injeção de dependência na camada de serviço:

```python
from abc import ABC, abstractmethod
from typing import NamedTuple

class SeasonalityResult(NamedTuple):
    index: float       # ex: 1.05
    confidence: str    # 'ALTA', 'MEDIA', 'BAIXA', 'INSUFICIENTE', 'PADRAO'

class SeasonalityProvider(ABC):
    @abstractmethod
    def get_category_seasonality(self, category: str, month: int) -> SeasonalityResult:
        """
        Retorna o índice sazonal da categoria para o mês civil informado (1 a 12).
        Deve retornar index = 1.0 e confidence = 'PADRAO' caso a categoria
        não tenha histórico mensurável ou ocorra fallback.
        """
        pass
```
