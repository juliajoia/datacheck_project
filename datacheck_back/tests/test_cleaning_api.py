import csv
import io
import math
import uuid
from pathlib import Path

import openpyxl
import pandas as pd
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_engine
from app.models import Analysis
from app.services import data_store
from tests.test_sample_and_api import BASE_CONFIG, SAMPLE, expected_set, upload_sample

FAM = "Quantidade de famílias"


def run_sample(c, n="1", **extra):
    aid = upload_sample(c, n)["id"]
    r = c.post(f"/api/analyses/{aid}/run", json={"config": BASE_CONFIG, **extra})
    assert r.status_code == 200, r.text
    return aid


def req(base, action, **kw):
    return {"base_version": base, "action": action, **kw}


def summary(c, aid):
    return c.get(f"/api/analyses/{aid}/cleaning/summary").json()


def upload_csv(c, text, name="t.csv"):
    r = c.post("/api/analyses/upload", files={"file": (name, text.encode(), "text/csv")})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def raw_sample():
    return pd.read_csv(SAMPLE / "municipios_exemplo_1.csv", dtype=str, keep_default_na=False)


# ---------------------------------------------------------------- resumo e versão original

def test_resumo_inicial_e_versao_original_preservada(user_client):
    c = user_client
    aid = run_sample(c)
    s = summary(c, aid)
    n = len(expected_set("1"))
    assert s["data_available"] and s["current_version"] == 0 and s["workflow_status"] == "analyzed"
    assert s["counts"]["total"] == n == s["counts"]["pending"] and s["counts"]["corrected"] == 0 and s["counts"]["progress_pct"] == 0
    assert s["can_generate_eda"] is False and "Conclua o tratamento" in s["readiness_message"]
    # a versão 0 guardada é idêntica ao arquivo enviado
    with Session(get_engine()) as db:
        a = db.scalar(select(Analysis))
        v0 = data_store.load_version(f"versions/{a.id}/v0.csv")
    pd.testing.assert_frame_equal(v0[0], raw_sample())
    assert v0[1] == list(range(2, 102))


# ---------------------------------------------------------------- tipo de variável e recomendação

def test_opcoes_tipos_estatisticos_e_recomendacoes(user_client):
    c = user_client
    aid = run_sample(c)
    o = c.get(f"/api/analyses/{aid}/cleaning/options", params={"column": FAM}).json()
    types = {x["name"]: x["stat_type"] for x in o["columns"]}
    assert types == {"ID": "identifier", "Município": "nominal", "Latitude": "quant_continuous", "Longitude": "quant_continuous",
                     "Data do registro": "temporal", FAM: "quant_discrete", "Situação": "nominal"}
    assert o["profile"]["n_missing"] == 2 and o["recommendation"]["method"] in ("mean", "median", "mode", "group")
    assert {m["key"] for m in o["methods"] if m["available"]} >= {"mean", "median", "constant", "keep_missing"}
    ident = c.get(f"/api/analyses/{aid}/cleaning/options", params={"column": "ID"}).json()
    assert ident["recommendation"]["method"] == "none"   # ID sem ausentes
    mun = c.get(f"/api/analyses/{aid}/cleaning/options", params={"column": "Município"}).json()
    assert mun["recommendation"]["method"] == "not_informed"
    # alterar manualmente a classificação
    r = c.put(f"/api/analyses/{aid}/cleaning/column-types", json={"types": {"Situação": {"type": "ordinal", "order": ["Ativo", "Em análise", "Concluído", "Inativo"]}}})
    assert r.status_code == 200
    assert {x["name"]: x for x in r.json()["columns"]}["Situação"]["stat_type"] == "ordinal"
    assert c.put(f"/api/analyses/{aid}/cleaning/column-types", json={"types": {"Situação": {"type": "ordinal", "order": ["x"]}}}).status_code == 422


# ---------------------------------------------------------------- imputação: prévia, confirmação, versão, desfazer

def test_imputacao_previa_confirmacao_versao_e_desfazer(user_client):
    c = user_client
    aid = run_sample(c)
    df = raw_sample()
    nums = pd.to_numeric(df[FAM], errors="coerce").dropna()
    expected = str(int(math.floor(nums.median() + 0.5)))
    missing_rows = [i + 2 for i in df.index[df[FAM] == ""]]
    body = req(0, "impute", column=FAM, scope="column_all", params={"method": "median"})

    p = c.post(f"/api/analyses/{aid}/cleaning/preview", json=body).json()
    assert [(x["row"], x["old"], x["new"]) for x in p["changes"]] == [(r, "", expected) for r in missing_rows]
    assert p["n_changes"] == 2 and p["errors"] == [] and p["impact"]["after"]["pending"] == p["impact"]["before"]["pending"] - 2
    assert summary(c, aid)["current_version"] == 0                      # prévia não altera nada

    assert c.post(f"/api/analyses/{aid}/cleaning/apply", json=body).status_code == 422          # sem confirmação
    r = c.post(f"/api/analyses/{aid}/cleaning/apply", json={**body, "confirm": True})
    assert r.status_code == 200 and r.json()["version"] == 1
    s = summary(c, aid)
    assert s["current_version"] == 1 and s["counts"]["corrected"] == 2 and s["operations"]["imputed_values"] == 2
    assert s["workflow_status"] == "in_treatment" and s["counts"]["pending"] == len(expected_set("1")) - 2
    assert s["before"]["score"] == pytest.approx(s["before"]["score"]) and s["after"]["rows"] == 100

    # versão antiga continua intacta no armazenamento
    with Session(get_engine()) as db:
        a = db.scalar(select(Analysis))
        v0, v1 = (data_store.load_version(f"versions/{a.id}/v{n}.csv")[0] for n in (0, 1))
    pd.testing.assert_frame_equal(v0, df)
    assert (v1[FAM][[r - 2 for r in missing_rows]] == expected).all()

    assert c.post(f"/api/analyses/{aid}/cleaning/apply", json={**body, "confirm": True}).status_code == 409  # base_version velha
    hist = c.get(f"/api/analyses/{aid}/cleaning/history").json()
    op = hist[0]
    assert op["operation_type"] == "impute_missing" and op["method"] == "median" and op["column"] == FAM and op["user"]
    assert [x["value"] for x in op["original_values"]] == ["", ""] and [x["value"] for x in op["replacement_values"]] == [expected] * 2

    u = c.post(f"/api/analyses/{aid}/cleaning/undo").json()
    assert u["current_version"] == 0 and u["counts"]["pending"] == len(expected_set("1"))
    assert c.post(f"/api/analyses/{aid}/cleaning/undo").status_code == 409      # nada mais a desfazer
    assert c.post(f"/api/analyses/{aid}/versions/1/restore").json()["current_version"] == 1
    assert c.post(f"/api/analyses/{aid}/versions/0/restore").json()["current_version"] == 0   # restaurar original
    versions = c.get(f"/api/analyses/{aid}/versions").json()
    assert [v["version_number"] for v in versions] == [0, 1] and versions[0]["is_current"]
    types = [h["operation_type"] for h in c.get(f"/api/analyses/{aid}/cleaning/history").json()]
    assert types.count("undo") == 1 and types.count("restore") == 2


def test_imputacao_somente_registro_selecionado_e_validacoes(user_client):
    c = user_client
    aid = run_sample(c)
    rows = [i + 2 for i in raw_sample().index[raw_sample()[FAM] == ""]]
    p = c.post(f"/api/analyses/{aid}/cleaning/preview", json=req(0, "impute", column=FAM, rows=[rows[0]], params={"method": "mean"})).json()
    assert [x["row"] for x in p["changes"]] == [rows[0]]
    bad = c.post(f"/api/analyses/{aid}/cleaning/preview", json=req(0, "impute", column=FAM, rows=[2], params={"method": "mean"})).json()
    assert bad["errors"]
    # texto em coluna numérica exige confirmação explícita do risco
    body = req(0, "impute", column=FAM, scope="column_all", params={"method": "constant", "value": "Não Informado"})
    pv = c.post(f"/api/analyses/{aid}/cleaning/preview", json=body).json()
    assert [r["key"] for r in pv["requires"]] == ["type_change"]
    assert c.post(f"/api/analyses/{aid}/cleaning/apply", json={**body, "confirm": True}).status_code == 422
    assert c.post(f"/api/analyses/{aid}/cleaning/apply", json={**body, "confirm": True, "acknowledge": ["type_change"]}).status_code == 200


# ---------------------------------------------------------------- manter ausente, exceções e prontidão

def test_manter_ausente_exige_justificativa_em_qualitativas(user_client):
    c = user_client
    aid = run_sample(c)
    body = req(0, "impute", column="Município", scope="column_all", params={"method": "keep_missing"})
    assert c.post(f"/api/analyses/{aid}/cleaning/apply", json={**body, "confirm": True}).status_code == 422
    r = c.post(f"/api/analyses/{aid}/cleaning/apply", json={**body, "confirm": True, "justification": "Município desconhecido na fonte"})
    assert r.status_code == 200
    s = r.json()["summary"]
    assert s["counts"]["accepted"] == 6 and s["counts"]["pending"] == len(expected_set("1")) - 6
    h = c.get(f"/api/analyses/{aid}/cleaning/history").json()[0]
    assert h["justification"] == "Município desconhecido na fonte" and h["operation_type"] == "keep_missing"
    pending = c.get(f"/api/analyses/{aid}/cleaning/issues", params={"column": "Município"}).json()
    assert pending["total"] == 0
    assert c.get(f"/api/analyses/{aid}/cleaning/issues", params={"column": "Município", "include_accepted": True}).json()["total"] == 6


def test_base_pronta_para_eda_somente_sem_pendencias(user_client):
    c = user_client
    aid = upload_csv(c, "ID,Idade\n1,30\n2,31\n3,29\n4,\n5,33\n6,28\n")
    cfg = {"config": {"types": {"expected": {"Idade": "integer"}}, "duplicates": {"enabled": False}}}
    r = c.post(f"/api/analyses/{aid}/run", json=cfg).json()
    assert r["total_issues"] == 1 and r["workflow_status"] == "analyzed"
    assert summary(c, aid)["can_generate_eda"] is False
    out = c.post(f"/api/analyses/{aid}/cleaning/apply", json={**req(0, "impute", column="Idade", scope="column_all", params={"method": "median"}), "confirm": True}).json()
    s = out["summary"]
    assert s["counts"]["pending"] == 0 and s["can_generate_eda"] and s["workflow_status"] == "ready_for_eda"
    assert c.post(f"/api/analyses/{aid}/cleaning/validate").json()["workflow_status"] == "ready_for_eda"
    # base sem nenhuma inconsistência também já nasce pronta
    clean = upload_csv(c, "ID,Idade\n1,30\n2,31\n")
    assert c.post(f"/api/analyses/{clean}/run", json=cfg).json()["workflow_status"] == "ready_for_eda"


# ---------------------------------------------------------------- duplicidades

def test_duplicidades_grupos_remocao_e_numeracao_original(user_client):
    c = user_client
    aid = run_sample(c)
    d = c.get(f"/api/analyses/{aid}/cleaning/duplicates").json()
    assert d["total_groups"] == 4 and d["conflicting_groups"] == 0 and all(g["exact"] and len(g["rows"]) == 2 for g in d["groups"])
    dup_rows = sorted(r for g in d["groups"] for r in g["rows"])
    exp_dup = sorted(r for (r, col, cat) in expected_set("1") if cat == "duplicados")
    assert dup_rows == exp_dup
    body = req(0, "remove_duplicates", params={"strategy": "first"})
    pv = c.post(f"/api/analyses/{aid}/cleaning/preview", json=body).json()
    assert pv["n_removed"] == 4 and [r["key"] for r in pv["requires"]] == ["remove_rows"]
    assert c.post(f"/api/analyses/{aid}/cleaning/apply", json={**body, "confirm": True}).status_code == 422
    r = c.post(f"/api/analyses/{aid}/cleaning/apply", json={**body, "confirm": True, "acknowledge": ["remove_rows"]}).json()
    s = r["summary"]
    assert s["after"]["rows"] == 96 and s["operations"]["removed_rows"] == 4 and s["operations"]["duplicates_resolved"] == 4
    assert c.get(f"/api/analyses/{aid}/cleaning/duplicates").json()["total_groups"] == 0
    # as demais ocorrências mantêm o número da linha ORIGINAL do arquivo
    left = {(i["row"], i["column"], i["category"]) for i in c.get(f"/api/analyses/{aid}/cleaning/issues", params={"page_size": 500}).json()["items"]}
    assert left == {e for e in expected_set("1") if e[2] != "duplicados" or e[0] not in [x for x in exp_dup if x not in [min(g["rows"]) for g in d["groups"]]]} - {e for e in expected_set("1") if e[2] == "duplicados"}
    assert c.post(f"/api/analyses/{aid}/cleaning/undo").json()["after"]["rows"] == 100


def test_duplicidade_por_chave_com_conflito_e_mesclagem_assistida(user_client):
    c = user_client
    csv_text = "ID,Nome,Email,Telefone\n1,Ana,ana@x.com,\n1,Ana,,1111\n2,Bia,bia@x.com,2222\n2,Bia,bia@y.com,2222\n3,Caio,c@x.com,3333\n"
    aid = upload_csv(c, csv_text)
    c.post(f"/api/analyses/{aid}/run", json={"config": {"duplicates": {"key_columns": ["ID"]}, "missing": {"enabled": False}}})
    d = c.get(f"/api/analyses/{aid}/cleaning/duplicates").json()
    by_id = {g["id"]: g for g in d["groups"]}
    assert d["total_groups"] == 2 and d["conflicting_groups"] == 2
    g1 = by_id[2]
    assert g1["merge"]["conflicts"] == [] and g1["merge"]["values"]["Email"] == "ana@x.com" and g1["merge"]["values"]["Telefone"] == "1111"
    assert by_id[4]["merge"]["conflicts"] == ["Email"]
    # mesclagem com conflito exige escolha explícita
    bad = req(0, "merge_duplicates", params={"merges": [{"group": 4}]})
    assert c.post(f"/api/analyses/{aid}/cleaning/preview", json=bad).json()["errors"]
    body = req(0, "merge_duplicates", params={"merges": [{"group": 2}, {"group": 4, "values": {"Email": "bia@y.com"}}]})
    pv = c.post(f"/api/analyses/{aid}/cleaning/preview", json=body).json()
    assert pv["errors"] == [] and pv["n_removed"] == 2
    got = {(x["row"], x["column"], x["new"]) for x in pv["changes"]}
    assert got == {(2, "Telefone", "1111"), (4, "Email", "bia@y.com")}   # linha 2 ganha o telefone; linha 4 recebe o e-mail escolhido
    # a remoção por estratégia em grupos com conflito exige reconhecimento do conflito
    rm = req(0, "remove_duplicates", params={"strategy": "last"})
    assert {r["key"] for r in c.post(f"/api/analyses/{aid}/cleaning/preview", json=rm).json()["requires"]} == {"conflicting_groups", "remove_rows"}
    ok = c.post(f"/api/analyses/{aid}/cleaning/apply", json={**body, "confirm": True, "acknowledge": ["remove_rows"]})
    assert ok.status_code == 200
    with Session(get_engine()) as db:
        a = db.scalar(select(Analysis))
        df, rows = data_store.load_version(f"versions/{a.id}/v1.csv")
    assert rows == [2, 4, 6] and df.loc[0, "Telefone"] == "1111" and df.loc[1, "Email"] == "bia@y.com"


def test_manter_registro_mais_recente_e_mais_completo(user_client):
    c = user_client
    aid = upload_csv(c, "ID,Data,A,B\n1,2024-01-01,x,\n1,2024-03-01,x,y\n1,2024-02-01,,\n2,2024-01-01,p,q\n")
    c.post(f"/api/analyses/{aid}/run", json={"config": {"duplicates": {"key_columns": ["ID"]}, "missing": {"enabled": False}}})
    latest = c.post(f"/api/analyses/{aid}/cleaning/preview", json=req(0, "remove_duplicates", params={"strategy": "latest", "date_column": "Data"})).json()
    assert sorted(r["row"] for r in latest["removed"]) == [2, 4]            # mantém a linha 3 (2024-03-01)
    complete = c.post(f"/api/analyses/{aid}/cleaning/preview", json=req(0, "remove_duplicates", params={"strategy": "most_complete"})).json()
    assert sorted(r["row"] for r in complete["removed"]) == [2, 4]          # linha 3 é a mais completa
    manual = c.post(f"/api/analyses/{aid}/cleaning/preview", json=req(0, "remove_duplicates", params={"decisions": [{"group": 2, "keep": [2, 3]}]})).json()
    assert [r["row"] for r in manual["removed"]] == [4]


# ---------------------------------------------------------------- outras correções

def test_correcoes_pontuais_valores_extremos_e_coordenadas(user_client):
    c = user_client
    lines = ["ID,Lat,Lon,Valor,Data"] + [f"{i},{-10 - i * 0.1:.1f},{-50 - i * 0.1:.1f},{100 + i},2024-01-{i:02d}" for i in range(1, 13)]
    lines[3] = "3,-150.2,-10.3,103,2024-01-03"     # lat/lon trocadas (linha 4): a latitude fica inválida
    lines[5] = "5,-10.5,-50.5,5000,03/01/2024"      # extremo e data em outro formato (linha 6)
    aid = upload_csv(c, "\n".join(lines) + "\n")
    cfg = {"geo": {"lat_column": "Lat", "lon_column": "Lon"}, "types": {"expected": {"Valor": "integer"}},
           "dates": {"columns": ["Data"], "date_format": "%Y-%m-%d"}, "duplicates": {"enabled": False}, "missing": {"enabled": False}}
    r = c.post(f"/api/analyses/{aid}/run", json={"config": cfg}).json()
    assert {(i["row"], i["category"]) for i in c.get(f"/api/analyses/{aid}/issues").json()["items"]} == {(4, "geo_fora_limite"), (6, "data_invalida")}
    sug = c.get(f"/api/analyses/{aid}/cleaning/coordinate-suggestions").json()["suggestions"]
    assert [s["row"] for s in sug] == [4]
    sw = req(0, "swap_latlon", rows=[4], params={"lat_column": "Lat", "lon_column": "Lon"})
    assert {x["new"] for x in c.post(f"/api/analyses/{aid}/cleaning/preview", json=sw).json()["changes"]} == {"-10.3", "-150.2"}
    assert c.post(f"/api/analyses/{aid}/cleaning/apply", json={**sw, "confirm": True}).status_code == 422       # exige confirmação específica
    assert c.post(f"/api/analyses/{aid}/cleaning/apply", json={**sw, "confirm": True, "acknowledge": ["swap_confirmation"]}).json()["version"] == 1
    cd = req(1, "convert_date", rows=[6], column="Data", params={"source_format": "%d/%m/%Y", "target_format": "%Y-%m-%d"})
    ch = c.post(f"/api/analyses/{aid}/cleaning/preview", json=cd).json()["changes"]
    assert [(x["old"], x["new"]) for x in ch] == [("03/01/2024", "2024-01-03")]
    assert c.post(f"/api/analyses/{aid}/cleaning/apply", json={**cd, "confirm": True}).status_code == 200
    out = c.post(f"/api/analyses/{aid}/cleaning/outliers", json={"column": "Valor", "method": "iqr"}).json()
    assert [x["row"] for x in out["candidates"]] == [6] and "não são necessariamente erros" in out["note"] and "IQR" in out["justification"]
    z = c.post(f"/api/analyses/{aid}/cleaning/outliers", json={"column": "Valor", "method": "zscore", "params": {"threshold": 3}}).json()
    assert [x["row"] for x in z["candidates"]] == [6]
    lim = c.post(f"/api/analyses/{aid}/cleaning/outliers", json={"column": "Valor", "method": "limits", "params": {"min": 0, "max": 200}}).json()
    assert [x["row"] for x in lim["candidates"]] == [6]
    clip = req(2, "clip", rows=[6], column="Valor", params={"upper": 200})
    assert c.post(f"/api/analyses/{aid}/cleaning/apply", json={**clip, "confirm": True}).status_code == 422       # exige autorização explícita
    assert c.post(f"/api/analyses/{aid}/cleaning/apply", json={**clip, "confirm": True, "acknowledge": ["clip_authorization"]}).status_code == 200
    s = summary(c, aid)
    assert s["operations"]["manual_corrections"] == 3                      # registros corrigidos: 1 (troca) + 1 (data) + 1 (limite)
    assert c.post(f"/api/analyses/{aid}/cleaning/outliers", json={"column": "ID", "method": "iqr"}).status_code == 422   # identificador não é quantitativo


def test_remocao_de_registros_exige_confirmacao_e_nao_zera_a_base(user_client):
    c = user_client
    aid = upload_csv(c, "ID,V\n1,a\n2,b\n")
    c.post(f"/api/analyses/{aid}/run", json={"config": {"missing": {"enabled": True}}})
    body = req(0, "remove_rows", rows=[2, 3])
    assert c.post(f"/api/analyses/{aid}/cleaning/apply", json={**body, "confirm": True, "acknowledge": ["remove_rows"]}).status_code == 422
    one = req(0, "remove_rows", rows=[2])
    assert c.post(f"/api/analyses/{aid}/cleaning/apply", json={**one, "confirm": True, "acknowledge": ["remove_rows"]}).status_code == 200


# ---------------------------------------------------------------- exportação da base tratada

def test_exportacao_da_base_tratada_csv_e_xlsx(user_client):
    c = user_client
    aid = upload_csv(c, "Cod,Nome,Valor\n00123,=1+1,10\n00456,Ana,\n00789,Bia,30\n00999,Caio,50\n00111,Dani,40\n")
    c.post(f"/api/analyses/{aid}/run", json={"config": {"types": {"expected": {"Valor": "integer"}}, "duplicates": {"enabled": False}}})
    c.post(f"/api/analyses/{aid}/cleaning/apply", json={**req(0, "impute", column="Valor", scope="column_all", params={"method": "median"}), "confirm": True})
    base = f"/api/analyses/{aid}/cleaning/export"
    r = c.get(base, params={"format": "csv", "delimiter": "semicolon", "encoding": "utf-8"})
    rows = list(csv.reader(io.StringIO(r.content.decode("utf-8")), delimiter=";"))
    assert rows[0] == ["Cod", "Nome", "Valor"] and rows[1] == ["00123", "'=1+1", "10"] and rows[2] == ["00456", "Ana", "35"]   # mediana(10,30,40,50)=35
    assert c.get(base, params={"format": "csv", "delimiter": "x"}).status_code == 422
    x = c.get(base, params={"format": "xlsx"})
    wb = openpyxl.load_workbook(io.BytesIO(x.content))
    assert wb.sheetnames == ["Base tratada", "Resumo do tratamento"]
    ws = wb["Base tratada"]
    assert ws["A2"].value == "00123" and ws["C3"].value == 35 and ws["B2"].value == "'=1+1"      # identificador preservado como texto; número como número
    summ = {r[0].value: r[1].value for r in wb["Resumo do tratamento"].iter_rows()}
    assert summ["Valores imputados"] == 1 and summ["Versão exportada"] == "Tratada 1"
    assert openpyxl.load_workbook(io.BytesIO(c.get(base, params={"format": "xlsx", "include_summary": False}).content)).sheetnames == ["Base tratada"]


# ---------------------------------------------------------------- acesso, privacidade e retenção

def test_controle_de_acesso_nos_endpoints_de_tratamento(account_client, other_client):
    aid = run_sample(account_client)
    base = f"/api/analyses/{aid}"
    gets = ["/cleaning/summary", "/cleaning/options", "/cleaning/issues", "/cleaning/duplicates", "/cleaning/history",
            "/cleaning/coordinate-suggestions", "/cleaning/export", "/versions", "/versions/0"]
    for path in gets:
        assert account_client.get(base + path).status_code == 200, path
        assert other_client.get(base + path).status_code == 404, path
    body = req(0, "impute", column=FAM, scope="column_all", params={"method": "mean"})
    for path, payload in [("/cleaning/preview", body), ("/cleaning/apply", {**body, "confirm": True}), ("/cleaning/undo", None),
                          ("/cleaning/validate", None), ("/versions/0/restore", None), ("/cleaning/outliers", {"column": FAM})]:
        assert other_client.post(base + path, json=payload).status_code == 404, path


def test_sem_base_armazenada_nao_ha_tratamento_e_retencao(user_client, monkeypatch):
    c = user_client
    aid = run_sample(c, keep_data=False)
    assert c.get(f"/api/analyses/{aid}/cleaning/summary").json()["data_available"] is False
    assert c.get(f"/api/analyses/{aid}/cleaning/options").status_code == 409
    kept = run_sample(c)
    with Session(get_engine()) as db:
        a = db.get(Analysis, uuid.UUID(kept))
        from datetime import datetime, timedelta, timezone
        a.data_expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        db.commit()
        from app.services.analysis_service import cleanup_expired
        cleanup_expired(db)
    assert c.get(f"/api/analyses/{kept}/cleaning/summary").json()["data_available"] is False
    assert not (Path(data_store.root()) / "versions" / kept).exists()
    assert c.get(f"/api/analyses/{kept}").status_code == 200       # indicadores e ocorrências permanecem


def test_excluir_analise_remove_arquivos_armazenados(user_client):
    c = user_client
    aid = run_sample(c)
    folder = Path(data_store.root()) / "versions" / aid
    assert folder.exists()
    assert c.delete(f"/api/analyses/{aid}").status_code == 204
    assert not folder.exists()
