# NebulaChain - Greenfield Implementation Tasks

These tasks require implementing NEW modules from scratch for the NebulaChain blockchain/distributed ledger platform. Each task must follow existing architectural patterns found in `src/core/`, `services/`, and `shared/contracts/`.

---

## Task 1: Smart Contract Validator Service

### Overview

Implement a Smart Contract Validator service that validates, compiles, and verifies smart contract bytecode before deployment to the NebulaChain ledger. The validator ensures contracts meet security standards, gas limits, and compliance requirements.

### Module Location

- Core module: `src/core/contract-validator.js`
- Service: `services/validator/service.js`
- Models: `src/models/smart-contract.js`

### Interface Contract

```javascript
// src/models/smart-contract.js
'use strict';

/**
 * Represents a smart contract submission for validation
 */
class SmartContract {
  /**
   * @param {string} contractId - Unique contract identifier
   * @param {string} bytecode - Compiled contract bytecode (hex string)
   * @param {string} sourceHash - SHA-256 hash of source code
   * @param {Object} metadata - Contract metadata
   */
  constructor(contractId, bytecode, sourceHash, metadata) {}

  /**
   * Compute estimated gas cost for deployment
   * @returns {number} Estimated gas units
   */
  estimateGas() {}

  /**
   * Check if contract exceeds maximum bytecode size
   * @param {number} maxBytes - Maximum allowed bytecode size (default: 24576)
   * @returns {boolean} True if within limits
   */
  isWithinSizeLimit(maxBytes) {}

  /**
   * Serialize contract for storage
   * @returns {Object} JSON-serializable representation
   */
  toJSON() {}

  /**
   * Deserialize from storage
   * @param {Object} obj - JSON object
   * @returns {SmartContract}
   */
  static fromJSON(obj) {}
}

/**
 * Validation result for a contract
 */
class ValidationResult {
  /**
   * @param {string} contractId - Contract being validated
   * @param {boolean} valid - Whether contract passed validation
   * @param {string[]} errors - List of validation errors
   * @param {string[]} warnings - List of validation warnings
   * @param {Object} metrics - Validation metrics (gas, size, complexity)
   */
  constructor(contractId, valid, errors, warnings, metrics) {}
}

module.exports = { SmartContract, ValidationResult };
```

```javascript
// src/core/contract-validator.js
'use strict';

/**
 * Opcodes that are forbidden in contracts (security risk)
 */
const FORBIDDEN_OPCODES = Object.freeze([
  'SELFDESTRUCT',
  'DELEGATECALL',
  'CALLCODE',
]);

/**
 * Gas costs per opcode category
 */
const GAS_COSTS = Object.freeze({
  arithmetic: 3,
  storage_read: 200,
  storage_write: 5000,
  call: 700,
  create: 32000,
});

/**
 * Validate bytecode for forbidden opcodes
 * @param {string} bytecode - Contract bytecode (hex string)
 * @returns {{safe: boolean, violations: string[]}}
 */
function validateOpcodes(bytecode) {}

/**
 * Compute cyclomatic complexity from bytecode
 * @param {string} bytecode - Contract bytecode
 * @returns {number} Complexity score (1-100)
 */
function computeComplexity(bytecode) {}

/**
 * Estimate total gas for contract deployment
 * @param {string} bytecode - Contract bytecode
 * @param {Object} gasCosts - Gas cost table (default: GAS_COSTS)
 * @returns {number} Total gas estimate
 */
function estimateDeploymentGas(bytecode, gasCosts) {}

/**
 * Verify source hash matches bytecode
 * @param {string} bytecode - Contract bytecode
 * @param {string} expectedHash - Expected SHA-256 hash
 * @returns {boolean} True if hash matches
 */
function verifySourceHash(bytecode, expectedHash) {}

/**
 * Check for reentrancy vulnerability patterns
 * @param {string} bytecode - Contract bytecode
 * @returns {{vulnerable: boolean, patterns: string[]}}
 */
function detectReentrancy(bytecode) {}

module.exports = {
  FORBIDDEN_OPCODES,
  GAS_COSTS,
  validateOpcodes,
  computeComplexity,
  estimateDeploymentGas,
  verifySourceHash,
  detectReentrancy,
};
```

```javascript
// services/validator/service.js
'use strict';

/**
 * Validate a smart contract for deployment eligibility
 * @param {SmartContract} contract - Contract to validate
 * @param {Object} options - Validation options
 * @param {number} options.maxGas - Maximum allowed gas (default: 3000000)
 * @param {number} options.maxComplexity - Maximum complexity score (default: 50)
 * @param {boolean} options.strict - Enable strict mode (default: false)
 * @returns {ValidationResult}
 */
function validateContract(contract, options) {}

/**
 * Batch validate multiple contracts
 * @param {SmartContract[]} contracts - Contracts to validate
 * @param {Object} options - Validation options
 * @returns {ValidationResult[]}
 */
function batchValidate(contracts, options) {}

/**
 * Check if contract is upgradeable (proxy pattern detected)
 * @param {SmartContract} contract - Contract to check
 * @returns {{upgradeable: boolean, proxyType: string|null}}
 */
function detectUpgradeability(contract) {}

/**
 * Generate compliance report for auditing
 * @param {ValidationResult[]} results - Validation results
 * @returns {{passed: number, failed: number, warnings: number, details: Object[]}}
 */
function generateComplianceReport(results) {}

/**
 * Register contract in pending deployment queue
 * @param {SmartContract} contract - Validated contract
 * @param {string} deployerAddress - Deployer wallet address
 * @returns {{queued: boolean, position: number, estimatedBlock: number}}
 */
function queueForDeployment(contract, deployerAddress) {}

module.exports = {
  validateContract,
  batchValidate,
  detectUpgradeability,
  generateComplianceReport,
  queueForDeployment,
};
```

### Required Data Structures

1. **SmartContract** - Contract submission with bytecode and metadata
2. **ValidationResult** - Validation outcome with errors/warnings
3. **OpcodeViolation** - Details of forbidden opcode usage
4. **ComplianceReport** - Aggregated validation statistics

### Architectural Patterns to Follow

- Use `Object.freeze()` for immutable constants (see `src/core/policy.js`)
- Return structured result objects with `{success, reason}` pattern (see `services/security/service.js`)
- Use `node:crypto` for hashing (see `src/models/dispatch-ticket.js`)
- Export flat functions and classes (see `services/gateway/service.js`)

### Acceptance Criteria

1. **Unit Tests** - Create `tests/unit/contract-validator.test.js`:
   - Test `validateOpcodes()` with safe and unsafe bytecode
   - Test `computeComplexity()` returns valid range
   - Test `estimateDeploymentGas()` calculation accuracy
   - Test `verifySourceHash()` with matching and mismatched hashes
   - Test `detectReentrancy()` pattern detection

2. **Service Tests** - Create `tests/services/validator.service.test.js`:
   - Test `validateContract()` with valid/invalid contracts
   - Test `batchValidate()` processes multiple contracts
   - Test `generateComplianceReport()` aggregation
   - Test `queueForDeployment()` with validated contracts

3. **Integration** - Contracts entry in `shared/contracts/contracts.js`:
   ```javascript
   validator: {
     id: 'validator',
     port: 8098,
     healthPath: '/health',
     version: '1.0.0',
     dependencies: ['security', 'policy'],
   }
   ```

4. **Test Command**: `npm test`

5. **Coverage Requirements**:
   - All exported functions must have at least one test
   - Edge cases: empty bytecode, oversized contracts, null inputs
   - Error paths: invalid opcodes, hash mismatches, complexity exceeded

---

## Task 2: Block Explorer Backend Service

### Overview

Implement a Block Explorer Backend service that provides queryable access to blockchain state, transaction history, and block metadata. This service enables external applications to browse and analyze the NebulaChain ledger.

### Module Location

- Core module: `src/core/block-explorer.js`
- Service: `services/explorer/service.js`
- Models: `src/models/block.js`

### Interface Contract

```javascript
// src/models/block.js
'use strict';

/**
 * Represents a block in the NebulaChain ledger
 */
class Block {
  /**
   * @param {number} height - Block height (0-indexed)
   * @param {string} hash - Block hash (SHA-256)
   * @param {string} parentHash - Previous block hash
   * @param {number} timestamp - Unix timestamp (ms)
   * @param {Transaction[]} transactions - Transactions in block
   * @param {string} validator - Validator address that produced block
   */
  constructor(height, hash, parentHash, timestamp, transactions, validator) {}

  /**
   * Compute Merkle root of transactions
   * @returns {string} Merkle root hash
   */
  computeMerkleRoot() {}

  /**
   * Check if block is genesis block
   * @returns {boolean}
   */
  isGenesis() {}

  /**
   * Get block size in bytes
   * @returns {number}
   */
  sizeBytes() {}

  /**
   * Serialize for storage
   * @returns {Object}
   */
  toJSON() {}

  /**
   * Deserialize from storage
   * @param {Object} obj
   * @returns {Block}
   */
  static fromJSON(obj) {}
}

/**
 * Represents a transaction in the ledger
 */
class Transaction {
  /**
   * @param {string} txHash - Transaction hash
   * @param {string} from - Sender address
   * @param {string} to - Recipient address (null for contract creation)
   * @param {string} value - Value transferred (in smallest unit)
   * @param {number} gasUsed - Gas consumed
   * @param {string} status - 'success' | 'failed' | 'pending'
   */
  constructor(txHash, from, to, value, gasUsed, status) {}

  /**
   * Check if transaction is contract creation
   * @returns {boolean}
   */
  isContractCreation() {}

  /**
   * Calculate transaction fee
   * @param {number} gasPrice - Gas price per unit
   * @returns {string} Fee in smallest unit
   */
  calculateFee(gasPrice) {}
}

module.exports = { Block, Transaction };
```

```javascript
// src/core/block-explorer.js
'use strict';

/**
 * In-memory block index for fast lookups
 */
class BlockIndex {
  constructor() {}

  /**
   * Add block to index
   * @param {Block} block
   */
  addBlock(block) {}

  /**
   * Get block by height
   * @param {number} height
   * @returns {Block|null}
   */
  getByHeight(height) {}

  /**
   * Get block by hash
   * @param {string} hash
   * @returns {Block|null}
   */
  getByHash(hash) {}

  /**
   * Get latest block height
   * @returns {number}
   */
  latestHeight() {}

  /**
   * Get blocks in range (inclusive)
   * @param {number} startHeight
   * @param {number} endHeight
   * @returns {Block[]}
   */
  getRange(startHeight, endHeight) {}
}

/**
 * Search transactions by address
 * @param {Transaction[]} transactions - Transactions to search
 * @param {string} address - Address to find
 * @param {string} direction - 'from' | 'to' | 'both'
 * @returns {Transaction[]}
 */
function searchByAddress(transactions, address, direction) {}

/**
 * Compute chain statistics
 * @param {Block[]} blocks - Blocks to analyze
 * @returns {{totalTx: number, avgBlockTime: number, avgTxPerBlock: number}}
 */
function computeChainStats(blocks) {}

/**
 * Find transaction by hash across blocks
 * @param {BlockIndex} index - Block index
 * @param {string} txHash - Transaction hash
 * @returns {{block: Block, transaction: Transaction}|null}
 */
function findTransaction(index, txHash) {}

/**
 * Calculate address balance from transaction history
 * @param {Transaction[]} transactions - All transactions for address
 * @param {string} address - Target address
 * @returns {string} Balance in smallest unit
 */
function calculateBalance(transactions, address) {}

/**
 * Detect chain reorganization (fork)
 * @param {Block[]} mainChain - Current main chain
 * @param {Block[]} newBlocks - Incoming blocks
 * @returns {{reorg: boolean, forkHeight: number, depth: number}}
 */
function detectReorg(mainChain, newBlocks) {}

module.exports = {
  BlockIndex,
  searchByAddress,
  computeChainStats,
  findTransaction,
  calculateBalance,
  detectReorg,
};
```

```javascript
// services/explorer/service.js
'use strict';

/**
 * Query blocks with pagination
 * @param {Object} query - Query parameters
 * @param {number} query.page - Page number (1-indexed)
 * @param {number} query.limit - Results per page (max 100)
 * @param {string} query.order - 'asc' | 'desc'
 * @returns {{blocks: Block[], total: number, page: number, pages: number}}
 */
function queryBlocks(query) {}

/**
 * Get transaction history for address
 * @param {string} address - Wallet address
 * @param {Object} options - Query options
 * @param {number} options.limit - Max results (default: 50)
 * @param {number} options.offset - Skip N results
 * @param {string} options.type - 'sent' | 'received' | 'all'
 * @returns {{transactions: Transaction[], total: number}}
 */
function getAddressHistory(address, options) {}

/**
 * Get block details with transaction summaries
 * @param {string} hashOrHeight - Block hash or height
 * @returns {{block: Block, txSummary: Object}|null}
 */
function getBlockDetails(hashOrHeight) {}

/**
 * Search transactions by various criteria
 * @param {Object} criteria - Search criteria
 * @param {string} criteria.address - Address involved
 * @param {number} criteria.minValue - Minimum transfer value
 * @param {number} criteria.startTime - Start timestamp
 * @param {number} criteria.endTime - End timestamp
 * @returns {Transaction[]}
 */
function searchTransactions(criteria) {}

/**
 * Get network overview statistics
 * @returns {{latestBlock: number, totalTx: number, avgBlockTime: number, validators: number}}
 */
function getNetworkStats() {}

module.exports = {
  queryBlocks,
  getAddressHistory,
  getBlockDetails,
  searchTransactions,
  getNetworkStats,
};
```

### Required Data Structures

1. **Block** - Immutable block with transactions and metadata
2. **Transaction** - Individual transaction record
3. **BlockIndex** - Efficient block lookup structure
4. **AddressHistory** - Transaction history for an address

### Architectural Patterns to Follow

- Use `Map` for indexing (see `src/core/resilience.js` CheckpointManager)
- Implement pagination with offset/limit pattern
- Return structured results with metadata (total, pages)
- Use BigInt or string for large numeric values

### Acceptance Criteria

1. **Unit Tests** - Create `tests/unit/block-explorer.test.js`:
   - Test `BlockIndex` CRUD operations
   - Test `searchByAddress()` with various directions
   - Test `computeChainStats()` calculation accuracy
   - Test `calculateBalance()` with sent/received transactions
   - Test `detectReorg()` fork detection

2. **Model Tests** - Create `tests/unit/block.test.js`:
   - Test `Block` construction and serialization
   - Test `computeMerkleRoot()` determinism
   - Test `Transaction` fee calculation
   - Test edge cases: genesis block, empty transactions

3. **Service Tests** - Create `tests/services/explorer.service.test.js`:
   - Test `queryBlocks()` pagination
   - Test `getAddressHistory()` filtering
   - Test `searchTransactions()` criteria matching

4. **Integration** - Contracts entry:
   ```javascript
   explorer: {
     id: 'explorer',
     port: 8099,
     healthPath: '/health',
     version: '1.0.0',
     dependencies: ['gateway'],
   }
   ```

5. **Test Command**: `npm test`

---

## Task 3: Token Transfer Service

### Overview

Implement a Token Transfer Service that manages fungible token operations including transfers, allowances, and balance tracking. This service provides ERC-20-like functionality for the NebulaChain platform.

### Module Location

- Core module: `src/core/token-ledger.js`
- Service: `services/token/service.js`
- Models: `src/models/token.js`

### Interface Contract

```javascript
// src/models/token.js
'use strict';

/**
 * Represents a fungible token on NebulaChain
 */
class Token {
  /**
   * @param {string} tokenId - Unique token identifier
   * @param {string} symbol - Token symbol (e.g., 'NBL')
   * @param {string} name - Full token name
   * @param {number} decimals - Decimal places (default: 18)
   * @param {string} totalSupply - Total supply in smallest unit
   * @param {string} owner - Token contract owner address
   */
  constructor(tokenId, symbol, name, decimals, totalSupply, owner) {}

  /**
   * Format amount with proper decimals
   * @param {string} amount - Raw amount in smallest unit
   * @returns {string} Human-readable amount
   */
  formatAmount(amount) {}

  /**
   * Parse human-readable amount to raw units
   * @param {string} humanAmount - Human-readable amount
   * @returns {string} Raw amount in smallest unit
   */
  parseAmount(humanAmount) {}
}

/**
 * Represents a token transfer request
 */
class TransferRequest {
  /**
   * @param {string} tokenId - Token being transferred
   * @param {string} from - Sender address
   * @param {string} to - Recipient address
   * @param {string} amount - Amount in smallest unit
   * @param {string} nonce - Unique nonce for idempotency
   */
  constructor(tokenId, from, to, amount, nonce) {}

  /**
   * Validate transfer request fields
   * @returns {{valid: boolean, reason: string|null}}
   */
  validate() {}

  /**
   * Compute transfer hash for signing
   * @returns {string} SHA-256 hash
   */
  computeHash() {}
}

/**
 * Represents an allowance grant
 */
class Allowance {
  /**
   * @param {string} tokenId - Token for allowance
   * @param {string} owner - Token owner granting allowance
   * @param {string} spender - Address allowed to spend
   * @param {string} amount - Maximum spendable amount
   * @param {number} expiresAt - Expiration timestamp (0 = never)
   */
  constructor(tokenId, owner, spender, amount, expiresAt) {}

  /**
   * Check if allowance is expired
   * @param {number} now - Current timestamp
   * @returns {boolean}
   */
  isExpired(now) {}

  /**
   * Check if amount can be spent
   * @param {string} requestedAmount
   * @returns {boolean}
   */
  canSpend(requestedAmount) {}
}

module.exports = { Token, TransferRequest, Allowance };
```

```javascript
// src/core/token-ledger.js
'use strict';

/**
 * In-memory token balance ledger
 */
class TokenLedger {
  constructor() {}

  /**
   * Register a new token
   * @param {Token} token
   * @returns {boolean} True if registered, false if exists
   */
  registerToken(token) {}

  /**
   * Get token by ID
   * @param {string} tokenId
   * @returns {Token|null}
   */
  getToken(tokenId) {}

  /**
   * Get balance for address
   * @param {string} tokenId
   * @param {string} address
   * @returns {string} Balance in smallest unit
   */
  balanceOf(tokenId, address) {}

  /**
   * Credit balance (mint or receive)
   * @param {string} tokenId
   * @param {string} address
   * @param {string} amount
   * @returns {string} New balance
   */
  credit(tokenId, address, amount) {}

  /**
   * Debit balance (burn or send)
   * @param {string} tokenId
   * @param {string} address
   * @param {string} amount
   * @returns {{success: boolean, balance: string, reason: string|null}}
   */
  debit(tokenId, address, amount) {}

  /**
   * Get all holders for a token
   * @param {string} tokenId
   * @returns {{address: string, balance: string}[]}
   */
  getHolders(tokenId) {}
}

/**
 * Execute atomic transfer between addresses
 * @param {TokenLedger} ledger
 * @param {TransferRequest} request
 * @returns {{success: boolean, txHash: string, reason: string|null}}
 */
function executeTransfer(ledger, request) {}

/**
 * Execute batch transfers atomically
 * @param {TokenLedger} ledger
 * @param {TransferRequest[]} requests
 * @returns {{success: boolean, completed: number, failed: number, results: Object[]}}
 */
function batchTransfer(ledger, requests) {}

/**
 * Check transfer would succeed without executing
 * @param {TokenLedger} ledger
 * @param {TransferRequest} request
 * @returns {{valid: boolean, reason: string|null}}
 */
function validateTransfer(ledger, request) {}

/**
 * Calculate total circulating supply (excluding burn address)
 * @param {TokenLedger} ledger
 * @param {string} tokenId
 * @param {string} burnAddress - Address considered "burned"
 * @returns {string} Circulating supply
 */
function circulatingSupply(ledger, tokenId, burnAddress) {}

module.exports = {
  TokenLedger,
  executeTransfer,
  batchTransfer,
  validateTransfer,
  circulatingSupply,
};
```

```javascript
// services/token/service.js
'use strict';

/**
 * Process transfer with signature verification
 * @param {TransferRequest} request
 * @param {string} signature - HMAC signature
 * @param {string} secret - Signing secret
 * @returns {{success: boolean, txHash: string, reason: string|null}}
 */
function transfer(request, signature, secret) {}

/**
 * Grant allowance to spender
 * @param {string} tokenId
 * @param {string} owner - Owner address
 * @param {string} spender - Spender address
 * @param {string} amount - Allowance amount
 * @param {number} ttlSeconds - Time to live (0 = permanent)
 * @returns {{success: boolean, allowanceId: string}}
 */
function approve(tokenId, owner, spender, amount, ttlSeconds) {}

/**
 * Transfer using allowance (transferFrom pattern)
 * @param {string} tokenId
 * @param {string} owner - Token owner
 * @param {string} spender - Caller with allowance
 * @param {string} to - Recipient
 * @param {string} amount
 * @returns {{success: boolean, txHash: string, remainingAllowance: string}}
 */
function transferFrom(tokenId, owner, spender, to, amount) {}

/**
 * Get allowance for spender
 * @param {string} tokenId
 * @param {string} owner
 * @param {string} spender
 * @returns {{amount: string, expiresAt: number}|null}
 */
function getAllowance(tokenId, owner, spender) {}

/**
 * Get token info and holder statistics
 * @param {string} tokenId
 * @returns {{token: Token, holderCount: number, topHolders: Object[]}}
 */
function getTokenInfo(tokenId) {}

module.exports = {
  transfer,
  approve,
  transferFrom,
  getAllowance,
  getTokenInfo,
};
```

### Required Data Structures

1. **Token** - Token metadata and formatting
2. **TransferRequest** - Validated transfer payload
3. **Allowance** - Spender authorization with expiry
4. **TokenLedger** - Balance tracking state machine

### Architectural Patterns to Follow

- Use string for large numeric values (avoid floating point)
- Implement idempotency with nonce checking
- Use HMAC signatures for auth (see `services/security/service.js`)
- Return structured results with success/reason pattern
- Implement atomic operations (all-or-nothing)

### Acceptance Criteria

1. **Unit Tests** - Create `tests/unit/token-ledger.test.js`:
   - Test `TokenLedger` credit/debit operations
   - Test `executeTransfer()` success and failure cases
   - Test `batchTransfer()` atomicity
   - Test `validateTransfer()` pre-flight checks
   - Test `circulatingSupply()` calculation

2. **Model Tests** - Create `tests/unit/token.test.js`:
   - Test `Token` amount formatting/parsing
   - Test `TransferRequest` validation
   - Test `Allowance` expiration and spending checks

3. **Service Tests** - Create `tests/services/token.service.test.js`:
   - Test `transfer()` with valid/invalid signatures
   - Test `approve()` and `transferFrom()` flow
   - Test `getAllowance()` retrieval
   - Test concurrent transfer handling

4. **Integration** - Contracts entry:
   ```javascript
   token: {
     id: 'token',
     port: 8100,
     healthPath: '/health',
     version: '1.0.0',
     dependencies: ['security', 'audit'],
   }
   ```

5. **Test Command**: `npm test`

6. **Edge Cases**:
   - Zero-value transfers
   - Self-transfers (from === to)
   - Insufficient balance
   - Expired allowances
   - Duplicate nonces (idempotency)

---

## General Implementation Notes

### Directory Structure

```
js/nebulachain/
  src/
    core/
      contract-validator.js    # Task 1
      block-explorer.js        # Task 2
      token-ledger.js          # Task 3
    models/
      smart-contract.js        # Task 1
      block.js                 # Task 2
      token.js                 # Task 3
  services/
    validator/
      service.js               # Task 1
    explorer/
      service.js               # Task 2
    token/
      service.js               # Task 3
  tests/
    unit/
      contract-validator.test.js
      block-explorer.test.js
      block.test.js
      token-ledger.test.js
      token.test.js
    services/
      validator.service.test.js
      explorer.service.test.js
      token.service.test.js
```

### Common Patterns

1. **Result Objects**: Always return `{success: boolean, reason: string|null, ...data}`
2. **Null Safety**: Check inputs at function entry, return early with descriptive reasons
3. **Constants**: Use `Object.freeze()` for immutable lookup tables
4. **Hashing**: Use `node:crypto` for SHA-256 and HMAC operations
5. **BigInt Math**: Use strings for amounts, convert to BigInt for arithmetic
6. **Test Style**: Use `node:test` and `node:assert/strict` (see existing tests)

### Running Tests

```bash
npm test
```

This runs all tests including the stress test matrices. For development, run specific test files:

```bash
node --test tests/unit/contract-validator.test.js
node --test tests/services/validator.service.test.js
```
