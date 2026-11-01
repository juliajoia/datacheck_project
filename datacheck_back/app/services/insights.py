"""Insights: interpretação dos resultados.

Versão atual: regras programadas, sem nenhuma chamada externa.

Extensão futura com modelo de linguagem: implemente `InsightProvider` (ex.: resumo
executivo, sugestão de novas regras, impacto das inconsistências) e registre-o em
`get_provider`. O provedor recebe apenas `summary`, que contém indicadores agregados
e nomes de colunas, nunca valores de células. Só deve ser ativado com consentimento
explícito do usuário.
"""
from __future__ import annotations

from typing import Protocol

LOCATION_HINTS = ("munic", "cidade", "estado", "uf", "bairro", "local", "regi", "endere")


class InsightProvider(Protocol):
    name: str

    def generate(self, summary: dict) -> list[dict]: ...


def _item(level: str, title: str, text: str, recommendation: str) -> dict:
    return {"level": level, "title": title, "text": text, "recommendation": recommendation}


class RuleBasedProvider:
    name = "rules"

    def generate(self, summary: dict) -> list[dict]:
        m = summary["metrics"]
        counts = {c["category"]: c["count"] for c in m["by_category"]}
        items: list[dict] = []

        if m["total_occurrences"] == 0:
            items.append(_item(
                "success", "Nenhuma inconsistência detectada",
                "As regras executadas não encontraram inconsistências nesta base.",
                "Isso não garante qualidade total: considere acrescentar regras para outros aspectos dos dados."))
        else:
            pct = m["affected_rows_pct"]
            level = "critical" if pct >= 30 else "warning" if pct >= 5 else "info"
            items.append(_item(
                level, "Visão geral",
                f"{pct:g}% dos registros ({m['affected_rows']} de {m['total_rows']}) apresentam "
                f"pelo menos uma inconsistência detectada, em um total de {m['total_occurrences']} ocorrências.",
                "Comece pelas ocorrências de severidade crítica na tabela de inconsistências."))

        for row in sorted(m["missing_by_column"], key=lambda r: -r["pct"])[:3]:
            if row["pct"] < 1:
                continue
            name = row["column"]
            if any(h in name.lower() for h in LOCATION_HINTS):
                impact = "podem comprometer análises agrupadas por localização"
            else:
                impact = "podem enviesar médias, contagens e agrupamentos que usem essa coluna"
            items.append(_item(
                "critical" if row["pct"] >= 50 else "warning", f"Ausências em «{name}»",
                f"A coluna «{name}» possui {row['count']} valores ausentes ({row['pct']:g}%) que {impact}.",
                "Verifique se o dado existe na fonte; se não, defina como a ausência deve ser tratada nas análises."))

        if counts.get("duplicados"):
            items.append(_item(
                "warning", "Registros duplicados",
                f"Foram encontrados {counts['duplicados']} registros pertencentes a grupos duplicados. Recomenda-se "
                "verificar se representam importações repetidas ou ocorrências legítimas.",
                "Compare as linhas repetidas com a primeira ocorrência antes de removê-las."))

        if counts.get("tipo_incompativel"):
            cols = ", ".join(f"«{c['column']}»" for c in m["top_columns_by_category"].get("tipo_incompativel", []))
            items.append(_item(
                "critical", "Tipos incompatíveis",
                f"{counts['tipo_incompativel']} valores não correspondem ao tipo esperado (colunas: {cols}). "
                "Eles podem impedir somas, médias e ordenações corretas.",
                "Corrija na origem ou padronize o formato antes de importar a base em outras ferramentas."))

        if counts.get("fora_limites"):
            items.append(_item(
                "critical", "Valores fora dos limites configurados",
                f"{counts['fora_limites']} valores violam os intervalos que você definiu.",
                "Confirme cada caso com a fonte e ajuste os limites se estiverem inadequados."))

        if counts.get("valor_suspeito"):
            items.append(_item(
                "info", "Valores suspeitos",
                f"{counts['valor_suspeito']} valores estão muito distantes da distribuição da coluna. "
                "São apenas suspeitos: nada indica que estejam errados sem uma regra que o confirme.",
                "Revise-os e, se houver um limite de negócio, configure-o para virar uma regra explícita."))

        geo = sum(counts.get(c, 0) for c in ("geo_ausente", "geo_nao_numerica", "geo_fora_limite"))
        if geo:
            items.append(_item(
                "critical" if counts.get("geo_fora_limite") or counts.get("geo_nao_numerica") else "warning",
                "Coordenadas geográficas",
                f"{geo} ocorrências em coordenadas. Registros com coordenadas inválidas ou ausentes "
                "não aparecerão corretamente em mapas e análises espaciais.",
                "Revise latitude/longitude (pontos decimais, sinais e possível troca entre colunas)."))

        dates = sum(counts.get(c, 0) for c in ("data_invalida", "data_futura", "data_fora_limite"))
        if dates:
            items.append(_item(
                "warning", "Datas",
                f"{dates} ocorrências em datas (inválidas, futuras ou fora do período definido). "
                "Elas podem distorcer séries temporais e filtros por período.",
                "Padronize o formato das datas e confirme os períodos esperados."))

        skipped = [r["name"] for r in summary["rules"] if not r["executed"]]
        if skipped:
            items.append(_item(
                "info", "Verificações não executadas",
                "As seguintes verificações não foram executadas: " + ", ".join(skipped) + ".",
                "Configure-as em uma nova análise para ampliar a cobertura."))

        if summary.get("issues_truncated"):
            items.append(_item(
                "info", "Lista de ocorrências limitada",
                "Havia mais ocorrências do que o limite armazenado; os totais continuam exatos, "
                "mas a tabela mostra apenas parte delas.",
                "Corrija os problemas mais frequentes e analise novamente."))
        return items


def get_provider() -> InsightProvider:
    return RuleBasedProvider()


def generate_insights(summary: dict) -> dict:
    provider = get_provider()
    return {"provider": provider.name, "llm_available": False, "items": provider.generate(summary)}
