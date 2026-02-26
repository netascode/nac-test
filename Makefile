# Developer helper – run `make prepush` before submitting PRs
# This target loops through formatting, linting, and pre-commit checks
# multiple times to auto-fix and stage all changes, ensuring local compliance
# with the same rules enforced in CI/CD.

# Number of passes to run. Default is 4 unless overridden at runtime:
# Example: `make prepush LOOPS=6`
LOOPS ?= 4

# Declares that these targets are not real files
.PHONY: prepush

prepush:
	@i=1; \
	while [ $$i -le $(LOOPS) ]; do \
		echo "🌀 Pass $$i of $(LOOPS)"; \
		uv run ruff format . && git add .; \
		uv run ruff format --check . && git add .; \
		uv run ruff check . --fix && git add .; \
		uv run ruff check . --fix && git add .; \
		uv run ruff format && git add .; \
		uv run pre-commit run --all-files && git add .; \
		i=$$((i+1)); \
	done; \
	echo "✅ Final git status:"; \
	git status
