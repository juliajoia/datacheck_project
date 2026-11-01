import csv
import io
from pathlib import Path

import openpyxl
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_engine
from app.models import AnalysisFeedback, User, ValidationIssue
from app.schemas.validation import AnalysisConfig
from app.services import temp_storage
from app.services.analyzer import run_analysis
from app.services.file_reader import read_table
from tests.helpers import TODAY

SAMPLE = Path(__file__).parent.parent / "data" / "sample"
BASE_CONFIG = {
    "types": {"expected": {"Quantidade de famílias": "integer"}},
    "ranges": {"limits": {"Quantidade de famílias": {"min": 0, "max": 100000}}},
    "geo": {"lat_column": "Latitude", "lon_column": "Longitude"},
    "dates": {"columns": ["Data do registro"], "flag_future": True, "min_date": "1990-01-01"},
}
CONFIGS = {
    "1": BASE_CONFIG,
    "2": {**BASE_CONFIG, "decimal_separator": "comma",
          "dates": {**BASE_CONFIG["dates"], "date_format": "%d/%m/%Y"}},
}


def expected_set(n):
    with open(SAMPLE / f"gabarito_erros_{n}.csv", encoding="utf-8") as f:
        return {(int(r["linha_original"]), r["coluna"], cat)
                for r in csv.DictReader(f) for cat in r["categorias_esperadas"].split(";")}


@pytest.mark.parametrize("n", ["1", "2"])
def test_bases_de_exemplo_detectam_exatamente_o_gabarito(n):
    table = read_table((SAMPLE / f"municipios_exemplo_{n}.csv").read_bytes(), "m.csv")
    _, issues = run_analysis(table, AnalysisConfig(**CONFIGS[n]), today=TODAY)
    detected = {(i.row, i.column, i.category) for i in issues}
    expected = expected_set(n)
    assert detected == expected, (detected - expected, expected - detected)


def upload_sample(c, n="1"):
    r = c.post(f"/api/analyses/upload-sample/{n}")
    assert r.status_code == 201, r.text
    return r.json()


def test_fluxo_completo(user_client):
    c = user_client
    prof = upload_sample(c)
    assert prof["n_rows"] == 100 and prof["n_cols"] == 7 and len(prof["preview"]["rows"]) == 10
    assert prof["suggested_config"]["lat_column"] == "Latitude"
    aid = prof["id"]
    assert temp_storage.load(__import__("uuid").UUID(aid)) is not None  # arquivo temporário existe

    r = c.post(f"/api/analyses/{aid}/run", json={"config": BASE_CONFIG})
    assert r.status_code == 200, r.text
    res = r.json()
    exp = expected_set("1")
    assert res["status"] == "completed" and res["total_issues"] == len(exp)
    assert res["affected_rows"] == len({e[0] for e in exp})
    assert res["quality_score"] == round(100 * (1 - res["affected_rows"] / 100), 1)
    assert temp_storage.load(__import__("uuid").UUID(aid)) is None  # temporário removido após a análise

    assert c.post(f"/api/analyses/{aid}/run", json={"config": BASE_CONFIG}).status_code == 409  # sem reenvio

    page = c.get(f"/api/analyses/{aid}/issues", params={"severity": "critical", "page_size": 5, "sort_by": "severity"}).json()
    assert page["total"] > 5 and len(page["items"]) == 5
    found = c.get(f"/api/analyses/{aid}/issues", params={"q": "doze"}).json()
    assert [i["value"] for i in found["items"]] == ["doze"]
    only_dup = c.get(f"/api/analyses/{aid}/issues", params={"category": "duplicados"}).json()
    assert only_dup["total"] == 8  # 4 grupos × (original + cópia)
    assert c.get(f"/api/analyses/{aid}/issues", params={"q": "100%"}).json()["total"] == 0  # % não vira curinga

    r = c.get(f"/api/analyses/{aid}/export", params={"format": "xlsx"})
    wb = openpyxl.load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames == ["Identificação", "Resumo da base", "Indicadores", "Gráficos", "Inconsistências", "Recomendações"]
    assert wb["Inconsistências"].max_row == len(exp) + 1
    assert c.get(f"/api/analyses/{aid}/export", params={"format": "csv"}).status_code == 200
    assert c.get(f"/api/analyses/{aid}/export", params={"format": "pdf"}).status_code == 422

    # tabela de inconsistências: mesmas colunas da visão detalhada
    t = c.get(f"/api/analyses/{aid}/export/issues", params={"format": "xlsx"})
    ws = openpyxl.load_workbook(io.BytesIO(t.content)).active
    assert [x.value for x in ws[1]] == ["Linha", "Coluna", "Valor original", "Tipo", "Severidade", "Descrição", "Sugestão de revisão"]
    assert ws.max_row == len(exp) + 1
    pdf = c.get(f"/api/analyses/{aid}/export/issues", params={"format": "pdf"})
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf" and pdf.content.startswith(b"%PDF")
    assert c.get(f"/api/analyses/{aid}/export/issues", params={"format": "csv"}).status_code == 422

    d = c.get("/api/dashboard/summary").json()
    assert d["total_analyses"] == 1 and d["total_issues"] == len(exp) and d["average_score"] == res["quality_score"]
    ch = c.get("/api/dashboard/charts").json()
    assert sum(x["count"] for x in ch["issues_by_category"]) == len(exp)
    assert sum(x["count"] for x in ch["analyses_over_time"]) == 1

    assert c.get("/api/analyses").json()["total"] == 1
    assert c.delete(f"/api/analyses/{aid}").status_code == 204
    assert c.get(f"/api/analyses/{aid}").status_code == 404
    with Session(get_engine()) as db:
        assert db.scalars(select(ValidationIssue)).first() is None  # exclusão em cascata


def test_valores_nao_armazenados_quando_desativado(user_client):
    aid = upload_sample(user_client)["id"]
    user_client.post(f"/api/analyses/{aid}/run", json={"config": BASE_CONFIG, "store_values": False})
    items = user_client.get(f"/api/analyses/{aid}/issues").json()["items"]
    assert {i["value"] for i in items} == {"(não armazenado)"}


def test_visitante_usa_o_app_sem_login(client):
    for _ in range(3):
        assert client.get("/api/analyses").status_code == 200
    assert client.get("/api/auth/me").status_code == 401  # visitante não tem sessão
    with Session(get_engine()) as db:
        assert [u.email for u in db.scalars(select(User))] == ["local@datacheck.local"]
    aid = upload_sample(client)["id"]
    assert client.post(f"/api/analyses/{aid}/run", json={"config": BASE_CONFIG}).status_code == 200


def test_autenticacao(client):
    r = client.post("/api/auth/register", json={"name": "Ana", "email": "ana@example.com", "password": "senha-segura-1"})
    assert r.status_code == 201
    assert client.get("/api/auth/me").json()["email"] == "ana@example.com"
    r = client.post("/api/auth/register", json={"name": "Xavier", "email": "ANA@example.com", "password": "outra-senha-1"})
    assert r.status_code == 409  # e-mail único, sem diferenciar caixa
    assert client.post("/api/auth/register", json={"name": "Ana", "email": "b@example.com", "password": "curta"}).status_code == 422
    assert client.post("/api/auth/register", json={"name": "Hack", "email": "local@datacheck.local", "password": "senha-segura-1"}).status_code in (409, 422)
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401
    assert client.post("/api/auth/login", json={"email": "ana@example.com", "password": "errada-123"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "local@datacheck.local", "password": "!"}).status_code in (401, 422)
    r = client.post("/api/auth/login", json={"email": "ana@example.com", "password": "senha-segura-1"})
    assert r.status_code == 200 and client.get("/api/auth/me").status_code == 200
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    with Session(get_engine()) as db:
        assert db.scalar(select(User.password_hash).where(User.email == "ana@example.com")).startswith("$argon2")


def test_isolamento_entre_conta_outra_conta_e_visitante(account_client, other_client):
    from fastapi.testclient import TestClient
    from app.main import app
    guest = TestClient(app)
    aid = upload_sample(account_client)["id"]
    account_client.post(f"/api/analyses/{aid}/run", json={"config": BASE_CONFIG})
    for who in (other_client, guest):
        for method, url in [("get", f"/api/analyses/{aid}"), ("get", f"/api/analyses/{aid}/issues"),
                            ("get", f"/api/analyses/{aid}/export"), ("get", f"/api/analyses/{aid}/export/issues"), ("get", f"/api/analyses/{aid}/data"),
                            ("get", f"/api/analyses/{aid}/profile"),
                            ("delete", f"/api/analyses/{aid}")]:
            assert getattr(who, method)(url).status_code == 404, url
        assert who.post(f"/api/analyses/{aid}/run", json={"config": BASE_CONFIG}).status_code == 404
        assert who.post(f"/api/analyses/{aid}/feedback", json={
            "usability_rating": 5, "usefulness_rating": 5, "would_use_again": "sim"}).status_code == 404
        assert who.get("/api/analyses").json()["total"] == 0
        assert who.get("/api/dashboard/summary").json()["total_analyses"] == 0
    assert account_client.get(f"/api/analyses/{aid}").status_code == 200
    # análises de visitante não aparecem para quem tem conta
    gid = upload_sample(guest)["id"]
    guest.post(f"/api/analyses/{gid}/run", json={"config": BASE_CONFIG})
    assert account_client.get(f"/api/analyses/{gid}").status_code == 404


def test_erros_amigaveis_no_upload(user_client):
    c = user_client
    r = c.post("/api/analyses/upload", files={"file": ("vazio.csv", b"", "text/csv")})
    assert r.status_code == 422 and "vazio" in r.json()["detail"]
    assert c.post("/api/analyses/upload", files={"file": ("x.pdf", b"%PDF", "application/pdf")}).status_code == 415
    assert c.post("/api/analyses/upload", files={"file": ("x.xlsx", b"nao e zip", "application/octet-stream")}).status_code == 422
    assert c.post("/api/analyses/00000000-0000-0000-0000-000000000000/run", json={}).status_code == 404
    assert c.get("/api/analyses").json()["total"] == 0  # uploads rejeitados não ficam registrados


def test_limite_de_tamanho(user_client, monkeypatch):
    monkeypatch.setenv("DATACHECK_MAX_UPLOAD_MB", "0.001")
    r = user_client.post("/api/analyses/upload", files={"file": ("a.csv", b"a,b\n" + b"1,2\n" * 1000, "text/csv")})
    assert r.status_code == 413


def test_erro_de_configuracao_nao_consome_o_upload(user_client):
    aid = upload_sample(user_client)["id"]
    bad = user_client.post(f"/api/analyses/{aid}/run", json={"config": {"types": {"expected": {"zzz": "decimal"}}}})
    assert bad.status_code == 422
    assert user_client.post(f"/api/analyses/{aid}/run", json={"config": BASE_CONFIG}).status_code == 200


def test_feedback_e_arquivo_expirado(user_client, monkeypatch):
    aid = upload_sample(user_client)["id"]
    user_client.post(f"/api/analyses/{aid}/run", json={"config": BASE_CONFIG})
    body = {"usability_rating": 4, "usefulness_rating": 5, "would_use_again": "sim", "suggestions": "ok"}
    assert user_client.post(f"/api/analyses/{aid}/feedback", json={**body, "usability_rating": 9}).status_code == 422
    assert user_client.post(f"/api/analyses/{aid}/feedback", json=body).status_code == 201
    assert user_client.get(f"/api/analyses/{aid}").json()["feedback_submitted"] is True
    user_client.delete(f"/api/analyses/{aid}")
    with Session(get_engine()) as db:  # feedback sobrevive à exclusão da análise
        fb = db.scalars(select(AnalysisFeedback)).one()
        assert fb.analysis_id is None and fb.usability_rating == 4
    # upload abandonado expira
    old = upload_sample(user_client)["id"]
    monkeypatch.setenv("DATACHECK_UPLOAD_TTL_MINUTES", "0")
    import time; time.sleep(0.05)
    assert temp_storage.purge_expired() == 1
    assert user_client.post(f"/api/analyses/{old}/run", json={"config": BASE_CONFIG}).status_code == 410


def test_visualizar_planilha_original_sem_baixar(user_client, other_client=None):
    c = user_client
    aid = upload_sample(c)["id"]
    c.post(f"/api/analyses/{aid}/run", json={"config": BASE_CONFIG})
    d = c.get(f"/api/analyses/{aid}/data", params={"page_size": 10}).json()
    assert d["total"] == d["total_rows"] == 100 and d["label"] == "Original" and len(d["rows"]) == 10
    assert d["columns"] == ["ID", "Município", "Latitude", "Longitude", "Data do registro", "Quantidade de famílias", "Situação"]
    assert [r["row"] for r in d["rows"]] == list(range(2, 12))                       # numeração da planilha original
    bad = c.get(f"/api/analyses/{aid}/data", params={"q": "doze"}).json()           # busca em qualquer coluna
    assert bad["total"] == 1 and bad["rows"][0]["flags"]["Quantidade de famílias"]["category"] == "tipo_incompativel"
    assert bad["rows"][0]["values"][5] == "doze"                                     # valor original, sem alteração
    assert c.get(f"/api/analyses/{aid}/data", params={"q": "inexistente-xyz"}).json()["total"] == 0
    assert c.get(f"/api/analyses/{aid}/data", params={"page": 2, "page_size": 100}).json()["rows"] == []
    off = upload_sample(c)["id"]
    c.post(f"/api/analyses/{off}/run", json={"config": BASE_CONFIG, "keep_data": False})
    assert c.get(f"/api/analyses/{off}/data").status_code == 409
