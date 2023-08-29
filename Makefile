.PHONY: test
test:
	@python3 devrun.py --help
	@pytest -vv --tb=long

.PHONY: install
install:
	@pip install -e .

.PHONY: distclean
distclean:
	@find . | grep -E "(/__pycache__$$)" | xargs rm -rf
	@rm -rf .pytest_cache/ build/
