import math

import numpy as np
import pandas as pd
import pytest

from app.core.config import DEFAULT_MARKERS
from app.schemas.eda import EdaConfig
from app.services.cleaning.variable_types import classify_all
from app.services.eda import engine as eng


def S(values):
    return pd.Series(values, dtype=float)


def test_estatisticas_descritivas_de_1_a_5():
    d = eng.descriptive(S([1, 2, 3, 4, 5]), 0, [10, 90])
    assert (d["n_valid"], d["mean"], d["median"], d["min"], d["max"], d["range"]) == (5, 3, 3, 1, 5, 4)
    assert d["variance"] == pytest.approx(2.5) and d["std"] == pytest.approx(math.sqrt(2.5), abs=1e-5)
    assert (d["q1"], d["q3"], d["iqr"]) == (2, 4, 2)
    assert d["cv"] == pytest.approx(math.sqrt(2.5) / 3, abs=1e-5)
    assert d["skewness"] == pytest.approx(0, abs=1e-9) and d["kurtosis"] == pytest.approx(-1.2, abs=1e-9)
    assert d["percentiles"] == {"p10": pytest.approx(1.4), "p90": pytest.approx(4.6)}
    assert d["mode"] is None   # nenhum valor se repete


def test_moda_e_assimetria_conhecidas():
    d = eng.descriptive(S([1, 2, 2, 3, 3, 3, 10]), 2, [50])
    assert d["mode"] == 3 and d["mode_count"] == 3 and d["n_missing"] == 2
    assert d["skewness"] > 1 and d["mean"] == pytest.approx(24 / 7, abs=1e-5)


def test_casos_extremos_vazia_constante_e_amostra_pequena():
    e = eng.descriptive(S([]), 4, [50])
    assert e["n_valid"] == 0 and e["warnings"] and "mean" not in e
    c = eng.descriptive(S([7, 7, 7, 7]), 0, [50])
    assert c["std"] == 0 and c["cv"] is None or c["cv"] == 0
    assert c["skewness"] is None and c["kurtosis"] is None and any("constante" in w for w in c["warnings"])
    one = eng.descriptive(S([5]), 0, [50])
    assert one["std"] is None and one["variance"] is None and one["skewness"] is None and any("Amostra pequena" in w for w in one["warnings"])
    z = eng.descriptive(S([-1, 0, 1]), 0, [50])
    assert z["mean"] == 0 and z["cv"] is None and any("Média igual a zero" in w for w in z["warnings"])
    inf = eng.descriptive(pd.Series([1.0, 2.0, float("inf")]).replace([np.inf], np.nan).dropna(), 0, [50])
    assert inf["mean"] == 1.5                      # valores não finitos nunca entram nos cálculos


def test_frequencias_com_ordem_ordinal():
    s = pd.Series(["Alto", "Baixo", "Baixo", "Médio", "", "Alto", "Baixo"])
    f = eng.frequencies(s, DEFAULT_MARKERS, ["Baixo", "Médio", "Alto"])
    assert [t["value"] for t in f["top"]] == ["Baixo", "Médio", "Alto"]
    assert [t["count"] for t in f["top"]] == [3, 1, 2] and [t["pct"] for t in f["top"]] == [50, pytest.approx(16.67), pytest.approx(33.33)]
    assert f["n_missing"] == 1 and f["n_unique"] == 3 and f["mode"] == "Baixo" and f["ordered"]
    n = eng.frequencies(pd.Series(["b", "a", "a", "b"]), DEFAULT_MARKERS, None)
    assert n["mode"] == "a"                        # empate: menor valor, determinístico


def test_correlacao_pearson_spearman_e_exclusoes():
    df = pd.DataFrame({"x": [1, 2, 3, 4, 5, 6], "y": [2, 4, 6, 8, 10, 12], "z": [1, 4, 9, 16, 25, 36], "k": [5, 5, 5, 5, 5, 5], "w": [1, 2, np.nan, np.nan, np.nan, np.nan]})
    p = eng.correlation(df, "pearson")
    assert p["columns"] == ["x", "y", "z"]
    assert {e["column"]: e["reason"] for e in p["excluded"]}.keys() == {"k", "w"}
    pairs = {(q["a"], q["b"]): q for q in p["pairs"]}
    assert pairs[("x", "y")]["r"] == 1 and pairs[("x", "y")]["strength"] == "muito forte" and pairs[("x", "y")]["direction"] == "positiva"
    assert pairs[("x", "z")]["r"] == pytest.approx(0.9786, abs=1e-3) and pairs[("x", "y")]["n"] == 6
    sp = eng.correlation(df[["x", "z"]], "spearman")
    assert sp["pairs"][0]["r"] == 1                # monotônica: Spearman = 1
    neg = eng.correlation(pd.DataFrame({"a": [1, 2, 3, 4], "b": [8, 6, 4, 2]}), "pearson")["pairs"][0]
    assert neg["r"] == -1 and neg["direction"] == "negativa"
    assert "causalidade" in p["warning"]
    assert eng.correlation(df[["x"]], "pearson")["pairs"] == []


def test_n_por_par_na_correlacao_com_ausentes():
    df = pd.DataFrame({"a": [1, 2, 3, 4, 5], "b": [2, 4, np.nan, 8, 10], "c": [1, np.nan, np.nan, 4, 5]})
    c = eng.correlation(df, "pearson")
    n = {(p["a"], p["b"]): p["n"] for p in c["pairs"]}
    assert n[("a", "b")] == 4 and n[("a", "c")] == 3 and n[("b", "c")] == 3


def test_distribuicao_histograma_boxplot_e_densidade():
    rng = np.random.default_rng(1)
    x = pd.Series(np.concatenate([rng.normal(50, 5, 200), [500.0]]))
    d = eng.distribution(x)
    assert sum(b["count"] for b in d["histogram"]["bins"]) == 201
    assert d["boxplot"]["n_outliers"] >= 1 and 500.0 in d["boxplot"]["outliers"] and d["boxplot"]["whisker_high"] < 500
    assert d["density"] is not None and len(d["density"]["x"]) == 80
    small = eng.distribution(S([1, 2, 2, 3]))
    assert small["histogram"]["discrete"] and small["density"] is None      # poucas observações: sem densidade
    assert eng.distribution(S([])) ["histogram"] is None
    const = eng.distribution(S([4, 4, 4]))
    assert const["histogram"]["bins"][0]["count"] == 3 and const["density"] is None


def test_valores_extremos_iqr():
    o = eng.outliers_block(S([10, 11, 12, 10, 11, 13, 12, 11, 10, 1000]))
    assert o["available"] and o["count"] == 1 and o["examples"] == [1000] and o["pct"] == 10
    assert not eng.outliers_block(S([5, 5, 5, 5, 5]))["available"]


def _build(data, cfg=None, overrides=None, treatment=None):
    df = pd.DataFrame(data, dtype=str)
    stat = {c["name"]: c for c in classify_all(df, DEFAULT_MARKERS, "auto", overrides)}
    return eng.build(df, stat, cfg or EdaConfig(), DEFAULT_MARKERS, "auto", treatment or {"imputed_values": 0}), stat


def test_build_respeita_o_tipo_estatistico_e_nao_correlaciona_identificadores():
    n = 30
    data = {"ID": [str(1000 + i) for i in range(n)], "Idade": [str(20 + i % 10) for i in range(n)], "Renda": [f"{1000 + (i % 7) * 10 + i}.5" for i in range(n)],
            "Situação": ["Ativo", "Inativo", "Ativo"] * 10, "Data": [f"2024-0{1 + i % 5}-{1 + i % 27:02d}" for i in range(n)]}
    r, stat = _build(data)
    assert stat["ID"]["stat_type"] == "identifier"
    assert [d["column"] for d in r["descriptive"]] == ["Idade", "Renda"]               # sem ID, sem nominal, sem data
    assert [f["column"] for f in r["frequencies"]] == ["Situação"]
    assert "ID" not in r["correlation"]["columns"] and set(r["correlation"]["columns"]) == {"Idade", "Renda"}
    assert r["temporal"]["available"] and r["temporal"]["date_column"] == "Data"
    assert sum(p["count"] for p in r["temporal"]["count_series"]) == n
    assert r["observations"] and any("Correlação não implica causalidade" in o for o in r["observations"])
    assert any("inferências" in x for x in r["limitations"])


def test_build_com_selecao_de_secoes_e_colunas():
    data = {"a": [str(i % 7) for i in range(20)], "b": [str((i % 7) * 2) for i in range(20)], "c": ["x", "y"] * 10}
    r, _ = _build(data, EdaConfig(sections=["descriptive"], columns=["a"]))
    assert [d["column"] for d in r["descriptive"]] == ["a"] and "frequencies" not in r and "correlation" not in r
    r, _ = _build({"a": ["1", "2", "3", "4"], "c": ["x", "y", "x", "y"]}, EdaConfig(sections=["correlation"]))
    assert "correlation" not in r and "quantitativas" in r["skipped"]["correlation"]


def test_temporal_agrupamentos_e_periodos_sem_registro():
    data = {"d": ["2024-01-05", "2024-01-20", "2024-03-02", "2024-03-03", "2024-03-04"], "v": ["10", "20", "30", "40", "50"]}
    r, _ = _build(data, EdaConfig(sections=["temporal"], temporal={"date_column": "d", "frequency": "M", "value_columns": ["v"]}))
    t = r["temporal"]
    assert [(p["period"], p["count"]) for p in t["count_series"]] == [("2024-01", 2), ("2024-02", 0), ("2024-03", 3)]
    assert t["gaps"] == ["2024-02"] and t["n_gaps"] == 1
    assert t["value_series"][0]["points"] == [{"period": "2024-01", "mean": 15.0, "n": 2}, {"period": "2024-03", "mean": 40.0, "n": 3}]
    y, _ = _build(data, EdaConfig(sections=["temporal"], temporal={"date_column": "d", "frequency": "Y"}))
    assert [(p["period"], p["count"]) for p in y["temporal"]["count_series"]] == [("2024", 5)]


def test_aplicabilidade_explica_o_que_nao_se_aplica():
    df = pd.DataFrame({"ID": [str(i) for i in range(30)], "Sit": ["a", "b"] * 15, "V": [str(i % 9) for i in range(30)]}, dtype=str)
    stat = {c["name"]: c for c in classify_all(df, DEFAULT_MARKERS, "auto", None)}
    a = eng.applicability(stat, 30)
    col = {c["name"]: c for c in a["columns"]}
    assert not col["Sit"]["descriptive"]["ok"] and "média não se aplica" in col["Sit"]["descriptive"]["reason"]
    assert not col["ID"]["correlation"]["ok"] and "Identificadores" in col["ID"]["correlation"]["reason"]
    assert col["V"]["descriptive"]["ok"] and not a["sections"]["correlation"]["ok"] and not a["sections"]["temporal"]["ok"]
