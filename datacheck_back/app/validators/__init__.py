from app.validators.base import Issue, Rule, RuleContext, RuleOutput
from app.validators.data_types import TypesRule
from app.validators.dates import DatesRule
from app.validators.duplicates import DuplicatesRule
from app.validators.geo import GeoRule
from app.validators.missing import MissingRule
from app.validators.ranges import RangesRule

# Ordem de execução = ordem das letras A–F do escopo do produto.
RULES: list[Rule] = [MissingRule(), DuplicatesRule(), TypesRule(), RangesRule(), GeoRule(), DatesRule()]

__all__ = ["RULES", "Issue", "Rule", "RuleContext", "RuleOutput"]
