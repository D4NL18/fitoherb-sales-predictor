"""
Configurações, caminhos e hiperparâmetros do pipeline de Precificação Compensatória.
Core Settings para a plataforma Fitoherb.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class PipelineConfig:
    # Origem de dados SQL Server (P-022) - Produtos e Vendas extraídos diretamente do banco
    use_database: bool = True
    db_schema: str = "Externo01"
    products_view: str = "Externo01.Produto"
    sales_view: str = "Externo01.Vendas"

    # Caminhos opcionais de arquivos locais (se informados manualmente)
    catalog_path: Optional[Path] = None
    sales_path: Optional[Path] = None
    fallback_catalog_path: Optional[Path] = None
    template_catalog_path: Optional[Path] = None
    template_sales_path: Optional[Path] = None

    output_dir: Path = Path("outputs")
    output_csv_path: Path = Path("outputs/precificacao_compensatoria_recomendada.csv")
    output_sql_path: Path = Path("outputs/precificacao_compensatoria_recomendada.sql")


    # Regras de Negócio e Limpeza (P-001 a P-004)
    min_price_ratio: float = 0.40          # Preço praticado mínimo (40% do catálogo)
    outlier_percentile: float = 99.5       # Percentil de corte de quantidade por pedido
    catalog_skiprows: int = 4              # Linhas de cabeçalho do ERP Atrio a pular
    catalog_delimiter: str = ";"           # Delimitador do CSV do catálogo
    sales_delimiter: str = ","             # Delimitador do CSV de vendas
    default_cost_ratio: float = 0.60       # Custo base estimado (60% do preço de tabela -> margem 40%)

    # Mineração de Cestas e Âncoras (P-005, P-006)
    min_basket_size: int = 2               # Mínimo de SKUs válidos na cesta (elimina órfãs)
    min_support: float = 0.002             # Suporte mínimo no FP-Growth
    min_confidence: float = 0.02           # Confiança mínima
    min_lift: float = 1.05                 # Lift mínimo para considerar associação relevante
    top_n_anchors: int = 15                # Quantidade de produtos âncora a eleger
    max_compensators_per_anchor: int = 10  # Máximo de compensadores associados por âncora

    # Pesos do Score Composto do Âncora (P-006)
    weight_giro: float = 0.40
    weight_penetracao: float = 0.35
    weight_lift: float = 0.25

    # Decaimento Temporal Exponencial (P-007)
    temporal_half_life_days: float = 100.0 # Meia-vida em dias (90 a 120 dias)

    # Restrições do Motor Prescritivo (P-008, P-009)
    anchor_min_discount: float = -0.15     # -15%
    anchor_max_discount: float = -0.05     # -5%
    comp_min_increase: float = 0.01        # +1%
    comp_max_increase: float = 0.06        # +6%
    margin_floor_pct: float = 0.05         # Preço novo >= Custo * 1.05
    k_basket_ratio: float = 0.25           # Trava comercial da cesta (K = 25%)

    # Teste de Estresse e Simulação (P-010)
    stress_volume_drop_pct: float = 0.05   # Simulação de queda de 5% de volume nos compensadores


DEFAULT_CONFIG = PipelineConfig()
