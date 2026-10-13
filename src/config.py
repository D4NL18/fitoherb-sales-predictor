"""
Configurações, caminhos e hiperparâmetros do pipeline de Precificação Compensatória.
Re-export para manter retrocompatibilidade com a suíte de testes.
"""
from src.core.config import PipelineConfig, DEFAULT_CONFIG

__all__ = ["PipelineConfig", "DEFAULT_CONFIG"]
