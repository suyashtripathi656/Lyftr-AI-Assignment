.PHONY: up down logs test clean

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f

test:
	cd backend && pip install -r requirements.txt -q && python -m pytest tests/ -v

clean:
	docker compose down -v --rmi local
	rm -rf backend/__pycache__ backend/app/__pycache__ backend/tests/__pycache__
