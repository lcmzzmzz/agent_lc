# Ecommerce Eval Cases

Each line in `cases.jsonl` is one golden case for the ecommerce research workflow.

Required fields:

- `case_id`: stable identifier.
- `query`: product/category query.
- `target_market`: market code accepted by `validate_research_request()`.
- `platforms`: search platforms.
- `depth`: `fast`, `standard`, or `deep`.
- `expected`: score ranges and coverage constraints.

Run from the project root with:

```bash
py -m pytest tests/test_ecommerce_eval_runner.py -q
```

Programmatic usage:

```python
from multi_agents.ecommerce.eval_runner import run_eval_cases
```
