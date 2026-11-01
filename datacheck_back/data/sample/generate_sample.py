"""Gera as duas bases fictícias de exemplo e seus gabaritos (determinístico).

Uso: python data/sample/generate_sample.py
Municípios, números e datas são inventados. Os gabaritos listam cada erro inserido
(linha do arquivo original, coluna e categorias esperadas) e servem aos testes automatizados.
"""
import csv
import random
from pathlib import Path

OUT = Path(__file__).parent
HEADER = ["ID", "Município", "Latitude", "Longitude", "Data do registro", "Quantidade de famílias", "Situação"]
STATUS = ["Ativo", "Inativo", "Em análise", "Concluído"]

BASES = {
    1: dict(seed=42, delimiter=",", decimal=".", date="%Y-%m-%d", id_start=1001,
            names=["Vila Nova do Sul", "Rio Claro do Norte", "Serra Dourada", "Campo Verde Alto", "Pedra Azul do Vale",
                   "Lagoa Funda", "Monte Alegre do Leste", "Santa Aurora", "Porto Seguro do Oeste", "Boa Esperança do Mar",
                   "Terra Branca", "Alto Horizonte", "Ilha Formosa", "Cachoeira Grande", "São Ludgero Novo"]),
    2: dict(seed=7, delimiter=";", decimal=",", date="%d/%m/%Y", id_start=5001,
            names=["Bela Vista do Planalto", "Rio das Pedras Altas", "Colina Dourada", "Vale do Sol Nascente",
                   "Ponte Alta do Norte", "Jardim das Águas", "Morro Azul", "Fazenda Nova do Leste",
                   "Praia Grande do Sul", "Cruzeiro do Vale", "Campina Verde", "São Tomé do Oeste"]),
}


def build(cfg):
    random.seed(cfg["seed"])
    dec = lambda x: f"{x:.4f}".replace(".", cfg["decimal"])
    d = lambda y, m, day: cfg["date"].replace("%Y", f"{y}").replace("%m", f"{m:02d}").replace("%d", f"{day:02d}")
    rows = [[str(cfg["id_start"] + i), random.choice(cfg["names"]), dec(random.uniform(-33.0, 5.0)),
             dec(random.uniform(-73.0, -35.0)), d(random.randint(2023, 2025), random.randint(1, 12), random.randint(1, 28)),
             str(random.randint(10, 5000)), random.choice(STATUS)] for i in range(96)]
    col = {n: i for i, n in enumerate(HEADER)}
    errors, free = [], list(range(96))
    random.shuffle(free)

    def inject(column, value, cats, desc):
        idx = free.pop()
        rows[idx][col[column]] = value
        errors.append((idx, column, cats, value, desc))

    for v in ["", "", ""]:
        inject("Município", v, "valores_ausentes", "Município vazio")
    inject("Município", "N/A", "valores_ausentes", "Marcador de ausência N/A")
    inject("Município", "n/a", "valores_ausentes", "Marcador de ausência n/a")
    inject("Município", "   ", "valores_ausentes", "Município só com espaços")
    for _ in range(2):
        inject("Quantidade de famílias", "", "valores_ausentes", "Quantidade de famílias vazia")
        inject("Situação", "", "valores_ausentes", "Situação vazia")
    inject("Latitude", "", "valores_ausentes;geo_ausente", "Latitude vazia")
    inject("Data do registro", "", "valores_ausentes", "Data vazia")

    inject("Latitude", dec(123.45), "geo_fora_limite", "Latitude acima de 90")
    inject("Latitude", dec(-95.2), "geo_fora_limite", "Latitude abaixo de -90")
    inject("Longitude", dec(-250.1), "geo_fora_limite", "Longitude abaixo de -180")
    inject("Longitude", dec(200.5), "geo_fora_limite", "Longitude acima de 180")
    inject("Latitude", "abc", "geo_nao_numerica", "Latitude com texto")

    inject("Quantidade de famílias", "doze", "tipo_incompativel", "Texto em coluna numérica")
    inject("Quantidade de famílias", "trinta", "tipo_incompativel", "Texto em coluna numérica")
    inject("Quantidade de famílias", "12,5x", "tipo_incompativel", "Número com caractere extra")
    inject("Quantidade de famílias", "-15", "fora_limites", "Valor negativo (mínimo configurado: 0)")
    inject("Quantidade de famílias", "-3", "fora_limites", "Valor negativo (mínimo configurado: 0)")
    inject("Quantidade de famílias", "9999999", "fora_limites", "Acima do máximo configurado (100000)")

    inject("Data do registro", d(2023, 2, 30), "data_invalida", "30 de fevereiro não existe")
    inject("Data do registro", "31/13/2024", "data_invalida", "Mês 13 não existe")
    inject("Data do registro", "ontem", "data_invalida", "Texto no lugar de data")
    inject("Data do registro", d(2031, 5, 10), "data_futura", "Data futura")
    inject("Data do registro", d(1899, 1, 1), "data_fora_limite", "Anterior ao mínimo configurado (1990-01-01)")

    # Duplicatas: o registro original e a cópia pertencem ao grupo duplicado (ambos são sinalizados).
    dirty = {e[0] for e in errors}
    sources = random.sample([i for i in range(96) if i not in dirty], 4)
    for src in sources:
        rows.append(list(rows[src]))
        label = " | ".join(rows[src][:4])
        errors.append((src, "(linha completa)", "duplicados", label, f"Original; repetido na linha {len(rows) + 1}"))
        errors.append((len(rows) - 1, "(linha completa)", "duplicados", label, f"Cópia exata da linha {src + 2}"))
    return rows, errors


for n, cfg in BASES.items():
    rows, errors = build(cfg)
    with open(OUT / f"municipios_exemplo_{n}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=cfg["delimiter"])
        w.writerow(HEADER)
        w.writerows(rows)
    with open(OUT / f"gabarito_erros_{n}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["linha_original", "coluna", "categorias_esperadas", "valor_inserido", "descricao"])
        for idx, column, cats, value, desc in sorted(errors):
            w.writerow([idx + 2, column, cats, value, desc])
    print(f"base {n}: {len(rows)} registros, {len(errors)} linhas no gabarito")
