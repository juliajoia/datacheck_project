"""Exporta todos os feedbacks (para a análise do experimento) em CSV, sem identificar usuários.

Uso: python -m app.scripts.export_feedback > feedbacks.csv
"""
import csv
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_engine
from app.models import AnalysisFeedback


def main() -> None:
    w = csv.writer(sys.stdout)
    w.writerow(["data", "facilidade_1a5", "utilidade_1a5", "usaria_novamente", "dificuldades", "sugestoes"])
    with Session(get_engine()) as db:
        for f in db.scalars(select(AnalysisFeedback).order_by(AnalysisFeedback.created_at)):
            w.writerow([f.created_at.isoformat(timespec="seconds"), f.usability_rating, f.usefulness_rating,
                        f.would_use_again, f.difficulties, f.suggestions])


if __name__ == "__main__":
    main()
