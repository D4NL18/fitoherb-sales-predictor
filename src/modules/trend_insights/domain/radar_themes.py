"""
Temas FECHADOS do radar por dimensao e frases fixas em pt-BR (P-180.3, v3.1). O radar nao guarda texto livre da
web: o modelo escolhe um `tema` da lista e o backend exibe a frase correspondente (sem digitos, sem dado de produto).
"""
from typing import Dict, Tuple

THEME_OTHER = "OUTRO"

RADAR_THEMES: Dict[str, Tuple[str, ...]] = {
    "POLITICA_REGULATORIO": ("NOVA_REGRA_SANITARIA", "TRIBUTO_OU_TARIFA", "FISCALIZACAO_OU_PROIBICAO", "INCERTEZA_POLITICA", THEME_OTHER),
    "CLIMA_SAFRA": ("QUEBRA_DE_SAFRA", "SAFRA_RECORDE", "SECA_OU_GEADA", "CHUVA_EXCESSIVA", THEME_OTHER),
    "CUSTO_MATERIA_PRIMA": ("INSUMO_MAIS_CARO", "INSUMO_MAIS_BARATO", THEME_OTHER),
    "OFERTA_DEMANDA_MATERIA_PRIMA": ("ESCASSEZ_DE_OFERTA", "OFERTA_ABUNDANTE", "DEMANDA_AQUECIDA_DA_INDUSTRIA", THEME_OTHER),
    "CAMBIO_LOGISTICA_IMPORTACAO": ("DOLAR_MAIS_ALTO", "DOLAR_MAIS_BAIXO", "FRETE_OU_PORTO_COM_PROBLEMA", THEME_OTHER),
    "CONSUMO_MIDIA_SAUDE": ("INTERESSE_EM_ALTA", "INTERESSE_EM_QUEDA", "ESTUDO_OU_MIDIA_SOBRE_SAUDE", THEME_OTHER),
    "CONCORRENCIA": ("LANCAMENTO_DE_CONCORRENTE", "GUERRA_DE_PRECOS", "CAMPANHA_DE_CONCORRENTE", THEME_OTHER),
    "EVENTOS_MERCADO": ("FEIRA_OU_DATA_COMERCIAL", "RECALL_OU_CRISE", "FUSAO_OU_AQUISICAO", THEME_OTHER),
}

_SENTENCES: Dict[Tuple[str, str], str] = {
    ("POLITICA_REGULATORIO", "NOVA_REGRA_SANITARIA"): "Há uma nova regra sanitária ou regulatória no período pesquisado.",
    ("POLITICA_REGULATORIO", "TRIBUTO_OU_TARIFA"): "Houve mudança de tributo ou tarifa no período pesquisado.",
    ("POLITICA_REGULATORIO", "FISCALIZACAO_OU_PROIBICAO"): "Houve fiscalização ou proibição relacionada ao assunto no período.",
    ("POLITICA_REGULATORIO", "INCERTEZA_POLITICA"): "Há incerteza política que pode afetar o assunto pesquisado.",
    ("CLIMA_SAFRA", "QUEBRA_DE_SAFRA"): "A safra do insumo teve quebra na pesquisa do período.",
    ("CLIMA_SAFRA", "SAFRA_RECORDE"): "A safra do insumo foi muito boa na pesquisa do período.",
    ("CLIMA_SAFRA", "SECA_OU_GEADA"): "Seca ou geada afetou a produção do insumo no período pesquisado.",
    ("CLIMA_SAFRA", "CHUVA_EXCESSIVA"): "Chuva excessiva afetou a produção do insumo no período pesquisado.",
    ("CUSTO_MATERIA_PRIMA", "INSUMO_MAIS_CARO"): "O insumo ficou mais caro na pesquisa do período.",
    ("CUSTO_MATERIA_PRIMA", "INSUMO_MAIS_BARATO"): "O insumo ficou mais barato na pesquisa do período.",
    ("OFERTA_DEMANDA_MATERIA_PRIMA", "ESCASSEZ_DE_OFERTA"): "A oferta do insumo ficou escassa no período pesquisado.",
    ("OFERTA_DEMANDA_MATERIA_PRIMA", "OFERTA_ABUNDANTE"): "A oferta do insumo ficou abundante no período pesquisado.",
    ("OFERTA_DEMANDA_MATERIA_PRIMA", "DEMANDA_AQUECIDA_DA_INDUSTRIA"): "Outras indústrias aqueceram a demanda pelo insumo.",
    ("CAMBIO_LOGISTICA_IMPORTACAO", "DOLAR_MAIS_ALTO"): "O dólar mais alto encareceu a importação no período.",
    ("CAMBIO_LOGISTICA_IMPORTACAO", "DOLAR_MAIS_BAIXO"): "O dólar mais baixo barateou a importação no período.",
    ("CAMBIO_LOGISTICA_IMPORTACAO", "FRETE_OU_PORTO_COM_PROBLEMA"): "Frete ou porto tiveram problemas no período pesquisado.",
    ("CONSUMO_MIDIA_SAUDE", "INTERESSE_EM_ALTA"): "O interesse do consumidor pelo assunto cresceu na pesquisa.",
    ("CONSUMO_MIDIA_SAUDE", "INTERESSE_EM_QUEDA"): "O interesse do consumidor pelo assunto diminuiu na pesquisa.",
    ("CONSUMO_MIDIA_SAUDE", "ESTUDO_OU_MIDIA_SOBRE_SAUDE"): "Estudo ou mídia sobre saúde citou o assunto no período.",
    ("CONCORRENCIA", "LANCAMENTO_DE_CONCORRENTE"): "Houve lançamento de concorrente no período pesquisado.",
    ("CONCORRENCIA", "GUERRA_DE_PRECOS"): "Houve disputa de preços entre marcas no período pesquisado.",
    ("CONCORRENCIA", "CAMPANHA_DE_CONCORRENTE"): "Concorrentes fizeram campanhas no período pesquisado.",
    ("EVENTOS_MERCADO", "FEIRA_OU_DATA_COMERCIAL"): "Feira ou data comercial movimentou o mercado no período.",
    ("EVENTOS_MERCADO", "RECALL_OU_CRISE"): "Recall ou crise afetou o mercado no período pesquisado.",
    ("EVENTOS_MERCADO", "FUSAO_OU_AQUISICAO"): "Fusão ou aquisição movimentou o mercado no período.",
}
_OTHER_SENTENCE = "Há um fato relevante nesta dimensão na pesquisa do período."

RADAR_THEME_TEXTS: Dict[Tuple[str, str], str] = {
    (dimension, theme): _SENTENCES.get((dimension, theme), _OTHER_SENTENCE)
    for dimension, themes in RADAR_THEMES.items() for theme in themes
}

NO_EVIDENCE_TEXT = "Nenhuma evidência encontrada nesta dimensão na pesquisa feita."
