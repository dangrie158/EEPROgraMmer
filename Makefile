PYTHON = python3

MODULE_NAME = eepro
AUTHOR = "Daniel Grießhaber"

format:
	black $(MODULE_NAME)/*.py

analyze:
	$(PYTHON) -m mypy $(MODULE_NAME)/*.py
	$(PYTHON) -m pylint $(MODULE_NAME)/*.py

test: format analyze
	$(PYTHON) -m unittest $(MODULE_NAME)/test_*.py

clean:
	$(PYTHON) setup.py clean

install:
	$(PYTHON) setup.py install

release: clean test
	$(PYTHON) setup.py sdist upload

.PHONY: clean test format analyze release
