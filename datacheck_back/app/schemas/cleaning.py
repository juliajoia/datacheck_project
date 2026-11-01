from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

Action = Literal[
    "impute", "remove_duplicates", "merge_duplicates", "set_value", "mark_missing", "convert_number",
    "convert_date", "clip", "swap_latlon", "remove_rows", "accept_exception",
]


class CleaningRequest(BaseModel):
    base_version: int = Field(description="Versão em que o usuário está trabalhando (controle de concorrência)")
    action: Action
    column: Optional[str] = None
    scope: Literal["selected", "column_all"] = "selected"
    rows: list[int] = []                    # linhas originais selecionadas
    cells: list[dict[str, Any]] = []        # [{row, column, value?, category?}]
    params: dict[str, Any] = {}
    justification: Optional[str] = Field(default=None, max_length=2000)
    confirm: bool = False                   # só a aplicação exige
    acknowledge: list[str] = []             # confirmações explícitas (ex.: type_change, remove_rows)


class ColumnTypesIn(BaseModel):
    types: dict[str, dict[str, Any]]        # {coluna: {"type": "...", "order": [...]}} ou {"type": null} para limpar


class OutlierRequest(BaseModel):
    column: str
    method: Literal["iqr", "zscore", "limits"] = "iqr"
    params: dict[str, Any] = {}
