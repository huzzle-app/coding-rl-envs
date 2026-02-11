# ClearLedger - Greenfield Implementation Tasks

## Overview

ClearLedger supports 3 greenfield implementation tasks requiring new module creation from scratch. Each task implements core financial ledger functionality following existing architectural patterns, with detailed interface contracts and integration requirements.

## Environment

- **Language**: Ruby
- **Infrastructure**: 12 services (settlement, reconciliation, risk, compliance, audit, ledger)
- **Difficulty**: Ultra-Principal (8-tier reward threshold)

## Tasks

### Task 1: Intercompany Elimination Engine (Greenfield Implementation)

Implement an intercompany elimination engine that identifies and removes internal transactions between related entities during consolidated reporting. The module must identify transaction pairs, calculate elimination amounts with tolerance handling, generate balanced journal entries, and validate elimination completeness.

**Interface**: `ClearLedger::Core::Intercompany` with module functions:
- `identify_pairs(transactions, entity_map)` — Find matching intercompany transaction pairs
- `elimination_amount(pair, tolerance_bps)` — Calculate elimination amount with tolerance
- `generate_eliminations(pairs)` — Produce balanced journal entries
- `unmatched_transactions(transactions, eliminations)` — Return transactions requiring manual review
- `related_entities?(entity_a, entity_b, entity_map)` — Determine if entities belong to same group
- `elimination_ratio(eliminated, total_intercompany)` — Calculate elimination ratio for compliance
- `net_exposure(transactions, eliminations)` — Calculate remaining net exposure
- `eliminations_balanced?(eliminations)` — Validate journal entries balance to zero

**Location**: `lib/clearledger/core/intercompany.rb`

**Tests**: Minimum 15 test cases in `tests/unit/intercompany_test.rb` covering pair identification, elimination generation, edge cases, and integration with Settlement module.

### Task 2: Multi-Currency Translator (Greenfield Implementation)

Implement a multi-currency translation engine supporting currency conversion with configurable exchange rates, triangulation through base currencies, and temporal rate selection for historical reporting. The module must handle batch translation, gain/loss calculation, weighted average rates, and staleness detection.

**Interface**: `ClearLedger::Core::Currency` with module functions:
- `convert(amount, from_currency, to_currency, rates)` — Direct currency conversion
- `triangulate(amount, from_currency, to_currency, rates, base_currency)` — Conversion through base currency
- `rate_for_date(from_currency, to_currency, date, rate_history)` — Select historical rate
- `translate_batch(entries, target_currency, rates)` — Translate batch of entries
- `translation_gain_loss(original_amount, original_rate, current_rate)` — Calculate unrealized gain/loss
- `valid_currency_code?(code)` — Validate ISO 4217 currency codes
- `inverse_rate(rate)` — Calculate inverse exchange rate
- `rate_key(from_currency, to_currency)` — Generate normalized rate key
- `weighted_average_rate(transactions)` — Calculate weighted average rate
- `rate_stale?(rate_timestamp, max_age_seconds, now)` — Detect stale rates

**Location**: `lib/clearledger/core/currency.rb`

**Tests**: Minimum 18 test cases in `tests/unit/currency_test.rb` covering direct conversion, triangulation, historical rates, batch translation, gain/loss calculations, and edge cases.

### Task 3: Financial Report Generator (Greenfield Implementation)

Implement a financial report generator producing structured reports (trial balance, balance sheet, income statement) from ledger data. The module must support configurable reporting periods, comparative analysis, account categorization, and validation of report completeness.

**Interface**: `ClearLedger::Core::Reporting` with module functions:
- `trial_balance(entries, as_of_date)` — Generate trial balance with balance validation
- `balance_sheet(entries, account_map, as_of_date)` — Categorize accounts into assets, liabilities, equity
- `income_statement(entries, account_map, start_date, end_date)` — Generate revenue and expense statement
- `comparative_report(current_data, prior_data)` — Generate period-over-period analysis
- `account_balance(entries, account)` — Calculate net balance for account
- `group_by_account(entries)` — Group entries by account name
- `filter_by_period(entries, start_date, end_date)` — Filter entries to date range
- `balanced?(trial_balance, tolerance)` — Validate trial balance (debits == credits)
- `financial_ratios(balance_sheet, income_statement)` — Calculate key ratios
- `format_report(report_type, data, metadata)` — Format report for output
- `missing_accounts(report, required_accounts)` — Validate report completeness

**Location**: `lib/clearledger/core/reporting.rb`

**Tests**: Minimum 20 test cases in `tests/unit/reporting_test.rb` covering trial balance generation, balance sheet categorization, income statement calculations, comparative analysis, period filtering, and edge cases.

## Getting Started

```bash
ruby -Ilib -Itests tests/run_all.rb
```

## Success Criteria

All implementations must:

1. Pass minimum test case counts in `tests/unit/{intercompany,currency,reporting}_test.rb`
2. Follow module structure with `module_function` and `frozen_string_literal: true`
3. Integrate with existing modules (registration in `lib/clearledger.rb`)
4. Handle edge cases with appropriate defaults (empty inputs, zero amounts)
5. Maintain monetary precision using `.round(6)`
6. Implement full interface contract with no `NotImplementedError` remaining

Acceptance criteria and detailed requirements defined in [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md).
