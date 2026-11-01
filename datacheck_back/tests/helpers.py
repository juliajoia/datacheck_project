import io
from datetime import date

import pandas as pd

from app.schemas.validation import AnalysisConfig
from app.services.analyzer import run_analysis
from app.services.file_reader import LoadedTable

TODAY = date(2026, 1, 1)


def table_from(rows, columns):
    return LoadedTable(df=pd.DataFrame(rows, columns=columns, dtype=str), header_line=1)


def analyze(rows, columns, **cfg):
    table = table_from(rows, columns)
    return run_analysis(table, AnalysisConfig(**cfg), filename="t.csv", file_size=1, today=TODAY)


def cats(issues):
    return [i.category for i in issues]
