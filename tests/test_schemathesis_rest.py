"""Fuzzing del contrato OpenAPI con Schemathesis sobre las operaciones de lectura.

Schemathesis genera requests positivos Y negativos desde el spec vivo y verifica:
- ningún 5xx inesperado (not_a_server_error)
- cada 2xx valida contra su schema del spec (response_schema_conformance)
- ningún código de estado no declarado (status_code_conformance)

Solo operaciones GET: las que modifican estado (POST/PUT/DELETE)
se testean en test_rest_contract.py.
"""
import schemathesis
from hypothesis import HealthCheck, settings

from conftest import BASE, ADMIN_KEY

schema = schemathesis.from_uri(
    f"{BASE}/openapi.json",
    method="GET",
    validate_schema=False,
)

HEADERS = {"X-API-KEY": ADMIN_KEY}


@schema.parametrize()
@settings(max_examples=15, suppress_health_check=list(HealthCheck), deadline=10000)
def test_contract_get_operations(case):
    case.call_and_validate(headers=HEADERS)
