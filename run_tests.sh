#!/bin/bash
# Run tests for KOMEK DAMU Bot

echo "================================"
echo "KOMEK DAMU Bot - Test Runner"
echo "================================"
echo ""

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo "Installing pytest..."
    pip install pytest pytest-asyncio pytest-cov
fi

# Run all tests
echo "Running tests..."
pytest -v --tb=short "$@"

# Show coverage if pytest-cov is available
if python -c "import pytest_cov" 2>/dev/null; then
    echo ""
    echo "Running with coverage..."
    pytest --cov=app --cov-report=term-missing
fi
