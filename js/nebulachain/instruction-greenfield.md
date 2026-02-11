# NebulaChain - Greenfield Implementation Tasks

## Overview

NebulaChain supports 3 greenfield implementation tasks requiring new modules from scratch. Each task implements a new service for the blockchain platform following existing architectural patterns in core modules, service layer, and shared contracts. Implementations must integrate with the existing test infrastructure and support the 9,213+ test suite.

## Environment

- **Language**: JavaScript
- **Infrastructure**: Three-layer architecture with core modules, service layer, and shared contracts
- **Difficulty**: Apex-Principal
- **Test Framework**: node:test

## Tasks

### Task 1: Smart Contract Validator Service

Implement a Smart Contract Validator service that validates, compiles, and verifies smart contract bytecode before deployment. The validator ensures contracts meet security standards, gas limits, and compliance requirements.

**Key Interfaces**:
- **SmartContract** class: Contract submission with bytecode and metadata, estimateGas(), isWithinSizeLimit(), toJSON()/fromJSON()
- **ValidationResult** class: Validation outcome with errors, warnings, and metrics
- **Contract Validator** core module: validateOpcodes(), computeComplexity(), estimateDeploymentGas(), verifySourceHash(), detectReentrancy()
- **Validator Service**: validateContract(), batchValidate(), detectUpgradeability(), generateComplianceReport(), queueForDeployment()

**Module Locations**:
- Core: `src/core/contract-validator.js`
- Service: `services/validator/service.js`
- Models: `src/models/smart-contract.js`

**Key Requirements**:
- Validate bytecode for forbidden opcodes (SELFDESTRUCT, DELEGATECALL, CALLCODE)
- Compute cyclomatic complexity from bytecode (1-100 score)
- Estimate gas costs using configurable GAS_COSTS table
- Verify source hash using SHA-256
- Detect reentrancy vulnerability patterns
- Support configurable validation options (maxGas, maxComplexity, strict mode)
- Integrate with service contracts registry

### Task 2: Block Explorer Backend Service

Implement a Block Explorer Backend service providing queryable access to blockchain state, transaction history, and block metadata. External applications can browse and analyze the NebulaChain ledger through this service.

**Key Interfaces**:
- **Block** class: Block metadata with height, hash, parentHash, timestamp, transactions, validator. Methods: computeMerkleRoot(), isGenesis(), sizeBytes(), toJSON()/fromJSON()
- **Transaction** class: Transaction record with hash, from, to, value, gasUsed, status. Methods: isContractCreation(), calculateFee()
- **BlockIndex** core class: In-memory index with addBlock(), getByHeight(), getByHash(), latestHeight(), getRange()
- **Explorer Core** functions: searchByAddress(), computeChainStats(), findTransaction(), calculateBalance(), detectReorg()
- **Explorer Service**: queryBlocks(), getAddressHistory(), getBlockDetails(), searchTransactions(), getNetworkStats()

**Module Locations**:
- Core: `src/core/block-explorer.js`
- Service: `services/explorer/service.js`
- Models: `src/models/block.js`

**Key Requirements**:
- Implement efficient block indexing with O(1) lookup by height/hash
- Support pagination with offset/limit for large result sets
- Search transactions by address with direction filtering (from/to/both)
- Calculate address balances from transaction history
- Compute chain statistics (totalTx, avgBlockTime, avgTxPerBlock)
- Detect chain reorganizations (forks) with depth tracking
- Return structured results with metadata (total, pages, count)

### Task 3: Token Transfer Service

Implement a Token Transfer Service managing fungible token operations including transfers, allowances, and balance tracking. Provides ERC-20-like functionality for the NebulaChain platform.

**Key Interfaces**:
- **Token** class: Token metadata with symbol, name, decimals, totalSupply, owner. Methods: formatAmount(), parseAmount()
- **TransferRequest** class: Transfer payload with from, to, amount, nonce. Methods: validate(), computeHash()
- **Allowance** class: Spender authorization with amount and expiration. Methods: isExpired(), canSpend()
- **TokenLedger** core class: Balance tracking with registerToken(), getToken(), balanceOf(), credit(), debit(), getHolders()
- **Token Core** functions: executeTransfer(), batchTransfer(), validateTransfer(), circulatingSupply()
- **Token Service**: transfer(), approve(), transferFrom(), getAllowance(), getTokenInfo()

**Module Locations**:
- Core: `src/core/token-ledger.js`
- Service: `services/token/service.js`
- Models: `src/models/token.js`

**Key Requirements**:
- Use string representation for large numeric values (avoid floating point)
- Implement idempotency with nonce checking
- Support HMAC signatures for authorization
- Execute atomic batch transfers (all-or-nothing semantics)
- Track allowance expiration and spending limits
- Support allowance delegation (approve/transferFrom pattern)
- Calculate circulating supply excluding burn address
- Handle edge cases: zero-value transfers, self-transfers, insufficient balance

## Getting Started

```bash
npm test
```

Verify that the test suite runs. New implementations should initially have failing tests that pass as the modules are completed.

## Success Criteria

All acceptance criteria from [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) must be met:

1. **Unit Tests** must pass for all core functions and classes
2. **Service Tests** must pass for all service-layer functions
3. **Integration** with existing service contracts registry
4. **No modifications** to test files or existing source code
5. **Architectural alignment** with existing patterns (Object.freeze for constants, structured result objects, Map-based indexing)

Each task includes specific acceptance criteria covering edge cases, error paths, and integration requirements.
