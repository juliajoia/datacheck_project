import pytest

from app.core.errors import DataCheckError
from app.schemas.validation import AnalysisConfig
from app.services.analyzer import run_analysis
from tests.helpers import TODAY, analyze, cats, table_from

OFF = dict(missing={"enabled": False}, duplicates={"enabled": False})


def test_ausentes_contagem_e_percentual():
    res, issues = analyze([["1", "a"], ["", "b"], ["N/A", " "], ["4", "d"]], ["x", "y"], duplicates={"enabled": False})
    assert cats(issues) == ["valores_ausentes"] * 3
    by_col = {r["column"]: r for r in res["metrics"]["missing_by_column"]}
    assert by_col["x"]["count"] == 2 and by_col["x"]["pct"] == 50.0
    assert by_col["y"]["count"] == 1
    assert [i.row for i in issues] == [3, 4, 4]  # cabeçalho = linha 1


def test_marcador_configuravel():
    _, issues = analyze([["-"], ["ok"]], ["x"], missing={"markers": ["-"]}, duplicates={"enabled": False})
    assert len(issues) == 1


def test_campo_obrigatorio_e_critico():
    _, issues = analyze([[""], ["a"]], ["x"], missing={"required_columns": ["x"]}, duplicates={"enabled": False})
    assert issues[0].severity == "critical" and "obrigatório" in issues[0].description


def test_duplicados_marca_todos_do_grupo():
    rows = [["1", "a"], ["2", "b"], ["1", "a"], ["1", "z"]]
    _, issues = analyze(rows, ["id", "v"], missing={"enabled": False})
    assert [(i.row, i.category) for i in issues] == [(2, "duplicados"), (4, "duplicados")]
    assert "2, 4" in issues[0].description
    _, issues = analyze(rows, ["id", "v"], missing={"enabled": False}, duplicates={"key_columns": ["id"]})
    assert [i.row for i in issues] == [2, 4, 5]


def test_tipos_inteiro_decimal_e_separador():
    rows = [["10"], ["doze"], ["1,5"], ["1.234,56"], ["abc"], ["inf"]]
    _, issues = analyze(rows, ["n"], types={"expected": {"n": "decimal"}}, **OFF)
    assert sorted(i.value for i in issues) == ["abc", "doze", "inf"]
    _, issues = analyze([["10"], ["1,5"], ["7.0"]], ["n"], types={"expected": {"n": "integer"}}, **OFF)
    assert sorted(i.value for i in issues) == ["1,5"]  # 7.0 é interpretável como inteiro


def test_separador_decimal_configurado():
    rows = [["12,5"], ["12.5"], ["1.234,5"]]
    _, issues = analyze(rows, ["n"], types={"expected": {"n": "decimal"}}, decimal_separator="comma", **OFF)
    assert [i.value for i in issues] == ["12.5"]
    _, issues = analyze(rows, ["n"], types={"expected": {"n": "decimal"}}, decimal_separator="dot", **OFF)
    assert sorted(i.value for i in issues) == ["1.234,5", "12,5"]


def test_tipo_data_e_texto():
    _, issues = analyze([["2024-01-31"], ["30/02/2024"]], ["d"], types={"expected": {"d": "date"}}, **OFF)
    assert [i.row for i in issues] == [3]
    _, issues = analyze([["Ana"], ["123"]], ["t"], types={"expected": {"t": "text"}}, **OFF)
    assert [i.row for i in issues] == [3]


def test_limites_confirmados_e_valores_suspeitos():
    _, issues = analyze([["5"], ["-1"], ["500"], ["abc"]], ["n"],
                        ranges={"limits": {"n": {"min": 0, "max": 100}}}, **OFF)
    assert cats(issues) == ["fora_limites"] * 2 and {i.severity for i in issues} == {"critical"}
    rows = [[str(v)] for v in [10, 11, 12, 10, 11, 13, 12, 11, 10, 1000]]
    _, issues = analyze(rows, ["n"], ranges={"suspect_columns": ["n"]}, **OFF)
    assert [(i.row, i.category, i.severity) for i in issues] == [(11, "valor_suspeito", "info")]


def test_geo():
    rows = [["-23.5", "-46.6"], ["91", "0"], ["0", "-181"], ["x", ""], ["-23.550", "10"]]
    _, issues = analyze(rows, ["lat", "lon"], geo={"lat_column": "lat", "lon_column": "lon"}, **OFF)
    assert sorted((i.row, i.column, i.category) for i in issues) == [
        (3, "lat", "geo_fora_limite"), (4, "lon", "geo_fora_limite"),
        (5, "lat", "geo_nao_numerica"), (5, "lon", "geo_ausente")]


def test_datas_formato_futuro_e_limites():
    rows = [["2024-02-30"], ["2030-01-01"], ["1980-05-05"], ["2024-05-05"]]
    _, issues = analyze(rows, ["d"], dates={"columns": ["d"], "flag_future": True, "min_date": "1990-01-01"}, **OFF)
    assert [(i.row, i.category) for i in issues] == [(2, "data_invalida"), (3, "data_futura"), (4, "data_fora_limite")]


def test_formato_de_data_configurado():
    _, issues = analyze([["31/12/2024"], ["2024-12-31"]], ["d"],
                        dates={"columns": ["d"], "date_format": "%d/%m/%Y"}, **OFF)
    assert [i.row for i in issues] == [3]


def test_ocorrencias_vs_linhas_afetadas_e_score():
    rows = [["", "abc"], ["ok", "5"], ["ok", "6"], ["ok", "7"]]  # linha 2 tem 2 problemas
    res, _ = analyze(rows, ["a", "n"], types={"expected": {"n": "decimal"}}, duplicates={"enabled": False})
    m = res["metrics"]
    assert m["total_occurrences"] == 2 and m["affected_rows"] == 1 and m["clean_rows_pct"] == 75.0
    assert res["score"]["value"] == 75.0  # 100 × (1 − 1/4)


def test_score_extremos_e_uniao_de_linhas():
    res, _ = analyze([["1"], ["2"]], ["n"], types={"expected": {"n": "decimal"}})
    assert res["score"]["value"] == 100.0
    res, _ = analyze([["a"], ["b"]], ["n"], types={"expected": {"n": "decimal"}}, ranges={"suspect_columns": []})
    assert res["score"]["value"] == 0.0
    from app.services.scoring import compute_score
    empty = compute_score(0, 0)
    assert empty["value"] is None and empty["label"] == "Indisponível"


def test_erros_de_configuracao():
    t = table_from([["1"]], ["a"])
    run = lambda cfg, tb=t: run_analysis(tb, AnalysisConfig(**cfg), filename="x", file_size=1, today=TODAY)
    with pytest.raises(DataCheckError, match="não existe"):
        run(dict(types={"expected": {"zzz": "decimal"}}))
    with pytest.raises(DataCheckError, match="Nenhuma verificação"):
        run(OFF)
    with pytest.raises(DataCheckError, match="mínimo é maior"):
        run(dict(ranges={"limits": {"a": {"min": 5, "max": 1}}}))
    with pytest.raises(DataCheckError, match="não contém registros"):
        run({}, table_from([], ["a"]))


def test_nao_altera_dados_originais():
    t = table_from([["  x ", ""], ["  x ", ""]], ["a", "b"])
    before = t.df.copy()
    run_analysis(t, AnalysisConfig(), filename="x", file_size=1, today=TODAY)
    assert t.df.equals(before)
