"""Modelos de configuração das verificações e das requisições da API."""
from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.core.config import DEFAULT_MARKERS


class MissingConfig(BaseModel):
    enabled: bool = True
    columns: Optional[list[str]] = None  # None = todas as colunas
    markers: list[str] = Field(default_factory=lambda: list(DEFAULT_MARKERS))
    treat_blank: bool = True
    required_columns: list[str] = Field(default_factory=list)  # ausência aqui é crítica


class DuplicatesConfig(BaseModel):
    enabled: bool = True
    key_columns: Optional[list[str]] = None  # None/[] = linha completa


class TypesConfig(BaseModel):
    enabled: bool = True
    expected: dict[str, Literal["integer", "decimal", "text", "date"]] = Field(default_factory=dict)
    date_format: Optional[str] = None  # formato strptime; None = formatos comuns


class RangeLimit(BaseModel):
    min: Optional[float] = None
    max: Optional[float] = None


class RangesConfig(BaseModel):
    enabled: bool = True
    limits: dict[str, RangeLimit] = Field(default_factory=dict)
    suspect_columns: list[str] = Field(default_factory=list)  # detecção estatística (IQR), só alerta


class GeoConfig(BaseModel):
    enabled: bool = True
    lat_column: Optional[str] = None
    lon_column: Optional[str] = None


class DatesConfig(BaseModel):
    enabled: bool = True
    columns: list[str] = Field(default_factory=list)
    date_format: Optional[str] = None
    min_date: Optional[date] = None
    max_date: Optional[date] = None
    flag_future: bool = False


class AnalysisConfig(BaseModel):
    decimal_separator: Literal["auto", "comma", "dot"] = "auto"
    missing: MissingConfig = Field(default_factory=MissingConfig)
    duplicates: DuplicatesConfig = Field(default_factory=DuplicatesConfig)
    types: TypesConfig = Field(default_factory=TypesConfig)
    ranges: RangesConfig = Field(default_factory=RangesConfig)
    geo: GeoConfig = Field(default_factory=GeoConfig)
    dates: DatesConfig = Field(default_factory=DatesConfig)


class RunRequest(BaseModel):
    sheet: Optional[str] = None
    config: AnalysisConfig = Field(default_factory=AnalysisConfig)
    # False = não grava o valor original das células (minimização de dados).
    store_values: bool = True
    # True = guarda a base em armazenamento privado (versionado) para tratamento e EDA; exclusão a qualquer momento.
    keep_data: bool = True
