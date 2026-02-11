#!/bin/bash

set -e

SERVICES="gateway auth catalog inventory orders payments shipping search notifications analytics"
TOTAL_PASSED=0
TOTAL_FAILED=0
TOTAL_PENDING=0

echo "=========================================="
echo "ShopStream - Running All Service Tests"
echo "=========================================="

for service in $SERVICES; do
    echo ""
    echo "Testing $service service..."
    echo "------------------------------------------"

    output=$(docker compose exec -T $service bundle exec rspec --format json 2>/dev/null || true)

    passed=$(echo "$output" | grep -o '"example_count":[0-9]*' | grep -o '[0-9]*' | head -1 || echo "0")
    failed=$(echo "$output" | grep -o '"failure_count":[0-9]*' | grep -o '[0-9]*' | head -1 || echo "0")
    pending=$(echo "$output" | grep -o '"pending_count":[0-9]*' | grep -o '[0-9]*' | head -1 || echo "0")

    actual_passed=$((passed - failed - pending))

    echo "$service: $actual_passed passed, $failed failed, $pending pending"

    TOTAL_PASSED=$((TOTAL_PASSED + actual_passed))
    TOTAL_FAILED=$((TOTAL_FAILED + failed))
    TOTAL_PENDING=$((TOTAL_PENDING + pending))
done

echo ""
echo "=========================================="
echo "Total Results"
echo "=========================================="
echo "Passed:  $TOTAL_PASSED"
echo "Failed:  $TOTAL_FAILED"
echo "Pending: $TOTAL_PENDING"
echo ""

if [ $TOTAL_FAILED -eq 0 ]; then
    echo "All tests passed!"
    exit 0
else
    echo "Some tests failed."
    exit 1
fi
