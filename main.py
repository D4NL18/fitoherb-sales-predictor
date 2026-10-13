"""
Ponto de entrada (CLI) para execução do Sistema de Precificação Dinâmica Compensatória.
Fitoherb Nordeste Distribuidora.
"""
import argparse
import sys
from pathlib import Path

from src.config import DEFAULT_CONFIG, PipelineConfig
from src.pipeline import run_full_pricing_pipeline


def parse_args():
    parser = argparse.ArgumentParser(
        description="Fitoherb Sales Predictor: Pipeline de Precificação Compensatória e Mineração de Cestas B2B.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    # Origem de dados (por padrão consome direto do SQL Server)
    parser.add_argument(
        "--catalog",
        type=str,
        default=None,
        help="Caminho opcional para arquivo de catálogo (se omitido, consome direto de Externo01.Produto no SQL Server)."
    )
    parser.add_argument(
        "--sales",
        type=str,
        default=None,
        help="Caminho opcional para arquivo de vendas (se omitido, consome direto de Externo01.Vendas no SQL Server)."
    )

    parser.add_argument(
        "--output-csv",
        type=str,
        default=str(DEFAULT_CONFIG.output_csv_path),
        help="Caminho de saída para a tabela CSV de precificação recomendada."
    )
    parser.add_argument(
        "--output-sql",
        type=str,
        default=str(DEFAULT_CONFIG.output_sql_path),
        help="Caminho de saída para o script SQL de atualização de preços no banco/ERP."
    )

    # Hiperparâmetros de Negócio & Cesta Fechada
    parser.add_argument(
        "--k-ratio",
        type=float,
        default=DEFAULT_CONFIG.k_basket_ratio,
        help="Fração máxima K da cesta permitida para produtos âncora promocionais (ex: 0.25 = 25%% do valor do pedido)."
    )
    parser.add_argument(
        "--top-anchors",
        type=int,
        default=DEFAULT_CONFIG.top_n_anchors,
        help="Quantidade de produtos âncora (iscas) a eleger para receberem desconto."
    )
    parser.add_argument(
        "--half-life",
        type=float,
        default=DEFAULT_CONFIG.temporal_half_life_days,
        help="Meia-vida em dias para o decaimento temporal exponencial das vendas (ponderação de relevância histórica)."
    )

    # Hiperparâmetros de Precificação Prescritiva
    parser.add_argument(
        "--anchor-min-discount",
        type=float,
        default=DEFAULT_CONFIG.anchor_min_discount,
        help="Desconto percentual máximo permitido no produto âncora (ex: -0.15 = até 15%% de desconto)."
    )
    parser.add_argument(
        "--anchor-max-discount",
        type=float,
        default=DEFAULT_CONFIG.anchor_max_discount,
        help="Desconto percentual mínimo a conceder no produto âncora (ex: -0.05 = pelo menos 5%% de desconto)."
    )
    parser.add_argument(
        "--comp-max-increase",
        type=float,
        default=DEFAULT_CONFIG.comp_max_increase,
        help="Reajuste percentual máximo permitido nos itens compensadores (ex: 0.06 = até 6%% de acréscimo)."
    )

    # Hiperparâmetros de Mineração e Estresse
    parser.add_argument(
        "--min-support",
        type=float,
        default=DEFAULT_CONFIG.min_support,
        help="Suporte mínimo para mineração de regras frequentes no algoritmo FP-Growth."
    )
    parser.add_argument(
        "--stress-drop",
        type=float,
        default=DEFAULT_CONFIG.stress_volume_drop_pct,
        help="Taxa de retração de volume simulada no teste de estresse dos compensadores (ex: 0.05 = 5%%)."
    )

    return parser.parse_args()


def main():
    args = parse_args()

    config = PipelineConfig(
        catalog_path=Path(args.catalog) if args.catalog else None,
        sales_path=Path(args.sales) if args.sales else None,
        output_csv_path=Path(args.output_csv),
        output_sql_path=Path(args.output_sql),

        k_basket_ratio=args.k_ratio,
        top_n_anchors=args.top_anchors,
        temporal_half_life_days=args.half_life,
        anchor_min_discount=args.anchor_min_discount,
        anchor_max_discount=args.anchor_max_discount,
        comp_max_increase=args.comp_max_increase,
        min_support=args.min_support,
        stress_volume_drop_pct=args.stress_drop,
    )

    try:
        summary = run_full_pricing_pipeline(config)
        print("\n" + "=" * 80)
        print("RESUMO EXECUTIVO DA EXECUÇÃO DO PIPELINE:")
        print("=" * 80)
        print(f"Total de SKUs Ativos no Catálogo: {summary['total_skus_catalogo']}")
        print(f"Total de Vendas Analíticas Pós-Funil: {summary['total_vendas_higienizadas']}")
        print(f"Total de Regras de Associação Mineradas: {summary['total_regras_mineradas']}")
        print(f"Produtos Âncora Eleitos: {summary['ancoras_eleitos']}")
        print(f"Produtos Compensadores Eleitos: {summary['compensadores_eleitos']}")
        print("\n--- REPLAY HISTÓRICO 2026 (TRAVA DE CESTA K%) ---")
        for k, v in summary['replay_2026'].items():
            print(f"  * {k}: {v}")
        print("\n--- TESTE DE ESTRESSE DE REAÇÃO ADVERSA (QUEDA DE VOLUME) ---")
        for k, v in summary['stress_test'].items():
            print(f"  * {k}: {v}")
        print("\n--- ARQUIVOS DE ENTREGA GERADOS ---")
        print(f"  * Tabela CSV Consolidada: {summary['output_csv']}")
        print(f"  * Script de Atualização SQL: {summary['output_sql']}")
        print("=" * 80)
        print("Pipeline executado com sucesso!\n")
    except Exception as e:
        print(f"Erro durante a execução do pipeline: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
