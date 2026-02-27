PYTHON ?= python3

.PHONY: install server agent run venv help

venv:
	$(PYTHON) -m venv venv

install: venv
	./venv/bin/python -m pip install -r requirements.txt

server:
	$(PYTHON) -m uvicorn server.main:app --reload --host 0.0.0.0 --port 8000

agent:
	sudo ./venv/bin/python -m agent.main

clean: 
	find ./package | grep -E "(__pycache__|\.pyc$$)" | xargs rm -rf

help:
	@echo "Available targets:"
	@echo "  make venv      # create virtual environment"
	@echo "  make install   # install dependencies (creates venv)"
	@echo "  make server    # start the FastAPI server"
	@echo "  make agent     # run monitoring agent"
	@echo "  make run       # start server (agent separately)"
	@echo "  make help      # show this message"
