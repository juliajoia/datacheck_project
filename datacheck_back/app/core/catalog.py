"""Catálogo de verificações, categorias de inconsistência e severidades."""

SEVERITY_LABELS = {"critical": "Crítica", "warning": "Aviso", "info": "Informativa"}
SEVERITY_RANK = {"critical": 0, "warning": 1, "info": 2}

CATEGORIES = {
    "valores_ausentes": {"label": "Valor ausente", "rule": "missing"},
    "duplicados": {"label": "Registro duplicado", "rule": "duplicates"},
    "tipo_incompativel": {"label": "Tipo incompatível", "rule": "types"},
    "fora_limites": {"label": "Fora dos limites", "rule": "ranges"},
    "valor_suspeito": {"label": "Valor suspeito", "rule": "ranges"},
    "geo_ausente": {"label": "Coordenada ausente", "rule": "geo"},
    "geo_nao_numerica": {"label": "Coordenada não numérica", "rule": "geo"},
    "geo_fora_limite": {"label": "Coordenada fora do intervalo", "rule": "geo"},
    "data_invalida": {"label": "Data inválida", "rule": "dates"},
    "data_futura": {"label": "Data futura", "rule": "dates"},
    "data_fora_limite": {"label": "Data fora do limite", "rule": "dates"},
}

RULES_INFO = [
    {
        "code": "missing",
        "letter": "A",
        "name": "Valores ausentes",
        "description": (
            "Encontra células vazias, só com espaços em branco ou preenchidas com "
            "marcadores de ausência configuráveis (ex.: N/A). Mostra quantidade e "
            "percentual por coluna."
        ),
    },
    {
        "code": "duplicates",
        "letter": "B",
        "name": "Registros duplicados",
        "description": (
            "Encontra linhas repetidas. Por padrão compara a linha inteira; você pode "
            "escolher colunas-chave (ex.: ID) para detectar duplicidade de identificador. "
            "A primeira ocorrência é preservada e as repetições são sinalizadas."
        ),
    },
    {
        "code": "types",
        "letter": "C",
        "name": "Tipos e formatos",
        "description": (
            "Você indica quais colunas devem conter número, data ou texto, e o DataCheck "
            "sinaliza os valores que não se encaixam (ex.: «doze» em uma coluna numérica)."
        ),
    },
    {
        "code": "ranges",
        "letter": "D",
        "name": "Valores fora dos limites",
        "description": (
            "Compara colunas numéricas com mínimo e/ou máximo definidos por você: violações são "
            "inconsistências confirmadas por regra explícita. Opcionalmente aponta valores "
            "estatisticamente suspeitos (muito distantes dos demais), que são apenas "
            "alertas, não erros confirmados."
        ),
    },
    {
        "code": "geo",
        "letter": "E",
        "name": "Coordenadas geográficas",
        "description": (
            "Verifica se latitude está entre -90 e 90 e longitude entre -180 e 180, e "
            "sinaliza coordenadas ausentes ou não numéricas. Regras por região geográfica "
            "poderão ser adicionadas no futuro."
        ),
    },
    {
        "code": "dates",
        "letter": "F",
        "name": "Validação de datas",
        "description": (
            "Identifica datas inexistentes (ex.: 30/02) ou fora do formato configurado e "
            "permite sinalizar datas futuras ou fora de um período definido."
        ),
    },
]
RULE_NAMES = {r["code"]: r["name"] for r in RULES_INFO}


def category_label(code: str) -> str:
    return CATEGORIES.get(code, {}).get("label", code)
