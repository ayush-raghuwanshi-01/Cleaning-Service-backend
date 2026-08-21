#!/bin/bash
# One-shot API test: logs in as admin and hits every endpoint.
# Usage: ./scripts/test_all_endpoints.sh   (expects backend on :8000)
BASE="http://localhost:8000/api/v1"

echo "== Login =="
LOGIN=$(curl -s -X POST "$BASE/auth/login" -H "Content-Type: application/json" \
  -d '{"identifier":"9999999999","password":"AdminPassword123!"}')
TOKEN=$(echo "$LOGIN" | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
if [ -z "$TOKEN" ]; then echo "LOGIN FAILED: $LOGIN"; exit 1; fi
AUTH="Authorization: Bearer $TOKEN"
echo "OK"

PASS=0; FAIL=0
check() {
  local label="$1"; shift
  local code=$(curl -s -o /tmp/_resp -w "%{http_code}" "$@")
  if [ "$code" = "200" ] || [ "$code" = "201" ] || [ "$code" = "204" ]; then
    echo "[PASS] $label -> $code"; PASS=$((PASS+1))
  else
    echo "[FAIL] $label -> $code ($(head -c 100 /tmp/_resp))"; FAIL=$((FAIL+1))
  fi
}

check "GET /auth/me"                    -H "$AUTH" "$BASE/auth/me"
check "GET /services"                   "$BASE/services"
check "GET /service-areas"              "$BASE/service-areas"
check "GET /admin/orders"               -H "$AUTH" "$BASE/admin/orders"
check "GET /admin/orders?page=1"        -H "$AUTH" "$BASE/admin/orders?page=1&page_size=5"
check "GET /admin/stats"                -H "$AUTH" "$BASE/admin/stats"
check "GET /admin/staff"                -H "$AUTH" "$BASE/admin/staff"
check "GET /admin/audit-logs"           -H "$AUTH" "$BASE/admin/audit-logs"
check "GET /admin/dashboard-alerts"     -H "$AUTH" "$BASE/admin/dashboard-alerts"
check "GET /admin/recurring-orders"     -H "$AUTH" "$BASE/admin/recurring-orders"
check "GET /admin/whatsapp-config"      -H "$AUTH" "$BASE/admin/whatsapp-config"
check "GET /admin/reports/revenue-summary" -H "$AUTH" "$BASE/admin/reports/revenue-summary?start_date=2026-01-01&end_date=2026-12-31"
check "GET /admin/reports/csv"          -H "$AUTH" "$BASE/admin/reports/csv?start_date=2026-01-01&end_date=2026-12-31"

echo ""
echo "RESULT: $PASS passed, $FAIL failed"
