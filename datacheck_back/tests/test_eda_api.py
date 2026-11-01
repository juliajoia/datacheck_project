import io
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd
import pytest

from app.services import data_store
from tests.test_cleaning_api import FAM, req, run_sample, summary, upload_csv
from tests.test_sample_and_api import SAMPLE

IDADE = [20, 30, 40, 30, 20, 30, 40, 30, 20, 30, 50, 25]
RENDA = [1000.5, 1200.0, 1500.25, 1100.0, 900.0, 1300.5, 1600.0, 1250.0, 950.0, 1400.0, 5000.0, 1050.0]
SIT = ["Ativo", "Inativo", "Ativo", "Ativo", "Inativo", "Ativo", "Ativo", "Ativo", "Inativo", "Ativo", "Ativo", "Inativo"]
DATAS = ["2024-01-10", "2024-01-20", "2024-03-05", "2024-03-15", "2024-03-25", "2024-04-01", "2024-04-02", "2024-04-03", "2024-06-10", "2024-06-11", "2024-06-12", "2024-06-13"]
CLEAN_CSV = "ID,Idade,Renda,Situação,Data\n" + "\n".join(f"{100 + i},{IDADE[i]},{RENDA[i]},{SIT[i]},{DATAS[i]}" for i in range(12)) + "\n"
CFG = {"config": {"types": {"expected": {"Idade": "integer", "Renda": "decimal"}}, "dates": {"columns": ["Data"]}, "duplicates": {"enabled": False}}}


def ready_analysis(c):
    aid = upload_csv(c, CLEAN_CSV)
    r = c.post(f"/api/analyses/{aid}/run", json=CFG).json()
    assert r["total_issues"] == 0 and r["workflow_status"] == "ready_for_eda"
    return aid


def wait(c, rid):
    """Consulta o status como a interface: o POST responde 'queued' e o processamento corre em segundo plano."""
    for _ in range(50):
        d = c.get(f"/api/eda/{rid}").json()
        if d["status"] in ("completed", "failed"):
            return d
    raise AssertionError("EDA não terminou")


def generate(c, aid, **body):
    r = c.post(f"/api/analyses/{aid}/eda/generate", json={"report_name": "Teste EDA", **body})
    assert r.status_code == 202, r.text
    assert r.json()["status"] == "queued"
    return wait(c, r.json()["id"])


def test_eda_bloqueada_com_pendencias(user_client):
    c = user_client
    aid = run_sample(c)
    o = c.get(f"/api/analyses/{aid}/eda/options").json()
    assert o["readiness"]["ready"] is False and "Conclua o tratamento" in o["message"]
    r = c.post(f"/api/analyses/{aid}/eda/generate", json={"report_name": "x"})
    assert r.status_code == 409 and "Conclua o tratamento" in r.json()["detail"]
    assert c.get("/api/eda").json() == []


def test_eda_com_estatisticas_corretas_e_arquivos(user_client):
    c = user_client
    aid = ready_analysis(c)
    rep = generate(c, aid, percentiles=[10, 50, 90])
    assert rep["status"] == "completed" and rep["version_number"] == 0 and rep["total_rows"] == 12   # tarefa em segundo plano já executou
    d = c.get(f"/api/eda/{rep['id']}").json()
    st = d["summary_statistics"]
    idade, renda = pd.Series(IDADE, dtype=float), pd.Series(RENDA)
    desc = {x["column"]: x for x in st["descriptive"]}
    assert set(desc) == {"Idade", "Renda"}                                   # sem ID, sem nominal, sem data
    assert desc["Idade"]["mean"] == pytest.approx(idade.mean()) and desc["Idade"]["median"] == idade.median() and desc["Idade"]["mode"] == 30
    assert desc["Idade"]["std"] == pytest.approx(idade.std(), abs=1e-5) and desc["Idade"]["iqr"] == pytest.approx(idade.quantile(.75) - idade.quantile(.25))
    assert desc["Renda"]["skewness"] == pytest.approx(renda.skew(), abs=1e-5) and desc["Renda"]["kurtosis"] == pytest.approx(renda.kurt(), abs=1e-5)
    assert desc["Renda"]["percentiles"]["p90"] == pytest.approx(renda.quantile(.9), abs=1e-5)
    fr = {x["column"]: x for x in st["frequencies"]}["Situação"]
    assert [(t["value"], t["count"]) for t in fr["top"]] == [("Ativo", 8), ("Inativo", 4)] and fr["mode"] == "Ativo"
    corr = st["correlation"]
    assert corr["columns"] == ["Idade", "Renda"] and corr["pairs"][0]["r"] == pytest.approx(idade.corr(renda), abs=1e-4) and corr["pairs"][0]["n"] == 12
    assert "ID" not in corr["columns"]
    assert sum(p["count"] for p in st["temporal"]["count_series"]) == 12 and "2024-02" in st["temporal"]["gaps"] and "2024-05" in st["temporal"]["gaps"]
    assert any(o["column"] == "Renda" and o["count"] >= 1 for o in st["outliers"])       # renda 5000 é atípica pelo IQR
    assert st["treatment"]["version_label"] == "Original" and st["treatment"]["imputed_values"] == 0
    assert any("Correlação não implica causalidade" in x for x in st["observations"])

    pdf = c.get(f"/api/eda/{rep['id']}/download", params={"format": "pdf"})
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF") and len(pdf.content) > 20_000
    wb = openpyxl.load_workbook(io.BytesIO(c.get(f"/api/eda/{rep['id']}/download", params={"format": "xlsx"}).content))
    assert wb.sheetnames[:5] == ["Resumo", "Estatísticas descritivas", "Frequências", "Correlações", "Valores extremos"] and "Informações do tratamento" in wb.sheetnames
    ws = wb["Estatísticas descritivas"]
    header = [x.value for x in ws[1]]
    assert ws.cell(2, 1).value == "Idade" and ws.cell(2, header.index("Média") + 1).value == pytest.approx(idade.mean())
    assert c.get(f"/api/eda/{rep['id']}/download", params={"format": "docx"}).status_code == 422
    # a EDA aparece na sua própria lista, separada da lista de análises
    assert [x["id"] for x in c.get("/api/eda").json()] == [rep["id"]] and c.get("/api/analyses").json()["total"] == 1
    assert c.get(f"/api/analyses/{aid}").json()["workflow_status"] == "eda_generated"


def test_selecao_de_secoes_colunas_e_spearman(user_client):
    c = user_client
    aid = ready_analysis(c)
    rep = generate(c, aid, sections=["descriptive", "correlation"], columns=["Idade", "Renda"], correlation_method="spearman")
    st = c.get(f"/api/eda/{rep['id']}").json()["summary_statistics"]
    assert "frequencies" not in st and "temporal" not in st and st["correlation"]["method"] == "spearman"
    spearman = pd.Series(IDADE).corr(pd.Series(RENDA), method="spearman")
    assert st["correlation"]["pairs"][0]["r"] == pytest.approx(spearman, abs=1e-4)
    wb = openpyxl.load_workbook(io.BytesIO(c.get(f"/api/eda/{rep['id']}/download", params={"format": "xlsx"}).content))
    assert "Frequências" not in wb.sheetnames
    assert c.post(f"/api/analyses/{aid}/eda/generate", json={"report_name": "x", "sections": ["inexistente"]}).status_code == 422
    assert c.post(f"/api/analyses/{aid}/eda/generate", json={"report_name": "x", "columns": ["nao_existe"]}).status_code == 422
    opts = c.get(f"/api/analyses/{aid}/eda/options").json()
    cols = {x["name"]: x for x in opts["columns"]}
    assert not cols["Situação"]["descriptive"]["ok"] and "média não se aplica" in cols["Situação"]["descriptive"]["reason"]
    assert not cols["ID"]["correlation"]["ok"] and opts["readiness"]["ready"] and opts["temporal_columns"] == ["Data"]


def test_eda_associada_a_versao_e_nao_muda_silenciosamente(user_client):
    c = user_client
    aid = ready_analysis(c)
    first = generate(c, aid, report_name="EDA v0")
    stats0 = c.get(f"/api/eda/{first['id']}").json()["summary_statistics"]
    # altera os dados depois (cria a versão 1): corrige a renda extrema manualmente
    fix = {**req(0, "set_value", cells=[{"row": 12, "column": "Renda", "value": "1500"}]), "confirm": True}
    assert c.post(f"/api/analyses/{aid}/cleaning/apply", json=fix).status_code == 200
    assert summary(c, aid)["current_version"] == 1 and c.get(f"/api/analyses/{aid}").json()["workflow_status"] == "ready_for_eda"
    # o relatório antigo continua idêntico e ligado à versão original
    again = c.get(f"/api/eda/{first['id']}").json()
    assert again["version_number"] == 0 and again["version_label"] == "Original" and again["summary_statistics"] == stats0
    second = generate(c, aid, report_name="EDA v1")
    assert second["version_number"] == 1 and second["version_label"] == "Tratada 1"
    renda1 = {x["column"]: x for x in c.get(f"/api/eda/{second['id']}").json()["summary_statistics"]["descriptive"]}["Renda"]
    renda0 = {x["column"]: x for x in stats0["descriptive"]}["Renda"]
    assert renda1["max"] == 1600 and renda0["max"] == 5000
    # é possível gerar EDA de uma versão anterior explicitamente
    old = generate(c, aid, version_number=0)
    assert old["version_number"] == 0
    assert {r["version_number"] for r in c.get("/api/eda").json()} == {0, 1}
    # regenerar mantém versão e configuração
    again2 = c.post(f"/api/eda/{first['id']}/regenerate")
    assert again2.status_code == 202 and again2.json()["status"] == "queued"
    done = wait(c, first["id"])
    assert done["version_number"] == 0 and done["status"] == "completed" and done["id"] == first["id"]


def test_eda_apos_tratamento_real_da_base_de_exemplo(user_client):
    """Base de exemplo: aceita todas as pendências com justificativa → pronta → EDA com estatísticas conferidas contra o CSV."""
    c = user_client
    aid = run_sample(c)
    cats = [x["category"] for x in summary(c, aid)["by_category"]]
    version = 0
    for cat in cats:
        body = req(version, "accept_exception", params={"category": cat}, justification="Aceito para o teste")
        r = c.post(f"/api/analyses/{aid}/cleaning/apply", json={**body, "confirm": True}).json()
        version = r["version"]
    s = summary(c, aid)
    assert s["counts"]["pending"] == 0 and s["can_generate_eda"] and s["workflow_status"] == "ready_for_eda"
    rep = generate(c, aid, report_name="Municípios")
    assert rep["status"] == "completed"
    st = c.get(f"/api/eda/{rep['id']}").json()["summary_statistics"]
    raw = pd.read_csv(SAMPLE / "municipios_exemplo_1.csv", dtype=str, keep_default_na=False)
    fam = pd.to_numeric(raw[FAM].str.replace(",", "."), errors="coerce").dropna()
    d = {x["column"]: x for x in st["descriptive"]}[FAM]
    assert d["n_valid"] == len(fam) and d["mean"] == pytest.approx(fam.mean(), rel=1e-5) and d["median"] == fam.median() and d["max"] == 9999999
    assert d["skewness"] > 5 and any("valor(es) além" in o or "assimétrica" in o for o in st["observations"])
    assert "ID" not in [x["column"] for x in st["descriptive"]] and st["treatment"]["exceptions_accepted"] == s["counts"]["accepted"]
    assert c.get(f"/api/eda/{rep['id']}/download", params={"format": "pdf"}).content.startswith(b"%PDF")


def test_acesso_e_exclusao_de_relatorios_eda(account_client, other_client):
    c = account_client
    aid = ready_analysis(c)
    rep = generate(c, aid)
    rid = rep["id"]
    assert other_client.get("/api/eda").json() == []
    for method, url in [("get", f"/api/eda/{rid}"), ("get", f"/api/eda/{rid}/download"), ("delete", f"/api/eda/{rid}"), ("post", f"/api/eda/{rid}/regenerate"),
                        ("get", f"/api/analyses/{aid}/eda/options")]:
        assert getattr(other_client, method)(url).status_code == 404, url
    assert other_client.post(f"/api/analyses/{aid}/eda/generate", json={"report_name": "x"}).status_code == 404
    files = [Path(data_store.root()) / f"reports/{rid}.pdf", Path(data_store.root()) / f"reports/{rid}.xlsx"]
    assert all(f.exists() for f in files)
    assert c.delete(f"/api/eda/{rid}").status_code == 204
    assert not any(f.exists() for f in files) and c.get(f"/api/eda/{rid}").status_code == 404
    assert c.get(f"/api/analyses/{aid}").json()["workflow_status"] == "ready_for_eda"      # sem EDA gerada para a versão
    rep2 = generate(c, aid)
    c.delete(f"/api/analyses/{aid}")                                                        # excluir a análise remove os relatórios
    assert not (Path(data_store.root()) / f"reports/{rep2['id']}.pdf").exists() and c.get("/api/eda").json() == []


def test_eda_falha_registra_status_sem_expor_dados(user_client, monkeypatch):
    from app.services.eda import engine
    monkeypatch.setattr(engine, "build", lambda *a, **k: (_ for _ in ()).throw(ValueError("segredo: 123.456.789-00")))
    c = user_client
    aid = ready_analysis(c)
    rep = generate(c, aid)
    assert rep["status"] == "failed" and "segredo" not in str(rep) and rep["error_message"].startswith("Não foi possível")
    assert c.get(f"/api/eda/{rep['id']}/download").status_code == 409
