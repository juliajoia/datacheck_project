import pandas as pd
import pytest

from app.core.config import DEFAULT_MARKERS
from app.services.cleaning import imputation as imp
from app.services.cleaning.plan import TableCtx
from app.services.cleaning.variable_types import classify_all


def make(data: dict, decimal="auto", overrides=None) -> TableCtx:
    df = pd.DataFrame(data, dtype=str)
    return TableCtx(df, list(range(2, len(df) + 2)), list(DEFAULT_MARKERS), decimal,
                    {c["name"]: c for c in classify_all(df, DEFAULT_MARKERS, decimal, overrides)})


def new_values(plan):
    return {c.row: c.new for c in plan.changes}


# ---------------------------------------------------------------- tipo estatístico

def test_classificacao_estatistica_nao_usa_so_o_tipo_de_armazenamento():
    n = 40
    t = make({
        "ID": [str(1000 + i) for i in range(n)],
        "Código IBGE": ["1302603"] * 20 + ["3550308"] * 20,           # só dígitos, mas é código
        "CPF": [f"{i:011d}" for i in range(n)],
        "Idade": [str(20 + i % 30) for i in range(n)],               # inteiros -> discreta
        "Renda": [f"{1000 + i * 37.5:.2f}" for i in range(n)],       # decimais -> contínua
        "Situação": ["Ativo", "Inativo"] * 20,
        "Data": [f"2024-01-{1 + i % 28:02d}" for i in range(n)],
    })
    got = {k: v["stat_type"] for k, v in t.stat.items()}
    assert got == {"ID": "identifier", "Código IBGE": "identifier", "CPF": "identifier", "Idade": "quant_discrete",
                   "Renda": "quant_continuous", "Situação": "nominal", "Data": "temporal"}


def test_classificacao_manual_ordinal_e_coluna_vazia():
    t = make({"Nivel": ["Baixo", "Alto", "Médio", ""]}, overrides={"Nivel": {"type": "ordinal", "order": ["Baixo", "Médio", "Alto"]}})
    assert t.stat["Nivel"]["stat_type"] == "ordinal" and t.stat["Nivel"]["source"] == "manual"
    vazio = make({"x": ["", "N/A", "  "]})
    assert vazio.stat["x"]["n_valid"] == 0


# ---------------------------------------------------------------- imputação quantitativa

def test_media_mediana_moda_discreta_arredondam_para_inteiro():
    t = make({"q": ["10", "20", "30", "41", ""]})                    # média 25,25 -> 25
    assert new_values(imp.plan_impute(t, "q", "column_all", [], {"method": "mean"})) == {6: "25"}
    t = make({"q": ["1", "2", "3", "100", ""]})                      # mediana 2,5 -> 3 (meio para cima)
    assert new_values(imp.plan_impute(t, "q", "column_all", [], {"method": "median"})) == {6: "3"}
    t = make({"q": ["1", "2", "2", "3", ""]})
    assert new_values(imp.plan_impute(t, "q", "column_all", [], {"method": "mode"})) == {6: "2"}


def test_continua_preserva_casas_decimais_e_separador():
    t = make({"v": ["1,50", "2,50", "3,00", ""]})                    # média 2,3333 -> 2 casas
    assert new_values(imp.plan_impute(t, "v", "column_all", [], {"method": "mean"})) == {5: "2,33"}
    t = make({"v": ["1.50", "2.50", "3.00", ""]})
    assert new_values(imp.plan_impute(t, "v", "column_all", [], {"method": "median"})) == {5: "2.50"}


def test_moda_indisponivel_quando_nenhum_valor_se_repete():
    t = make({"q": ["1", "2", "3", "4", ""]})
    p = imp.plan_impute(t, "q", "column_all", [], {"method": "mode"})
    assert p.errors and "moda" in p.errors[0].lower()


def test_selecao_de_registros_especificos_e_validacao():
    t = make({"q": ["10", "", "30", "", "50"]})
    p = imp.plan_impute(t, "q", "selected", [3], {"method": "median"})
    assert new_values(p) == {3: "30"} and not p.errors
    bad = imp.plan_impute(t, "q", "selected", [2], {"method": "median"})     # linha 2 tem valor
    assert bad.errors
    assert imp.plan_impute(t, "q", "selected", [99], {"method": "median"}).errors


def test_coluna_totalmente_vazia_nao_permite_estatisticas():
    t = make({"q": ["", "", ""], "o": ["a", "b", "c"]})
    for m in ("mean", "median", "mode", "group", "interpolate"):
        assert imp.plan_impute(t, "q", "column_all", [], {"method": m, "group_by": ["o"]}).errors
    prof = imp.column_profile(t, "q")
    assert prof["n_valid"] == 0 and imp.recommend(prof, [], [])["method"] == "keep_missing"


def test_dominio_nao_negativo_e_valor_constante():
    t = make({"q": ["0", "1", "2", "3", ""]})
    p = imp.plan_impute(t, "q", "column_all", [], {"method": "constant", "value": "-5"})
    assert "domain" in p.requires
    p = imp.plan_impute(t, "q", "column_all", [], {"method": "constant", "value": "2,5"})
    assert p.errors and "inteiro" in p.errors[0]
    p = imp.plan_impute(t, "q", "column_all", [], {"method": "constant", "value": "Não Informado"})
    assert "type_change" in p.requires and "tipo de armazenamento" in " ".join(p.warnings)


def test_nao_informado_em_coluna_numerica_mantem_nulo_e_registra_decisao():
    t = make({"q": ["1", "2", "3", ""]})
    p = imp.plan_impute(t, "q", "column_all", [], {"method": "not_informed"})
    assert p.changes == [] and p.op_type == "keep_missing" and p.exceptions[0]["row"] == 5


# ---------------------------------------------------------------- por grupo e interpolação

def test_imputacao_por_grupo_com_grupo_insuficiente():
    t = make({"mun": ["A", "A", "A", "A", "B", "B", "C", "A", "B", "C"],
              "q":   ["10", "20", "30", "", "100", "200", "7", "", "", ""]})
    p = imp.plan_impute(t, "q", "column_all", [], {"method": "group", "group_by": ["mun"], "statistic": "median", "min_group_size": 2})
    assert new_values(p) == {5: "20", 9: "20", 10: "150"}              # A: mediana(10,20,30)=20 ; B: mediana(100,200)=150
    assert p.unresolved == [11] and "partial_application" in p.requires  # C tem 1 observação
    fb = imp.plan_impute(t, "q", "column_all", [], {"method": "group", "group_by": ["mun"], "statistic": "median",
                                                     "min_group_size": 2, "fallback": "constant", "fallback_value": "0"})
    assert new_values(fb)[11] == "0" and not fb.unresolved and "partial_application" not in fb.requires


def test_imputacao_por_multiplas_colunas():
    t = make({"mun": ["A", "A", "A", "A", "A", "A"], "ano": ["1", "1", "2", "2", "1", "2"], "q": ["10", "20", "5", "7", "", ""]})
    p = imp.plan_impute(t, "q", "column_all", [], {"method": "group", "group_by": ["mun", "ano"], "statistic": "mean", "min_group_size": 2})
    assert new_values(p) == {6: "15", 7: "6"}


def test_interpolacao_linear_exige_ordenacao_e_nao_extrapola():
    t = make({"data": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-06"],
              "v": ["", "10", "", "30", "", ""]})
    assert imp.plan_impute(t, "v", "column_all", [], {"method": "interpolate"}).errors      # sem coluna de ordenação
    p = imp.plan_impute(t, "v", "column_all", [], {"method": "interpolate", "order_by": "data"})
    assert new_values(p) == {4: "20"}                                  # 10 (dia 2) e 30 (dia 4) -> 20 no dia 3
    assert p.unresolved == [2, 6, 7] and "partial_application" in p.requires   # pontas da série: sem extrapolação


# ---------------------------------------------------------------- qualitativas

def test_qualitativas_moda_nao_informado_personalizado_e_ordem():
    t = make({"s": ["Ativo", "Ativo", "Inativo", ""]})
    assert new_values(imp.plan_impute(t, "s", "column_all", [], {"method": "mode"})) == {5: "Ativo"}
    assert new_values(imp.plan_impute(t, "s", "column_all", [], {"method": "not_informed"})) == {5: "Não Informado"}
    assert new_values(imp.plan_impute(t, "s", "column_all", [], {"method": "constant", "value": "Desconhecido"})) == {5: "Desconhecido"}
    t = make({"g": ["A", "A", "A", "B", "B", "B", "", ""], "s": ["x", "x", "y", "z", "z", "z", "", ""]})
    # moda por grupo; a linha 8 não tem grupo -> não resolvida
    t.df.loc[6, "g"], t.df.loc[7, "g"] = "A", ""
    p = imp.plan_impute(t, "s", "column_all", [], {"method": "group", "group_by": ["g"]})
    assert new_values(p) == {8: "x"} and p.unresolved == [9]
    o = make({"n": ["Baixo", "Alto", "Alto", "Baixo", ""]}, overrides={"n": {"type": "ordinal", "order": ["Baixo", "Médio", "Alto"]}})
    assert new_values(imp.plan_impute(o, "n", "column_all", [], {"method": "mode"})) == {6: "Baixo"}   # empate: ordem definida


# ---------------------------------------------------------------- recomendação

def _rec(t, col):
    prof = imp.column_profile(t, col)
    return imp.recommend(prof, imp.group_candidates(t, col), imp.order_columns(t, col)), prof


def test_recomendacao_simetrica_media_e_assimetrica_mediana():
    sym = [str(v) for v in list(range(30, 70)) * 2] + [""]   # idades repetidas (não é identificador)
    r, _ = _rec(make({"idade": sym}), "idade")
    assert r["method"] == "mean" and "simétrica" in r["justification"]
    skewed = ["1000"] * 20 + ["1200"] * 10 + ["1500"] * 5 + ["90000", "120000", "150000", ""]
    r, _ = _rec(make({"renda": skewed}), "renda")
    assert r["method"] == "median" and "mediana" in r["justification"].lower() and "extremo" in r["justification"]


def test_recomendacao_nominal_identificador_data_e_poucas_observacoes():
    r, _ = _rec(make({"situacao": ["Planejamento", "Andamento", "Concluído"] * 10 + [""]}), "situacao")
    assert r["method"] == "not_informed" and "classificação incorreta" in r["justification"]
    ids = [str(i) for i in range(100, 140)] + [""]
    r, _ = _rec(make({"ID": ids}), "ID")
    assert r["method"] == "manual_review" and "identificadores" in r["justification"]
    r, _ = _rec(make({"d": [f"2024-01-{i:02d}" for i in range(1, 12)] + [""]}), "d")
    assert r["method"] == "keep_missing"
    r, _ = _rec(make({"q": ["1", "2", ""]}), "q")
    assert r["method"] == "keep_missing" and "observaç" in r["justification"]


def test_recomendacao_por_grupo_quando_a_coluna_explica_a_variacao():
    mun = ["A"] * 15 + ["B"] * 15 + ["A", "B"]
    q = [str(10 + i % 3) for i in range(15)] + [str(100 + i % 3) for i in range(15)] + ["", ""]
    r, _ = _rec(make({"mun": mun, "q": q}), "q")
    assert r["method"] == "group" and r["group_by"] == ["mun"] and "η²" in r["justification"]


def test_alerta_de_vies_com_ausencia_elevada_e_sem_alteracao_automatica():
    q = [str(i) for i in range(10)] + [""] * 6
    t = make({"q": q})
    before = t.df.copy()
    r, prof = _rec(t, "q")
    assert any("viés" in w for w in r["warnings"]) and prof["pct_missing"] == 37.5
    imp.plan_impute(t, "q", "column_all", [], {"method": "mean"})
    assert t.df.equals(before)                                         # planejar nunca altera os dados
