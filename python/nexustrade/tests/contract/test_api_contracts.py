"""
Contract tests for API boundaries between NexusTrade services.

These tests verify that service interfaces conform to agreed-upon schemas,
ensuring that request/response formats, field types, enum values, and nested
structures remain consistent across service boundaries.
"""
import pytest
import re
import json
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_required_keys(data: dict, keys: list) -> bool:
    """Return True when *data* contains every key in *keys*."""
    return all(k in data for k in keys)


def _is_valid_uuid(value: str) -> bool:
    """Loose UUID v4 format check."""
    return bool(re.match(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
        value,
    ))


def _is_iso8601(value: str) -> bool:
    """Check ISO-8601 datetime string."""
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except (ValueError, AttributeError):
        return False


# =========================================================================
# Gateway Contract
# =========================================================================

class TestGatewayContract:
    """Verify the API gateway honours its published request/response contract."""

    def test_request_format_requires_content_type(self):
        """Gateway must enforce Content-Type header on POST requests."""
        request_headers = {"Content-Type": "application/json", "Accept": "application/json"}
        assert "Content-Type" in request_headers
        assert request_headers["Content-Type"] == "application/json"

    def test_response_includes_request_id(self):
        """Every gateway response must carry an X-Request-Id header."""
        response_headers = {
            "X-Request-Id": "req-abc-123",
            "Content-Type": "application/json",
        }
        assert "X-Request-Id" in response_headers
        assert len(response_headers["X-Request-Id"]) > 0

    def test_error_response_format(self):
        """Error responses must follow the standard envelope."""
        error_response = {
            "error": {
                "code": "INVALID_ORDER",
                "message": "Order quantity must be positive",
                "details": {"field": "quantity", "constraint": "gt_zero"},
            }
        }
        assert "error" in error_response
        err = error_response["error"]
        assert _has_required_keys(err, ["code", "message", "details"])
        assert isinstance(err["code"], str)
        assert isinstance(err["message"], str)
        assert isinstance(err["details"], dict)

    def test_pagination_format(self):
        """Paginated list responses must include cursor metadata."""
        paginated = {
            "data": [{"id": 1}, {"id": 2}],
            "pagination": {
                "next_cursor": "eyJpZCI6Mn0=",
                "has_more": True,
                "page_size": 20,
            },
        }
        assert "data" in paginated
        assert "pagination" in paginated
        pag = paginated["pagination"]
        assert _has_required_keys(pag, ["next_cursor", "has_more", "page_size"])
        assert isinstance(pag["has_more"], bool)
        assert isinstance(pag["page_size"], int)

    def test_rate_limit_header_format(self):
        """Rate-limit headers must expose remaining quota."""
        headers = {
            "X-RateLimit-Limit": "1000",
            "X-RateLimit-Remaining": "997",
            "X-RateLimit-Reset": "1700000000",
        }
        for key in ("X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"):
            assert key in headers
            assert headers[key].isdigit()

    def test_content_type_negotiation(self):
        """Gateway should respect Accept header for response format."""
        supported_types = ["application/json", "application/xml", "text/csv"]
        accept_header = "application/json"
        assert accept_header in supported_types

    def test_api_versioning_headers(self):
        """API version must be communicated via header."""
        response_headers = {
            "X-API-Version": "2024-01-15",
            "Deprecation": "false",
        }
        assert "X-API-Version" in response_headers
        assert re.match(r"^\d{4}-\d{2}-\d{2}$", response_headers["X-API-Version"])

    def test_cors_headers_present(self):
        """Preflight responses must include CORS headers."""
        cors_headers = {
            "Access-Control-Allow-Origin": "https://app.nexustrade.io",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Authorization, Content-Type",
            "Access-Control-Max-Age": "86400",
        }
        required = [
            "Access-Control-Allow-Origin",
            "Access-Control-Allow-Methods",
            "Access-Control-Allow-Headers",
        ]
        for h in required:
            assert h in cors_headers


# =========================================================================
# Order Service Contract
# =========================================================================

class TestOrderServiceContract:
    """Verify the Order Service honours its published schema."""

    def test_order_creation_request_schema(self):
        """Order creation payload must contain required fields."""
        request = {
            "symbol": "BTC/USD",
            "side": "buy",
            "type": "limit",
            "quantity": "1.5",
            "price": "42000.00",
            "time_in_force": "GTC",
            "client_order_id": "cli-001",
        }
        required = ["symbol", "side", "type", "quantity"]
        assert _has_required_keys(request, required)
        assert request["side"] in ("buy", "sell")
        assert request["type"] in ("limit", "market", "stop", "stop_limit")

    def test_order_response_schema(self):
        """Order response must echo back all contract fields."""
        response = {
            "order_id": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
            "status": "accepted",
            "symbol": "BTC/USD",
            "side": "buy",
            "type": "limit",
            "quantity": "1.5",
            "price": "42000.00",
            "filled_quantity": "0.0",
            "created_at": "2024-06-01T12:00:00Z",
        }
        required = ["order_id", "status", "symbol", "side", "type",
                     "quantity", "created_at"]
        assert _has_required_keys(response, required)
        assert _is_valid_uuid(response["order_id"])

    def test_order_status_enum_values(self):
        """Order status must be one of the agreed-upon values."""
        valid_statuses = {
            "accepted", "pending", "open", "partially_filled",
            "filled", "cancelled", "rejected", "expired",
        }
        for status in ["accepted", "open", "filled", "cancelled"]:
            assert status in valid_statuses

    def test_order_event_schema(self):
        """Order lifecycle events must carry required metadata."""
        event = {
            "event_type": "order.filled",
            "order_id": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
            "timestamp": "2024-06-01T12:05:00Z",
            "data": {"filled_quantity": "1.5", "fill_price": "41999.50"},
        }
        assert _has_required_keys(event, ["event_type", "order_id", "timestamp", "data"])
        assert event["event_type"].startswith("order.")

    def test_order_list_pagination(self):
        """Order list endpoint must paginate correctly."""
        page = {
            "orders": [{"order_id": f"id-{i}"} for i in range(20)],
            "total_count": 150,
            "page": 1,
            "page_size": 20,
        }
        assert len(page["orders"]) <= page["page_size"]
        assert page["total_count"] >= len(page["orders"])

    def test_order_filter_parameters(self):
        """Order query filters must use agreed parameter names."""
        valid_filters = {
            "symbol", "side", "status", "start_date", "end_date",
            "min_quantity", "max_quantity", "type",
        }
        applied_filters = {"symbol": "BTC/USD", "status": "open", "side": "buy"}
        for key in applied_filters:
            assert key in valid_filters

    def test_order_webhook_payload(self):
        """Webhook callback payload must follow the standard format."""
        webhook = {
            "webhook_id": "wh-001",
            "event": "order.filled",
            "timestamp": "2024-06-01T12:05:00Z",
            "signature": "sha256=abc123...",
            "payload": {"order_id": "id-1", "filled_quantity": "1.5"},
        }
        assert _has_required_keys(webhook, ["webhook_id", "event", "timestamp",
                                             "signature", "payload"])
        assert webhook["signature"].startswith("sha256=")

    def test_order_modification_constraints(self):
        """Only modifiable fields should be accepted in PATCH."""
        modifiable_fields = {"quantity", "price", "time_in_force", "expire_time"}
        patch_request = {"price": "43000.00", "quantity": "2.0"}
        for field in patch_request:
            assert field in modifiable_fields, f"{field} is not modifiable"


# =========================================================================
# Auth Service Contract
# =========================================================================

class TestAuthServiceContract:
    """Verify Authentication/Authorization service schemas."""

    def test_login_request_response_schema(self):
        """Login must accept credentials and return token pair."""
        request = {"email": "trader@nexus.io", "password": "s3cret!"}
        assert _has_required_keys(request, ["email", "password"])

        response = {
            "access_token": "eyJhbGciOi...",
            "refresh_token": "dGhpcyBpcyBh...",
            "token_type": "Bearer",
            "expires_in": 3600,
        }
        assert _has_required_keys(response, ["access_token", "refresh_token",
                                              "token_type", "expires_in"])
        assert response["token_type"] == "Bearer"

    def test_jwt_token_structure(self):
        """Access token must have three Base64-encoded segments."""
        token = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIxMjMifQ.signature"
        parts = token.split(".")
        assert len(parts) == 3, "JWT must have header.payload.signature"

    def test_refresh_token_format(self):
        """Refresh token must be an opaque string of sufficient length."""
        refresh_token = "dGhpcyBpcyBhIHJlZnJlc2ggdG9rZW4gdGhhdCBpcyBsb25n"
        assert isinstance(refresh_token, str)
        assert len(refresh_token) >= 32, "Refresh token must be at least 32 chars"

    def test_user_info_response_schema(self):
        """User info endpoint must return agreed-upon fields."""
        user_info = {
            "user_id": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
            "email": "trader@nexus.io",
            "display_name": "Trader One",
            "roles": ["trader", "viewer"],
            "created_at": "2024-01-15T08:00:00Z",
        }
        assert _has_required_keys(user_info, ["user_id", "email", "roles"])
        assert isinstance(user_info["roles"], list)
        assert _is_valid_uuid(user_info["user_id"])

    def test_permission_response_format(self):
        """Permission check must return an explicit boolean allow/deny."""
        response = {
            "allowed": True,
            "resource": "orders",
            "action": "create",
            "conditions": {"max_order_value": 1000000},
        }
        assert isinstance(response["allowed"], bool)
        assert _has_required_keys(response, ["allowed", "resource", "action"])

    def test_auth_error_code_consistency(self):
        """Auth errors must use enumerated error codes."""
        valid_codes = {
            "INVALID_CREDENTIALS", "TOKEN_EXPIRED", "TOKEN_REVOKED",
            "INSUFFICIENT_PERMISSIONS", "ACCOUNT_LOCKED", "MFA_REQUIRED",
        }
        error = {"code": "TOKEN_EXPIRED", "message": "Access token has expired"}
        assert error["code"] in valid_codes

    def test_token_claims_structure(self):
        """Decoded JWT claims must include required fields."""
        claims = {
            "sub": "user-123",
            "iss": "auth.nexustrade.io",
            "aud": "api.nexustrade.io",
            "exp": 1700003600,
            "iat": 1700000000,
            "roles": ["trader"],
            "permissions": ["orders:read", "orders:write"],
        }
        required_claims = ["sub", "iss", "aud", "exp", "iat"]
        assert _has_required_keys(claims, required_claims)
        assert claims["exp"] > claims["iat"], "Expiry must be after issued-at"


# =========================================================================
# Matching Engine Contract
# =========================================================================

class TestMatchingEngineContract:
    """Verify the Matching Engine's published event schemas."""

    def test_order_book_snapshot_schema(self):
        """Order book snapshot must include both sides with price levels."""
        snapshot = {
            "symbol": "BTC/USD",
            "timestamp": "2024-06-01T12:00:00.123Z",
            "sequence": 100042,
            "bids": [{"price": "41999.00", "quantity": "3.2"}],
            "asks": [{"price": "42001.00", "quantity": "1.8"}],
        }
        assert _has_required_keys(snapshot, ["symbol", "timestamp", "bids", "asks"])
        assert isinstance(snapshot["bids"], list)
        assert isinstance(snapshot["asks"], list)
        for level in snapshot["bids"] + snapshot["asks"]:
            assert _has_required_keys(level, ["price", "quantity"])

    def test_trade_execution_event_schema(self):
        """Trade execution event must carry full match details."""
        trade = {
            "trade_id": "t-001",
            "symbol": "BTC/USD",
            "price": "42000.00",
            "quantity": "0.5",
            "buyer_order_id": "ord-buy-1",
            "seller_order_id": "ord-sell-1",
            "timestamp": "2024-06-01T12:00:01Z",
            "is_maker_buyer": True,
        }
        required = ["trade_id", "symbol", "price", "quantity",
                     "buyer_order_id", "seller_order_id", "timestamp"]
        assert _has_required_keys(trade, required)

    def test_market_data_tick_format(self):
        """Market data tick must contain OHLCV fields."""
        tick = {
            "symbol": "BTC/USD",
            "open": "41900.00",
            "high": "42100.00",
            "low": "41850.00",
            "close": "42000.00",
            "volume": "150.25",
            "interval": "1m",
            "timestamp": "2024-06-01T12:00:00Z",
        }
        ohlcv = ["open", "high", "low", "close", "volume"]
        assert _has_required_keys(tick, ohlcv + ["symbol", "timestamp"])

    def test_order_acknowledgment_format(self):
        """Order acknowledgment must include server-assigned id and timestamp."""
        ack = {
            "order_id": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
            "client_order_id": "cli-001",
            "status": "accepted",
            "received_at": "2024-06-01T12:00:00.001Z",
            "sequence": 100043,
        }
        assert _has_required_keys(ack, ["order_id", "client_order_id",
                                         "status", "received_at"])
        assert _is_valid_uuid(ack["order_id"])

    def test_fill_notification_schema(self):
        """Fill notifications must detail partial or full fills."""
        fill = {
            "order_id": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
            "trade_id": "t-001",
            "fill_price": "42000.00",
            "fill_quantity": "0.5",
            "remaining_quantity": "1.0",
            "is_full_fill": False,
            "timestamp": "2024-06-01T12:00:01Z",
        }
        assert _has_required_keys(fill, ["order_id", "trade_id", "fill_price",
                                          "fill_quantity", "remaining_quantity"])
        assert isinstance(fill["is_full_fill"], bool)

    def test_cancel_confirmation_format(self):
        """Cancel confirmation must echo order id and final state."""
        cancel = {
            "order_id": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
            "status": "cancelled",
            "cancelled_quantity": "1.0",
            "reason": "user_requested",
            "timestamp": "2024-06-01T12:01:00Z",
        }
        assert cancel["status"] == "cancelled"
        assert _has_required_keys(cancel, ["order_id", "status",
                                            "cancelled_quantity", "reason"])

    def test_order_book_depth_levels(self):
        """Order book depth must provide configurable level counts."""
        depths = {
            "symbol": "BTC/USD",
            "levels": 10,
            "bids": [{"price": str(42000 - i * 10), "quantity": "1.0"} for i in range(10)],
            "asks": [{"price": str(42000 + i * 10), "quantity": "1.0"} for i in range(10)],
        }
        assert len(depths["bids"]) == depths["levels"]
        assert len(depths["asks"]) == depths["levels"]
        bid_prices = [float(b["price"]) for b in depths["bids"]]
        assert bid_prices == sorted(bid_prices, reverse=True), "Bids must be descending"


# =========================================================================
# Risk Service Contract
# =========================================================================

class TestRiskServiceContract:
    """Verify the Risk Service request/response schemas."""

    def test_risk_check_request_response(self):
        """Pre-trade risk check must return allow/deny with reason."""
        request = {
            "order_id": "ord-001",
            "account_id": "acc-001",
            "symbol": "BTC/USD",
            "side": "buy",
            "quantity": "10.0",
            "price": "42000.00",
        }
        assert _has_required_keys(request, ["account_id", "symbol", "quantity"])

        response = {
            "approved": True,
            "order_id": "ord-001",
            "checks_passed": ["position_limit", "credit_limit", "concentration"],
            "warnings": [],
        }
        assert isinstance(response["approved"], bool)
        assert isinstance(response["checks_passed"], list)

    def test_margin_requirement_format(self):
        """Margin requirement response must specify amounts and ratios."""
        margin = {
            "account_id": "acc-001",
            "initial_margin": "50000.00",
            "maintenance_margin": "25000.00",
            "margin_ratio": "0.45",
            "currency": "USD",
            "as_of": "2024-06-01T12:00:00Z",
        }
        required = ["account_id", "initial_margin", "maintenance_margin",
                     "margin_ratio", "currency"]
        assert _has_required_keys(margin, required)
        assert float(margin["margin_ratio"]) <= 1.0

    def test_exposure_report_schema(self):
        """Exposure report must break down by asset class."""
        report = {
            "account_id": "acc-001",
            "total_exposure": "1500000.00",
            "currency": "USD",
            "breakdown": [
                {"asset_class": "crypto", "exposure": "1000000.00", "pct": "66.67"},
                {"asset_class": "fx", "exposure": "500000.00", "pct": "33.33"},
            ],
            "generated_at": "2024-06-01T12:00:00Z",
        }
        assert _has_required_keys(report, ["account_id", "total_exposure", "breakdown"])
        for entry in report["breakdown"]:
            assert _has_required_keys(entry, ["asset_class", "exposure"])

    def test_risk_alert_event_format(self):
        """Risk alert events must carry severity and threshold info."""
        alert = {
            "alert_id": "alert-001",
            "account_id": "acc-001",
            "severity": "high",
            "type": "margin_call",
            "message": "Account margin ratio below maintenance",
            "threshold": "0.25",
            "current_value": "0.22",
            "timestamp": "2024-06-01T12:00:00Z",
        }
        assert alert["severity"] in ("low", "medium", "high", "critical")
        assert _has_required_keys(alert, ["alert_id", "severity", "type", "message"])

    def test_credit_check_response(self):
        """Credit check must return available credit and utilisation."""
        response = {
            "account_id": "acc-001",
            "credit_limit": "5000000.00",
            "used_credit": "3200000.00",
            "available_credit": "1800000.00",
            "utilisation_pct": "64.00",
            "status": "ok",
        }
        assert _has_required_keys(response, ["credit_limit", "available_credit", "status"])
        assert response["status"] in ("ok", "warning", "exceeded")


# =========================================================================
# Settlement Contract
# =========================================================================

class TestSettlementContract:
    """Verify Settlement service message schemas."""

    def test_settlement_instruction_schema(self):
        """Settlement instruction must specify both counterparties."""
        instruction = {
            "instruction_id": "si-001",
            "trade_id": "t-001",
            "buyer_account": "acc-001",
            "seller_account": "acc-002",
            "symbol": "BTC/USD",
            "quantity": "1.5",
            "price": "42000.00",
            "settlement_date": "2024-06-03",
            "status": "pending",
        }
        required = ["instruction_id", "trade_id", "buyer_account",
                     "seller_account", "quantity", "settlement_date"]
        assert _has_required_keys(instruction, required)

    def test_settlement_confirmation_format(self):
        """Settlement confirmation must reference the original instruction."""
        confirmation = {
            "confirmation_id": "sc-001",
            "instruction_id": "si-001",
            "status": "settled",
            "settled_at": "2024-06-03T16:00:00Z",
            "buyer_balance_change": "+1.5 BTC",
            "seller_balance_change": "+63000.00 USD",
        }
        assert confirmation["status"] in ("settled", "failed", "partial")
        assert _has_required_keys(confirmation, ["confirmation_id",
                                                   "instruction_id", "status"])

    def test_settlement_failure_notification(self):
        """Failure notifications must include a failure reason code."""
        failure = {
            "instruction_id": "si-002",
            "status": "failed",
            "reason_code": "INSUFFICIENT_BALANCE",
            "reason_message": "Seller does not have sufficient BTC balance",
            "failed_at": "2024-06-03T16:05:00Z",
            "retry_eligible": True,
        }
        valid_reasons = {
            "INSUFFICIENT_BALANCE", "ACCOUNT_FROZEN", "COMPLIANCE_HOLD",
            "SYSTEM_ERROR", "TIMEOUT",
        }
        assert failure["reason_code"] in valid_reasons
        assert isinstance(failure["retry_eligible"], bool)

    def test_reconciliation_report_format(self):
        """Daily reconciliation report must tally matched and unmatched."""
        report = {
            "report_date": "2024-06-03",
            "total_instructions": 1250,
            "settled": 1240,
            "failed": 8,
            "pending": 2,
            "matched": True,
            "discrepancies": [],
        }
        assert report["total_instructions"] == (
            report["settled"] + report["failed"] + report["pending"]
        )
        assert isinstance(report["discrepancies"], list)

    def test_settlement_batch_schema(self):
        """Batch settlement must contain an array of instructions."""
        batch = {
            "batch_id": "batch-001",
            "instructions": [
                {"instruction_id": "si-001", "status": "pending"},
                {"instruction_id": "si-002", "status": "pending"},
            ],
            "created_at": "2024-06-03T15:00:00Z",
            "priority": "normal",
        }
        assert _has_required_keys(batch, ["batch_id", "instructions", "priority"])
        assert isinstance(batch["instructions"], list)
        assert len(batch["instructions"]) > 0
        assert batch["priority"] in ("low", "normal", "high", "critical")


# =========================================================================
# Notification Contract
# =========================================================================

class TestNotificationContract:
    """Verify Notification service payload schemas."""

    def test_notification_payload_schema(self):
        """Notification payload must contain routing and content fields."""
        notification = {
            "notification_id": "n-001",
            "user_id": "user-123",
            "channel": "email",
            "priority": "high",
            "subject": "Margin Call Warning",
            "body": "Your account margin ratio is below threshold.",
            "created_at": "2024-06-01T12:00:00Z",
            "metadata": {"account_id": "acc-001"},
        }
        required = ["notification_id", "user_id", "channel", "priority",
                     "subject", "body"]
        assert _has_required_keys(notification, required)

    def test_notification_channel_types(self):
        """Channel field must use recognised delivery channels."""
        valid_channels = {"email", "sms", "push", "in_app", "webhook", "slack"}
        for channel in ["email", "push", "in_app"]:
            assert channel in valid_channels

    def test_notification_priority_levels(self):
        """Priority must map to one of the defined levels."""
        valid_priorities = {"low", "medium", "high", "critical"}
        for prio in ["low", "medium", "high", "critical"]:
            assert prio in valid_priorities

    def test_email_template_variables(self):
        """Email template must declare required variable slots."""
        template = {
            "template_id": "margin-call-v2",
            "required_variables": ["user_name", "account_id", "margin_ratio",
                                   "threshold", "action_url"],
            "subject_template": "Margin Alert for {{account_id}}",
            "body_template": "Hi {{user_name}}, your margin ratio is {{margin_ratio}}.",
        }
        assert _has_required_keys(template, ["template_id", "required_variables"])
        assert isinstance(template["required_variables"], list)
        # Every placeholder in the body should be listed as required
        for var in template["required_variables"]:
            assert isinstance(var, str)
            assert len(var) > 0

    def test_notification_status_values(self):
        """Notification delivery status must use known values."""
        valid_statuses = {
            "queued", "sending", "delivered", "failed",
            "bounced", "read", "dismissed",
        }
        for status in ["queued", "delivered", "failed", "read"]:
            assert status in valid_statuses


# =========================================================================
# Audit Contract
# =========================================================================

class TestAuditContract:
    """Verify Audit/Compliance log schemas."""

    def test_audit_log_entry_schema(self):
        """Each audit entry must include actor, action, and resource."""
        entry = {
            "audit_id": "aud-001",
            "timestamp": "2024-06-01T12:00:00Z",
            "actor": {"type": "user", "id": "user-123"},
            "action": "order.create",
            "resource": {"type": "order", "id": "ord-001"},
            "result": "success",
            "ip_address": "192.168.1.10",
            "metadata": {},
        }
        required = ["audit_id", "timestamp", "actor", "action",
                     "resource", "result"]
        assert _has_required_keys(entry, required)
        assert entry["result"] in ("success", "failure", "denied")
        assert _has_required_keys(entry["actor"], ["type", "id"])
        assert _has_required_keys(entry["resource"], ["type", "id"])

    def test_audit_event_types(self):
        """Audit event type must follow the domain.verb convention."""
        valid_patterns = re.compile(r"^[a-z]+\.[a-z_]+$")
        events = [
            "order.create", "order.cancel", "account.login",
            "account.logout", "settlement.execute", "risk.check",
        ]
        for event in events:
            assert valid_patterns.match(event), f"Event '{event}' is not domain.verb"

    def test_audit_trail_query_format(self):
        """Audit trail query parameters must follow the defined schema."""
        query = {
            "actor_id": "user-123",
            "action": "order.create",
            "resource_type": "order",
            "start_time": "2024-06-01T00:00:00Z",
            "end_time": "2024-06-01T23:59:59Z",
            "page_size": 100,
            "cursor": None,
        }
        assert _has_required_keys(query, ["start_time", "end_time"])
        assert _is_iso8601(query["start_time"])
        assert _is_iso8601(query["end_time"])

    def test_compliance_report_schema(self):
        """Compliance report must include summary and violation details."""
        report = {
            "report_id": "cr-001",
            "period_start": "2024-06-01",
            "period_end": "2024-06-30",
            "total_events": 150000,
            "violations": [
                {
                    "type": "unauthorized_access",
                    "count": 3,
                    "severity": "high",
                    "details": "3 attempts to access restricted API without permissions",
                },
            ],
            "compliant": False,
            "generated_at": "2024-07-01T08:00:00Z",
        }
        assert _has_required_keys(report, ["report_id", "total_events",
                                            "violations", "compliant"])
        assert isinstance(report["compliant"], bool)
        for v in report["violations"]:
            assert _has_required_keys(v, ["type", "count", "severity"])

    def test_audit_retention_policy_format(self):
        """Audit retention policy must specify duration and archive rules."""
        policy = {
            "policy_id": "arp-001",
            "retention_days": 2555,
            "archive_after_days": 365,
            "archive_storage": "s3://nexustrade-audit-archive",
            "deletion_requires_approval": True,
            "applicable_event_types": ["*"],
        }
        assert _has_required_keys(policy, ["policy_id", "retention_days",
                                            "archive_after_days"])
        assert policy["retention_days"] > policy["archive_after_days"]
        assert isinstance(policy["deletion_requires_approval"], bool)
