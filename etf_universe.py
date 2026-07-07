#!/usr/bin/env python3
"""
Universo de ETFs setoriais/tematicos dos EUA para o painel Setores.
42 ETFs: 11 setores GICS + subsetores (semicondutores, robotica, mineracao, etc.).
"""

ETF_SETORES = {
    "XLK": "Tecnologia da Informação",
    "XLF": "Financeiro",
    "XLV": "Saúde (Health Care)",
    "XLY": "Consumo Discricionário",
    "XLP": "Consumo Básico (Staples)",
    "XLE": "Energia",
    "XLI": "Industrial",
    "XLB": "Materiais Básicos",
    "XLU": "Utilities",
    "XLRE": "Imobiliário",
    "XLC": "Serviços de Comunicação",
    "SMH": "Semicondutores",
    "IGV": "Software",
    "FDN": "Internet",
    "HACK": "Cibersegurança",
    "BOTZ": "Robótica & Inteligência Artificial",
    "ROBO": "Robótica & Automação",
    "ARKK": "Inovação Disruptiva",
    "SKYY": "Cloud Computing",
    "BLOK": "Blockchain",
    "AIQ": "Inteligência Artificial",
    "IBB": "Biotecnologia",
    "XBI": "Biotech (equal weight)",
    "IHI": "Equipamentos Médicos",
    "XOP": "Exploração & Produção de Petróleo",
    "OIH": "Serviços de Petróleo",
    "TAN": "Energia Solar",
    "ICLN": "Energia Limpa",
    "URA": "Urânio & Nuclear",
    "LIT": "Lítio & Baterias",
    "XME": "Mineração & Metais",
    "GDX": "Mineradoras de Ouro",
    "SIL": "Mineradoras de Prata",
    "COPX": "Mineradoras de Cobre",
    "REMX": "Terras Raras & Metais Estratégicos",
    "ITA": "Aeroespacial & Defesa",
    "IYT": "Transporte",
    "JETS": "Companhias Aéreas",
    "XHB": "Construção Civil",
    "XRT": "Varejo",
    "KRE": "Bancos Regionais",
    "KWEB": "China Internet",
}

def get_etfs(): return list(ETF_SETORES.keys())
def setor_de(tk): return ETF_SETORES.get(tk.replace(".SA",""), "")