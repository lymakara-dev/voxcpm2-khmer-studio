.PHONY: test test-backend test-frontend install-backend install-frontend

install-backend:
	cd backend && python3 -m venv .venv
	cd backend && .venv/bin/pip install -q -r requirements-dev.txt

install-frontend:
	cd frontend && npm install
	cd frontend && npx playwright install --with-deps chromium

test-backend:
	cd backend && MOCK_TTS=1 .venv/bin/python -m pytest

test-frontend:
	cd frontend && npm run build
	cd frontend && npm test

test: test-backend test-frontend
