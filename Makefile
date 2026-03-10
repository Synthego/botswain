.PHONY: help install test test-verbose test-coverage lint format clean run migrate makemigrations shell createsuperuser
.PHONY: docker-build docker-up docker-down docker-restart docker-logs docker-shell docker-test
.PHONY: requirements freeze check staticfiles
.PHONY: cli cli-test cli-debug
.PHONY: run-bedrock run-claude-cli check-bedrock show-provider
.PHONY: token-report token-report-today token-report-week token-report-month show-coverage

# Variables
PYTHON := python
VENV := venv
VENV_BIN := $(VENV)/bin
DJANGO_SETTINGS := botswain.settings.local
TEST_SETTINGS := botswain.settings.test
DOCKER_COMPOSE := docker-compose

# Colors for output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[0;33m
BLUE := \033[0;34m
NC := \033[0m # No Color

##@ General

help: ## Display this help message
	@echo "$(BLUE)Botswain - Natural Language Factory Query Assistant$(NC)"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"; printf "Usage:\n  make $(CYAN)<target>$(NC)\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  $(CYAN)%-20s$(NC) %s\n", $$1, $$2 } /^##@/ { printf "\n$(YELLOW)%s$(NC)\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Setup & Installation

install: ## Install all dependencies in virtual environment
	@echo "$(GREEN)Installing dependencies...$(NC)"
	$(PYTHON) -m venv $(VENV)
	$(VENV_BIN)/pip install --upgrade pip
	$(VENV_BIN)/pip install -r requirements.txt
	@echo "$(GREEN)✓ Installation complete!$(NC)"
	@echo "$(YELLOW)Run 'source venv/bin/activate' to activate the environment$(NC)"

requirements: ## Install/update requirements
	@echo "$(GREEN)Installing requirements...$(NC)"
	$(VENV_BIN)/pip install -r requirements.txt

freeze: ## Freeze current dependencies to requirements.txt
	@echo "$(GREEN)Freezing dependencies...$(NC)"
	$(VENV_BIN)/pip freeze > requirements.txt

##@ Development Server

run: ## Run development server (local)
	@echo "$(GREEN)Starting Botswain development server...$(NC)"
	DJANGO_SETTINGS_MODULE=$(DJANGO_SETTINGS) $(VENV_BIN)/python manage.py runserver 8002

run-production: ## Run with production settings
	@echo "$(GREEN)Starting Botswain in production mode...$(NC)"
	DJANGO_SETTINGS_MODULE=botswain.settings.production $(VENV_BIN)/python manage.py runserver 8002

##@ Database

migrate: ## Run database migrations
	@echo "$(GREEN)Running migrations...$(NC)"
	DJANGO_SETTINGS_MODULE=$(DJANGO_SETTINGS) $(VENV_BIN)/python manage.py migrate

makemigrations: ## Create new migrations
	@echo "$(GREEN)Creating migrations...$(NC)"
	DJANGO_SETTINGS_MODULE=$(DJANGO_SETTINGS) $(VENV_BIN)/python manage.py makemigrations

migrate-test: ## Run migrations for test database
	@echo "$(GREEN)Running test database migrations...$(NC)"
	DJANGO_SETTINGS_MODULE=$(TEST_SETTINGS) $(VENV_BIN)/python manage.py migrate

shell: ## Open Django shell
	@echo "$(GREEN)Opening Django shell...$(NC)"
	DJANGO_SETTINGS_MODULE=$(DJANGO_SETTINGS) $(VENV_BIN)/python manage.py shell

dbshell: ## Open database shell
	@echo "$(GREEN)Opening database shell...$(NC)"
	DJANGO_SETTINGS_MODULE=$(DJANGO_SETTINGS) $(VENV_BIN)/python manage.py dbshell

createsuperuser: ## Create Django superuser
	@echo "$(GREEN)Creating superuser...$(NC)"
	DJANGO_SETTINGS_MODULE=$(DJANGO_SETTINGS) $(VENV_BIN)/python manage.py createsuperuser

##@ Testing

test: ## Run all tests
	@echo "$(GREEN)Running test suite...$(NC)"
	$(VENV_BIN)/pytest

test-verbose: ## Run tests with verbose output
	@echo "$(GREEN)Running test suite (verbose)...$(NC)"
	$(VENV_BIN)/pytest -v

test-coverage: ## Run tests with coverage report
	@echo "$(GREEN)Running tests with coverage...$(NC)"
	$(VENV_BIN)/pytest --cov=core --cov=api --cov-report=html --cov-report=term
	@echo "$(YELLOW)Coverage report: htmlcov/index.html$(NC)"

test-watch: ## Run tests in watch mode (requires pytest-watch)
	@echo "$(GREEN)Running tests in watch mode...$(NC)"
	$(VENV_BIN)/ptw

test-failed: ## Re-run only failed tests
	@echo "$(GREEN)Re-running failed tests...$(NC)"
	$(VENV_BIN)/pytest --lf

test-api: ## Run only API tests
	@echo "$(GREEN)Running API tests...$(NC)"
	$(VENV_BIN)/pytest tests/test_api_*.py -v

test-core: ## Run only core tests
	@echo "$(GREEN)Running core tests...$(NC)"
	$(VENV_BIN)/pytest tests/test_*_*.py -v --ignore=tests/test_api_*.py

test-unit: ## Run unit tests (non-Django)
	@echo "$(GREEN)Running unit tests...$(NC)"
	$(VENV_BIN)/pytest -m "not django_db" -v

##@ Code Quality

check: ## Run Django system checks
	@echo "$(GREEN)Running Django checks...$(NC)"
	DJANGO_SETTINGS_MODULE=$(DJANGO_SETTINGS) $(VENV_BIN)/python manage.py check

lint: ## Run code linting (flake8, pylint)
	@echo "$(GREEN)Running linters...$(NC)"
	@if [ -f "$(VENV_BIN)/flake8" ]; then \
		$(VENV_BIN)/flake8 core/ api/ --max-line-length=120 --exclude=migrations; \
	else \
		echo "$(YELLOW)flake8 not installed. Run: pip install flake8$(NC)"; \
	fi
	@if [ -f "$(VENV_BIN)/pylint" ]; then \
		$(VENV_BIN)/pylint core/ api/ --disable=C0111,R0903; \
	else \
		echo "$(YELLOW)pylint not installed. Run: pip install pylint$(NC)"; \
	fi

format: ## Format code with black and isort
	@echo "$(GREEN)Formatting code...$(NC)"
	@if [ -f "$(VENV_BIN)/black" ]; then \
		$(VENV_BIN)/black core/ api/ tests/ --line-length=120; \
	else \
		echo "$(YELLOW)black not installed. Run: pip install black$(NC)"; \
	fi
	@if [ -f "$(VENV_BIN)/isort" ]; then \
		$(VENV_BIN)/isort core/ api/ tests/; \
	else \
		echo "$(YELLOW)isort not installed. Run: pip install isort$(NC)"; \
	fi

format-check: ## Check code formatting without making changes
	@echo "$(GREEN)Checking code formatting...$(NC)"
	@if [ -f "$(VENV_BIN)/black" ]; then \
		$(VENV_BIN)/black core/ api/ tests/ --check --line-length=120; \
	else \
		echo "$(YELLOW)black not installed. Run: pip install black$(NC)"; \
	fi

type-check: ## Run mypy type checking
	@echo "$(GREEN)Running type checks...$(NC)"
	@if [ -f "$(VENV_BIN)/mypy" ]; then \
		$(VENV_BIN)/mypy core/ api/ --ignore-missing-imports; \
	else \
		echo "$(YELLOW)mypy not installed. Run: pip install mypy$(NC)"; \
	fi

##@ Docker

docker-build: ## Build Docker images
	@echo "$(GREEN)Building Docker images...$(NC)"
	$(DOCKER_COMPOSE) build

docker-up: ## Start all Docker services
	@echo "$(GREEN)Starting Docker services...$(NC)"
	$(DOCKER_COMPOSE) up -d
	@echo "$(GREEN)✓ Services started!$(NC)"
	@echo "$(YELLOW)API available at: http://localhost:8002$(NC)"
	@echo "$(YELLOW)Run 'make docker-logs' to view logs$(NC)"

docker-down: ## Stop all Docker services
	@echo "$(GREEN)Stopping Docker services...$(NC)"
	$(DOCKER_COMPOSE) down

docker-restart: ## Restart all Docker services
	@echo "$(GREEN)Restarting Docker services...$(NC)"
	$(DOCKER_COMPOSE) restart

docker-logs: ## View Docker service logs
	@echo "$(GREEN)Viewing Docker logs (Ctrl+C to exit)...$(NC)"
	$(DOCKER_COMPOSE) logs -f

docker-logs-web: ## View web service logs only
	@echo "$(GREEN)Viewing web service logs (Ctrl+C to exit)...$(NC)"
	$(DOCKER_COMPOSE) logs -f web

docker-shell: ## Open shell in web container
	@echo "$(GREEN)Opening shell in web container...$(NC)"
	$(DOCKER_COMPOSE) exec web /bin/bash

docker-django-shell: ## Open Django shell in web container
	@echo "$(GREEN)Opening Django shell in web container...$(NC)"
	$(DOCKER_COMPOSE) exec web python manage.py shell

docker-migrate: ## Run migrations in Docker
	@echo "$(GREEN)Running migrations in Docker...$(NC)"
	$(DOCKER_COMPOSE) exec web python manage.py migrate

docker-makemigrations: ## Create migrations in Docker
	@echo "$(GREEN)Creating migrations in Docker...$(NC)"
	$(DOCKER_COMPOSE) exec web python manage.py makemigrations

docker-test: ## Run tests in Docker
	@echo "$(GREEN)Running tests in Docker...$(NC)"
	$(DOCKER_COMPOSE) exec web pytest

docker-superuser: ## Create superuser in Docker
	@echo "$(GREEN)Creating superuser in Docker...$(NC)"
	$(DOCKER_COMPOSE) exec web python manage.py createsuperuser

docker-ps: ## Show running Docker containers
	@echo "$(GREEN)Docker containers:$(NC)"
	$(DOCKER_COMPOSE) ps

docker-clean: ## Remove all Docker containers and volumes
	@echo "$(RED)Removing all Docker containers and volumes...$(NC)"
	$(DOCKER_COMPOSE) down -v
	@echo "$(GREEN)✓ Cleanup complete!$(NC)"

##@ Utilities

clean: ## Clean up Python cache files and test artifacts
	@echo "$(GREEN)Cleaning up...$(NC)"
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.coverage" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	rm -f test_db.sqlite3
	rm -f .coverage
	@echo "$(GREEN)✓ Cleanup complete!$(NC)"

clean-all: clean docker-clean ## Clean everything including Docker

staticfiles: ## Collect static files
	@echo "$(GREEN)Collecting static files...$(NC)"
	DJANGO_SETTINGS_MODULE=$(DJANGO_SETTINGS) $(VENV_BIN)/python manage.py collectstatic --noinput

show-urls: ## Show all URL patterns
	@echo "$(GREEN)Registered URL patterns:$(NC)"
	DJANGO_SETTINGS_MODULE=$(DJANGO_SETTINGS) $(VENV_BIN)/python manage.py show_urls 2>/dev/null || \
	DJANGO_SETTINGS_MODULE=$(DJANGO_SETTINGS) $(VENV_BIN)/python -c "from django.core.management import execute_from_command_line; import sys; sys.argv = ['manage.py', 'show_urls']; execute_from_command_line(sys.argv)" 2>/dev/null || \
	echo "$(YELLOW)show_urls command not available. Install django-extensions: pip install django-extensions$(NC)"

##@ Quick Start

quickstart: install migrate ## Quick start: install dependencies and run migrations
	@echo ""
	@echo "$(GREEN)✓ Quick start complete!$(NC)"
	@echo ""
	@echo "$(YELLOW)Next steps:$(NC)"
	@echo "  1. Activate environment: source venv/bin/activate"
	@echo "  2. Run server: make run"
	@echo "  3. Test API: make test-api-call"
	@echo ""

quickstart-docker: docker-build docker-up docker-migrate ## Quick start with Docker
	@echo ""
	@echo "$(GREEN)✓ Docker quick start complete!$(NC)"
	@echo ""
	@echo "$(YELLOW)Services running:$(NC)"
	@echo "  • API: http://localhost:8002"
	@echo "  • PostgreSQL: localhost:5433"
	@echo "  • Redis: localhost:6380"
	@echo ""
	@echo "$(YELLOW)Useful commands:$(NC)"
	@echo "  • View logs: make docker-logs"
	@echo "  • Run tests: make docker-test"
	@echo "  • Stop: make docker-down"
	@echo ""

##@ API Testing

test-api-call: ## Test API with sample query
	@echo "$(GREEN)Testing API endpoint...$(NC)"
	@echo ""
	@curl -X POST http://localhost:8002/api/query \
		-H "Content-Type: application/json" \
		-d '{"question": "What synthesizers are available?", "format": "json"}' \
		-s | python -m json.tool || echo "$(RED)Error: API not responding. Is the server running?$(NC)"
	@echo ""

test-api-health: ## Check if API is responding
	@echo "$(GREEN)Checking API health...$(NC)"
	@curl -s http://localhost:8002/api/query -o /dev/null -w "%{http_code}" | \
		grep -q "405" && echo "$(GREEN)✓ API is responding$(NC)" || \
		echo "$(RED)✗ API is not responding$(NC)"


##@ CLI Usage

cli: ## Show CLI help
	@echo "$(GREEN)Botswain CLI$(NC)"
	@./botswain-cli.py --help

cli-test: ## Test CLI with sample query
	@echo "$(GREEN)Testing CLI...$(NC)"
	@./botswain-cli.py "What synthesizers are available?"

cli-debug: ## Test CLI in debug mode
	@echo "$(GREEN)Testing CLI with debug output...$(NC)"
	@./botswain-cli.py "What synthesizers are available?" --debug
##@ Documentation

docs: ## Generate documentation
	@echo "$(GREEN)Generating documentation...$(NC)"
	@echo "$(YELLOW)Project documentation:$(NC)"
	@echo "  • README.md - User documentation"
	@echo "  • IMPLEMENTATION_SUMMARY.md - Technical implementation"
	@echo "  • API docs: http://localhost:8002/api/ (when server is running)"

show-config: ## Show current configuration
	@echo "$(BLUE)Botswain Configuration$(NC)"
	@echo "$(YELLOW)Python:$(NC) $$($(PYTHON) --version)"
	@echo "$(YELLOW)Virtual Environment:$(NC) $(VENV)"
	@echo "$(YELLOW)Django Settings:$(NC) $(DJANGO_SETTINGS)"
	@echo "$(YELLOW)Test Settings:$(NC) $(TEST_SETTINGS)"
	@echo ""
	@echo "$(YELLOW)Available endpoints:$(NC)"
	@echo "  • POST /api/query - Main query endpoint"
	@echo "  • GET  /admin/ - Django admin (requires superuser)"
	@echo ""

##@ CI/CD

ci-test: ## Run tests as in CI pipeline
	@echo "$(GREEN)Running CI test suite...$(NC)"
	$(VENV_BIN)/pytest -v --cov=core --cov=api --cov-report=term --cov-report=xml
	@echo "$(GREEN)✓ CI tests complete!$(NC)"

ci-lint: ## Run linting as in CI pipeline
	@echo "$(GREEN)Running CI linting...$(NC)"
	@if [ -f "$(VENV_BIN)/flake8" ]; then \
		$(VENV_BIN)/flake8 core/ api/ --max-line-length=120 --exclude=migrations --statistics; \
	else \
		echo "$(RED)flake8 not installed$(NC)" && exit 1; \
	fi

ci: ci-lint ci-test ## Run full CI pipeline locally
	@echo "$(GREEN)✓ CI pipeline complete!$(NC)"

##@ Deployment

deploy-check: ## Check deployment readiness
	@echo "$(BLUE)Deployment Readiness Check$(NC)"
	@echo ""
	@echo "$(YELLOW)Running system checks...$(NC)"
	@DJANGO_SETTINGS_MODULE=$(DJANGO_SETTINGS) $(VENV_BIN)/python manage.py check --deploy || true
	@echo ""
	@echo "$(YELLOW)Running tests...$(NC)"
	@$(VENV_BIN)/pytest --tb=no -q
	@echo ""
	@echo "$(YELLOW)Checking migrations...$(NC)"
	@DJANGO_SETTINGS_MODULE=$(DJANGO_SETTINGS) $(VENV_BIN)/python manage.py showmigrations | \
		grep -q "\[ \]" && echo "$(RED)⚠ Unapplied migrations found$(NC)" || echo "$(GREEN)✓ All migrations applied$(NC)"
	@echo ""
	@echo "$(GREEN)✓ Deployment check complete!$(NC)"

##@ Development

dev-setup: install migrate createsuperuser ## Full development setup
	@echo "$(GREEN)✓ Development environment ready!$(NC)"
	@echo "$(YELLOW)Run 'make run' to start the server$(NC)"

watch-test: ## Watch files and run tests on changes (requires pytest-watch)
	@echo "$(GREEN)Watching for changes...$(NC)"
	@if [ -f "$(VENV_BIN)/ptw" ]; then \
		$(VENV_BIN)/ptw; \
	else \
		echo "$(YELLOW)pytest-watch not installed. Run: pip install pytest-watch$(NC)"; \
	fi

console: shell ## Alias for shell command

.DEFAULT_GOAL := help


##@ BARB Integration

run-barb: ## Run server connected to BARB database
	@echo "$(GREEN)Starting Botswain with BARB database connection...$(NC)"
	@echo "$(YELLOW)Ensure BARB is running: cd ~/code/barb && docker-compose up -d$(NC)"
	DJANGO_SETTINGS_MODULE=botswain.settings.barb_local $(VENV_BIN)/python manage.py runserver 8002

barb-shell: ## Open Django shell connected to BARB
	@echo "$(GREEN)Opening Django shell with BARB database...$(NC)"
	DJANGO_SETTINGS_MODULE=botswain.settings.barb_local $(VENV_BIN)/python manage.py shell

barb-dbshell: ## Open PostgreSQL shell to BARB database
	@echo "$(GREEN)Opening PostgreSQL shell to BARB...$(NC)"
	DJANGO_SETTINGS_MODULE=botswain.settings.barb_local $(VENV_BIN)/python manage.py dbshell

check-barb: ## Check if BARB database is accessible
	@echo "$(GREEN)Checking BARB database connection...$(NC)"
	@psql -h localhost -p 5434 -U barb -d barb_local -c "SELECT COUNT(*) as instrument_count FROM inventory_instrument;" 2>/dev/null && \
		echo "$(GREEN)✓ BARB database is accessible$(NC)" || \
		echo "$(RED)✗ Cannot connect to BARB database. Is BARB running?$(NC)"

run-barb-prod: ## Run server connected to BARB production read-replica
	@echo "$(GREEN)Starting Botswain with BARB PRODUCTION read-replica (READ-ONLY)...$(NC)"
	@echo "$(YELLOW)⚠️  Connected to PRODUCTION data - read-only access$(NC)"
	DJANGO_SETTINGS_MODULE=botswain.settings.barb_prod_replica $(VENV_BIN)/python manage.py runserver 8002

check-barb-prod: ## Check if BARB production replica is accessible
	@echo "$(GREEN)Checking BARB production replica connection...$(NC)"
	@psql -h barb-prod-pg-replica-0.cb7xtwywa7y5.us-west-2.rds.amazonaws.com -p 5432 -U readonlyuser -d barb -c "SELECT COUNT(*) as instrument_count FROM inventory_instrument;" 2>/dev/null && \
		echo "$(GREEN)✓ BARB production replica is accessible$(NC)" || \
		echo "$(RED)✗ Cannot connect to BARB production replica$(NC)"

##@ LLM Provider Management

run-bedrock: ## Run development server with AWS Bedrock (default)
	@echo "$(GREEN)Starting Botswain with AWS Bedrock provider...$(NC)"
	LLM_PROVIDER=bedrock DJANGO_SETTINGS_MODULE=$(DJANGO_SETTINGS) $(VENV_BIN)/python manage.py runserver 8002

run-claude-cli: ## Run development server with Claude CLI (legacy)
	@echo "$(GREEN)Starting Botswain with Claude CLI provider...$(NC)"
	@echo "$(YELLOW)Note: Claude CLI is legacy - prefer Bedrock for new development$(NC)"
	LLM_PROVIDER=claude_cli DJANGO_SETTINGS_MODULE=$(DJANGO_SETTINGS) $(VENV_BIN)/python manage.py runserver 8002

check-bedrock: ## Check AWS Bedrock connection and configuration
	@echo "$(GREEN)Checking AWS Bedrock configuration...$(NC)"
	@DJANGO_SETTINGS_MODULE=$(DJANGO_SETTINGS) $(VENV_BIN)/python -c "from core.llm.factory import LLMProviderFactory; p = LLMProviderFactory.get_default(); print(f'Provider: {p.__class__.__name__}'); print(f'Model: {p.model}')" && \
		echo "$(GREEN)✓ Bedrock provider configured$(NC)" || \
		echo "$(RED)✗ Bedrock provider configuration error$(NC)"

show-provider: ## Show current LLM provider configuration
	@echo "$(BLUE)Current LLM Provider Configuration$(NC)"
	@DJANGO_SETTINGS_MODULE=$(DJANGO_SETTINGS) $(VENV_BIN)/python -c "from core.llm.factory import LLMProviderFactory; p = LLMProviderFactory.get_default(); print(f'Provider: {p.__class__.__name__}'); print(f'Model: {p.model}')"

##@ Token Usage & Cost Reporting

token-report: ## Generate token usage and cost report for all time
	@echo "$(GREEN)Generating token usage report...$(NC)"
	DJANGO_SETTINGS_MODULE=$(DJANGO_SETTINGS) $(VENV_BIN)/python manage.py token_usage_report

token-report-today: ## Generate token usage report for today
	@echo "$(GREEN)Generating token usage report for today...$(NC)"
	DJANGO_SETTINGS_MODULE=$(DJANGO_SETTINGS) $(VENV_BIN)/python manage.py token_usage_report --start-date $$(date +%Y-%m-%d)

token-report-week: ## Generate token usage report for past 7 days
	@echo "$(GREEN)Generating token usage report for past week...$(NC)"
	DJANGO_SETTINGS_MODULE=$(DJANGO_SETTINGS) $(VENV_BIN)/python manage.py token_usage_report --start-date $$(date -d '7 days ago' +%Y-%m-%d)

token-report-month: ## Generate token usage report for current month
	@echo "$(GREEN)Generating token usage report for current month...$(NC)"
	DJANGO_SETTINGS_MODULE=$(DJANGO_SETTINGS) $(VENV_BIN)/python manage.py token_usage_report --start-date $$(date +%Y-%m-01)

show-coverage: ## Open coverage report in browser
	@echo "$(GREEN)Opening coverage report...$(NC)"
	@if [ -f "htmlcov/index.html" ]; then \
		xdg-open htmlcov/index.html 2>/dev/null || open htmlcov/index.html 2>/dev/null || echo "$(YELLOW)Coverage report available at htmlcov/index.html$(NC)"; \
	else \
		echo "$(RED)No coverage report found. Run 'make test-coverage' first$(NC)"; \
	fi
