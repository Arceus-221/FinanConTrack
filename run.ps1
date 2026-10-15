$ErrorActionPreference = "Stop"

Write-Host "==> Syncing dependencies..." -ForegroundColor Cyan
uv sync
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> Running pytest..." -ForegroundColor Cyan
uv run pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> Running ruff..." -ForegroundColor Cyan
uv run ruff check .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> Launching Streamlit app..." -ForegroundColor Green
uv run streamlit run app.py