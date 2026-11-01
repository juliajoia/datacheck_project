import io

import openpyxl
import pytest

from app.core.errors import DataCheckError
from app.services.file_reader import read_table


def test_csv_basico_e_numeracao_de_linhas():
    t = read_table(b"a,b\n1,2\n3,4\n", "x.csv")
    assert list(t.df.columns) == ["a", "b"]
    assert len(t.df) == 2 and t.first_data_line == 2


def test_csv_ponto_e_virgula_e_cp1252():
    t = read_table("nome;cidade\nJosé;São Paulo\n".encode("cp1252"), "x.csv")
    assert t.encoding == "cp1252" and t.delimiter == ";"
    assert t.df.iloc[0, 1] == "São Paulo"


def test_arquivo_vazio():
    for content in (b"", b"   \n\n"):
        with pytest.raises(DataCheckError, match="vazio"):
            read_table(content, "x.csv")


def test_somente_cabecalho():
    with pytest.raises(DataCheckError, match="cabeçalho"):
        read_table(b"a,b\n", "x.csv")


def test_csv_com_linha_de_tamanho_inconsistente():
    with pytest.raises(DataCheckError, match="Não foi possível ler"):
        read_table(b"a,b\n1,2,3,4\n5,6\n", "x.csv")


def test_extensao_nao_suportada_e_xlsx_corrompido():
    with pytest.raises(DataCheckError, match="Formato não suportado"):
        read_table(b"x", "x.txt")
    with pytest.raises(DataCheckError, match="não é um .xlsx válido"):
        read_table(b"isto nao e zip", "x.xlsx")
    with pytest.raises(DataCheckError, match="corrompido"):
        read_table(b"PK\x03\x04lixo", "x.xlsx")


def _xlsx():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "A"
    ws.append(["n", "f"])
    ws.append([1, "=1+1"])
    wb.create_sheet("B").append(["x"])
    wb["B"].append(["y"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_xlsx_abas_e_formulas_nao_executadas():
    content = _xlsx()
    t = read_table(content, "x.xlsx")
    assert t.sheets == ["A", "B"] and t.sheet == "A"
    # sem valor em cache, fórmula nunca é calculada
    assert t.df.iloc[0, 1] in ("", "=1+1")
    assert read_table(content, "x.xlsx", "B").df.iloc[0, 0] == "y"
    with pytest.raises(DataCheckError, match="não existe"):
        read_table(content, "x.xlsx", "Z")
