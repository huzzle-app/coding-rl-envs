# Coding RL Environments

50 environments across 9 languages for training and evaluating code agents. Each environment includes three task types: debugging (fix bugs), alternative (feature development), and greenfield (build from scratch).

**Compatible with Harbor framework.**

## Quick Start

```bash
# Install Harbor CLI
pip install harbor

# Run with an agent on a single task
harbor run -p python/talentflow -a aider -m deepseek/deepseek-coder-v2

# Run the oracle (reference solution) to verify setup
harbor run -p python/talentflow -a oracle
# Run on all environments
for env in */*/task.toml; do harbor run -p "$(dirname $env)" -a aider -m qwen/qwen-2.5-coder-32b; done
```

**Requirements:** Docker must be installed and running.

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

| Environment | Language | Difficulty | Agent Timeout |
|-------------|----------|------------|---------------|
| talentflow | Python | medium | 4h |
| nexustrade | Python | hard | 8h |
| omnicloud | Python | hard | 16h |
| synapsenet | Python | hard | 16h |
| aetherops | Python | hard | 20h |
| heliosops | Python | hard | 20h |
| ionveil | Python | hard | 48h |
| latticeforge | Python | hard | 48h |
| collabcanvas | JavaScript | medium | 4h |
| mediaflow | JavaScript | hard | 8h |
| cloudmatrix | JavaScript | hard | 16h |
| datanexus | JavaScript | hard | 16h |
| fluxrail | JavaScript | hard | 16h |
| signaldock | JavaScript | hard | 20h |
| nebulachain | JavaScript | hard | 48h |
| cloudvault | Go | medium | 4h |
| tradeengine | Go | hard | 8h |
| gridweaver | Go | hard | 16h |
| incidentmesh | Go | hard | 16h |
| atlasdispatch | Go | hard | 20h |
| quorumledger | Go | hard | 20h |
| ironfleet | Go | hard | 48h |
| vaultfs | Rust | medium | 4h |
| geneforge | Rust | hard | 8h |
| quantumcore | Rust | hard | 8h |
| aerolith | Rust | hard | 16h |
| polariscore | Rust | hard | 20h |
| tensorforge | Rust | hard | 48h |
| vectorharbor | Rust | hard | 48h |
| taskforge | Ruby | medium | 4h |
| shopstream | Ruby | hard | 8h |
| clearledger | Ruby | hard | 16h |
| mercuryledger | Ruby | hard | 48h |
| opalcommand | Ruby | hard | 48h |
| healthlink | C# | medium | 4h |
| eventhorizon | C# | hard | 8h |
| aegiscore | C# | hard | 20h |
| strataguard | C# | hard | 48h |
| cacheforge | C++ | medium | 4h |
| chronomesh | C++ | hard | 48h |
| obsidianmesh | C++ | hard | 48h |
| signalstream | C++ | hard | 48h |
| docuvault | Java | medium | 4h |
| fleetpulse | Java | hard | 8h |
| transitcore | Java | hard | 12h |
| vertexgrid | Java | hard | 48h |
| pulsemap | Kotlin | medium | 4h |
| mindvault | Kotlin | hard | 8h |
| helixops | Kotlin | hard | 48h |
| nimbusflow | Kotlin | hard | 48h |

</details>

### Timeout Structure

Each environment has two timeouts in `task.toml`:
- **Agent timeout**: How long the agent has to solve the task (4h-48h)
- **Verifier timeout**: How long to run tests (15min-60min, scales with test suite size)

## Task Types

Each environment supports three task types:

| Type | File | Description |
|------|------|-------------|
| **Debug** | `instruction.md` | Fix intentional bugs in existing code |
| **Alternative** | `instruction-alternative.md` | Feature development, refactoring, optimization |
| **Greenfield** | `instruction-greenfield.md` | Build new modules from scratch |

**Debug tasks** are the default - agents must find and fix bugs to make tests pass.

**Alternative tasks** include challenges like:
- Implementing new features (e.g., LFU eviction policy)
- Performance optimization
- API refactoring
- Adding new integrations

**Greenfield tasks** require building complete new modules:
- Cache warming services
- Metrics exporters
- New protocol handlers
- Monitoring dashboards

To use alternative or greenfield tasks, copy the corresponding instruction file:
```bash
cp instruction-alternative.md instruction.md  # For alternative tasks
cp instruction-greenfield.md instruction.md   # For greenfield tasks
```

## Directory Structure

```
<language>/<environment>/
├── task.toml                    # Harbor task configuration
├── instruction.md               # Debug task (default)
├── instruction-alternative.md   # Alternative tasks (features, refactoring)
├── instruction-greenfield.md    # Greenfield tasks (new modules)
├── TASK.md                      # Detailed debug specification
├── TASKS_ALTERNATIVE.md         # Alternative task specifications
├── TASKS_GREENFIELD.md          # Greenfield task specifications
├── docker-compose.yml           # Docker environment
├── Dockerfile
├── tests/
│   └── test.sh                  # Verification script → writes reward
├── solution/
│   └── solve.sh                 # Reference solution placeholder
├── environment/
│   ├── reward.py                # Reward calculation
│   └── scoring.py               # Scoring utilities
└── <source code>                # Language-specific layout:
    # Python: apps/, <project>/
    # Go: cmd/, internal/, pkg/
    # Rust/JS/C++: src/
    # Java/Kotlin: src/main/
    # C#: src/<Project>/
    # Ruby: lib/, app/
```

## Reward System

Environments use sparse, threshold-based rewards:

**Medium difficulty (5-threshold):**
```
Pass Rate    Reward
≥100%        1.00
≥90%         0.65
≥75%         0.35
≥50%         0.15
<50%         0.00
```

**Hard difficulty (8-threshold):**
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

Use `curriculum.json` for structured training progression:

```json
{
  "difficulty_order": ["senior", "principal", "distinguished", "ultra-principal", "hyper-principal", "apex-principal"],
  "recommended_order": [
    {"env": "python/talentflow", "tier": "senior", "tests": 250},
    {"env": "js/collabcanvas", "tier": "senior", "tests": 200},
    ...
  ]
}
```

Start with senior-tier environments (fewer bugs, smaller codebases) and progress to apex-tier (1000+ bugs, complex architectures).

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

## Contributing

1. Bugs should be realistic (wrong operators, boundary errors, logic inversions)
2. Tests should fail initially (~95-99% failure rate for hard environments)
3. No build/compile errors in hard environments
4. Reward thresholds must match difficulty tier

## License

See LICENSE file for details.
