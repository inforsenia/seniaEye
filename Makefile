PYTHON ?= python

.PHONY: install server agent run venv

venv:
	$(PYTHON) -m venv venv

install: venv
	./venv/bin/python -m pip install -r requirements.txt

server:
	$(PYTHON) -m uvicorn server.main:app --reload --host 0.0.0.0 --port 8000

agent:
	$(PYTHON) -m agent.main
