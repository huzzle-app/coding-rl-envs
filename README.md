# Coding RL Environments

50 debugging environments across 9 languages for training and evaluating code agents. Each environment contains intentional bugs that agents must find and fix.

**Compatible with Terminal-Bench v2 / Harbor framework.**

## Quick Start

```bash
# Install Harbor CLI
pip install harbor

# Run with an agent on a single task
harbor run -p python/talentflow -a aider -m deepseek/deepseek-coder-v2

# Run the oracle (reference solution) to verify setup
harbor run -p python/talentflow -a oracle

# Run on the full dataset
harbor run -d terminal-bench@2.0 -a aider -m qwen/qwen-2.5-coder-32b
```

**Requirements:** Docker must be installed and running.

## Curriculum Structure (RL Training)

The `curriculum.json` file defines the full training progression:

```json
{
  "difficulty_order": ["senior", "principal", "distinguished", "ultra-principal", "hyper-principal", "apex-principal"],
  "tier_config": {
    "senior": {"estimated_steps": 500, "max_steps": 2000, "initial_pass_rate": "10-30%"},
    "principal": {"estimated_steps": 2000, "max_steps": 8000, "initial_pass_rate": "5-15%"},
    "distinguished": {"estimated_steps": 5000, "max_steps": 20000, "initial_pass_rate": "3-10%"},
    "ultra-principal": {"estimated_steps": 10000, "max_steps": 40000, "initial_pass_rate": "2-8%"},
    "hyper-principal": {"estimated_steps": 20000, "max_steps": 80000, "initial_pass_rate": "1-5%"},
    "apex-principal": {"estimated_steps": 50000, "max_steps": 200000, "initial_pass_rate": "0.5-3%"}
  }
}
```

### Difficulty Tiers

| Tier | Hours | Bugs | Tests | Setup Bugs | Reward Thresholds |
|------|-------|------|-------|------------|-------------------|
| Senior | 4-8h | 20-30 | 100-300 | Yes | 5-threshold |
| Principal | 8-20h | 30-50 | 300-1000 | Yes | 8-threshold |
| Distinguished | 20-40h | 50-100 | 1000-3000 | Sometimes | 8-threshold |
| Ultra-Principal | 40-70h | 100-500 | 3000-6000 | No | 8-threshold |
| Hyper-Principal | 70-140h | 500-1250 | 6000-10000 | No | 8-threshold |
| Apex-Principal | 120-168h | 1200-1400 | 9000-15000 | No | 10-threshold |

**Setup Bugs**: Senior/Principal tiers have intentional build errors (circular imports, DI cycles) that block startup. Hyper/Apex tiers skip setup bugs—tests run immediately but most fail due to logic bugs.

## Environments

| Language | Count | Test Command |
|----------|-------|--------------|
| Python | 8 | `python tests/run_all.py` |
| JavaScript | 7 | `npm test` |
| Go | 7 | `go test -race -v ./...` |
| Rust | 7 | `cargo test` |
| Ruby | 5 | `ruby -Ilib tests/run_all.rb` |
| C# | 4 | `dotnet test` |
| C++ | 4 | `ctest --output-on-failure` |
| Java | 4 | `mvn test -q` |
| Kotlin | 4 | `./gradlew test` |

### Full Environment List

<details>
<summary>Click to expand all 50 environments</summary>

| Environment | Language | Tier | Tests | Timeout |
|-------------|----------|------|-------|---------|
| **Senior Tier** |
| talentflow | Python | senior | 250 | 4h |
| collabcanvas | JavaScript | senior | 200 | 4h |
| cloudvault | Go | senior | 300 | 4h |
| healthlink | C# | senior | 280 | 4h |
| cacheforge | C++ | senior | 220 | 4h |
| pulsemap | Kotlin | senior | 240 | 4h |
| docuvault | Java | senior | 260 | 4h |
| taskforge | Ruby | senior | 230 | 4h |
| vaultfs | Rust | senior | 270 | 4h |
| **Principal Tier** |
| synapsenet | Python | principal | 800 | 8h |
| nexustrade | Python | principal | 750 | 8h |
| omnicloud | Python | principal | 900 | 8h |
| cloudmatrix | JavaScript | principal | 700 | 8h |
| datanexus | JavaScript | principal | 850 | 8h |
| mediaflow | JavaScript | principal | 780 | 8h |
| atlasdispatch | Go | principal | 720 | 8h |
| quorumledger | Go | principal | 680 | 8h |
| shopstream | Ruby | principal | 640 | 8h |
| fleetpulse | Java | principal | 710 | 8h |
| transitcore | Java | principal | 1094 | 8h |
| mindvault | Kotlin | principal | 690 | 8h |
| eventhorizon | C# | principal | 820 | 8h |
| aerolith | Rust | principal | 760 | 8h |
| geneforge | Rust | principal | 810 | 8h |
| signalstream | C++ | principal | 740 | 8h |
| **Distinguished Tier** |
| fluxrail | JavaScript | distinguished | 2200 | 16h |
| signaldock | JavaScript | distinguished | 2100 | 16h |
| gridweaver | Go | distinguished | 2500 | 16h |
| incidentmesh | Go | distinguished | 2300 | 16h |
| polariscore | Rust | distinguished | 2400 | 16h |
| quantumcore | Rust | distinguished | 2600 | 16h |
| **Ultra-Principal Tier** |
| tradeengine | Go | ultra-principal | 5100 | 20h |
| clearledger | Ruby | ultra-principal | 4800 | 20h |
| mercuryledger | Ruby | ultra-principal | 5200 | 20h |
| tensorforge | Rust | ultra-principal | 5500 | 20h |
| vectorharbor | Rust | ultra-principal | 4900 | 20h |
| **Hyper-Principal Tier** |
| aetherops | Python | hyper-principal | 7152 | 48h |
| heliosops | Python | hyper-principal | 7000 | 48h |
| nimbusflow | Kotlin | hyper-principal | 9261 | 48h |
| aegiscore | C# | hyper-principal | 9261 | 48h |
| chronomesh | C++ | hyper-principal | 9257 | 48h |
| vertexgrid | Java | hyper-principal | 9200 | 48h |
| **Apex-Principal Tier** |
| ionveil | Python | apex-principal | 12462 | 48h |
| latticeforge | Python | apex-principal | 15270 | 48h |
| nebulachain | JavaScript | apex-principal | 9213 | 48h |
| ironfleet | Go | apex-principal | 9213 | 48h |
| opalcommand | Ruby | apex-principal | 9263 | 48h |
| helixops | Kotlin | apex-principal | 12000 | 48h |
| strataguard | C# | apex-principal | 9261 | 48h |
| obsidianmesh | C++ | apex-principal | 12678 | 48h |

</details>

## Directory Structure

```
<language>/<environment>/
├── task.toml              # Harbor task configuration
├── instruction.md         # Agent-facing task description
├── TASK.md                # Detailed specification
├── docker-compose.yml     # Docker environment
├── Dockerfile
├── tests/
│   └── test.sh            # Verification script → writes reward
├── solution/
│   └── solve.sh           # Reference solution placeholder
├── environment/
│   ├── setup.py           # Environment wrapper
│   ├── reward.py          # Reward calculation
│   └── scoring.py         # Scoring utilities
└── src/                   # Source code with bugs
```

### Timeout Structure

Each environment has two timeouts in `task.toml`:
- **Agent timeout**: How long the agent has to solve the task (4h-48h)
- **Verifier timeout**: How long to run tests (15min-60min, scales with test suite size)

## Reward System

Environments use sparse, threshold-based rewards:

**5-threshold (Senior):**
```
Pass Rate    Reward
≥100%        1.00
≥90%         0.65
≥75%         0.35
≥50%         0.15
<50%         0.00
```

**8-threshold (Principal → Hyper-Principal):**
```
Pass Rate    Reward
≥100%        1.00
≥95%         0.78
≥85%         0.55
≥70%         0.38
≥55%         0.22
≥40%         0.12
≥25%         0.05
<25%         0.00
```

**10-threshold (Apex-Principal):**
```
Pass Rate    Reward
≥100%        1.00
≥99%         0.85
≥96%         0.66
≥90%         0.47
≥80%         0.31
≥67%         0.19
≥52%         0.11
≥36%         0.05
≥22%         0.015
<10%         0.00
```

## Bug Structure

- **Bug Dependency Chains**: 40-71% of bugs have prerequisites (depth 3-8)
- **Common Patterns**:
  - Boundary errors (`>` vs `>=`, off-by-one)
  - Sort direction inversions
  - Wrong constants (e.g., `0.3` → `0.5`)
  - Missing validation (null checks, bounds)
  - Logic inversions (min/max, oldest/newest)
  - Silent errors (swallowed exceptions)

## Running Locally

```bash
cd python/talentflow

# Start services (databases, etc.)
docker compose up -d

# Run tests
docker compose -f docker-compose.test.yml up --build

# Or run tests directly (language-specific)
python tests/run_all.py      # Python
npm install && npm test      # JavaScript
go test -race -v ./...       # Go
cargo test                   # Rust
ruby -Ilib tests/run_all.rb  # Ruby
dotnet test                  # C#
mvn test -q                  # Java
./gradlew test               # Kotlin
cmake --build build && ctest --test-dir build --output-on-failure  # C++
```

## Training Features

### Incremental Rewards

Track progress between attempts:

```bash
PREV_PASSED=50 ./tests/test.sh
```

Returns bonus/penalty for newly passing or regressing tests.

### Training Modes

Dense reward signals for RL training:

```bash
TRAINING_MODE=linear ./tests/test.sh     # Linear 0.0-1.0
TRAINING_MODE=sublinear ./tests/test.sh  # Diminishing returns
TRAINING_MODE=smooth ./tests/test.sh     # Sigmoid curve
```

### Targeted Testing

```bash
TEST_FILE=src/services/auth.py ./tests/test.sh
```

### Checkpoints

```bash
./tests/checkpoint.sh save my-checkpoint
./tests/checkpoint.sh restore my-checkpoint
./tests/checkpoint.sh list
```

### Curriculum Learning

```bash
# Enable in curriculum.json
"curriculum_learning": {
  "enabled": true,
  "promotion_threshold": 0.85,
  "demotion_threshold": 0.20
}
```

## Harbor Compatibility

All environments follow the Harbor task format:

| Required File | Purpose |
|---------------|---------|
| `task.toml` | Task metadata (`[metadata]`, `[agent]`, `[verifier]`) |
| `instruction.md` | Agent instructions |
| `tests/test.sh` | Writes reward to `/logs/verifier/reward.txt` |
| `solution/solve.sh` | Reference solution |
| `docker-compose.yml` | Environment definition |

### Validate Format

```bash
# Using Harbor CLI
pip install harbor
harbor tasks check -p python/talentflow -m deepseek/deepseek-coder-v2

# Or validate locally (no LLM required)
python3 -c "
import tomllib
from pathlib import Path
for p in Path('.').glob('*/*/task.toml'):
    data = tomllib.load(open(p, 'rb'))
    assert 'metadata' in data and 'verifier' in data
    print(f'OK: {p.parent}')
"
```

## Test Output Parsing

| Language | Pattern |
|----------|---------|
| Python | `X passed, Y failed` |
| JavaScript | `# pass X` / `# fail Y` |
| Go | `--- PASS:` / `--- FAIL:` counts |
| Ruby | `X examples, Y failures` |
| Java | `Tests run: X, Failures: Y` |
| Kotlin | JUnit XML in `build/test-results/` |
| C# | `Passed: X, Failed: Y` |
| Rust | `test result: ok. X passed; Y failed` |
| C++ | `X tests failed out of Y` |

## Validation Scripts

The `scripts/` directory contains tools for environment validation:

```bash
# Validate all environments
python scripts/validate_environments.py

# Add tier metadata to task.toml
python scripts/add_tier_to_toml.py

# Transform test scripts
python scripts/transform_test_sh.py
```

## Contributing

1. Bugs should be realistic (wrong operators, boundary errors, logic inversions)
2. Tests should fail initially (see tier's initial_pass_rate above)
3. No build/compile errors in Hyper/Apex tiers
4. Reward thresholds must match difficulty tier
5. All environments must pass `scripts/validate_environments.py`

## License

See LICENSE file for details.
