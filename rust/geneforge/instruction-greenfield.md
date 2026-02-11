# GeneForge - Greenfield Implementation Tasks

## Overview

GeneForge greenfield tasks require implementing 3 new modules from scratch for the genomics platform. Each module follows established architectural patterns from existing source code and integrates with the core platform infrastructure. Tasks test ability to implement complex data structures, validation logic, and computational functions while maintaining consistency with the existing codebase.

## Environment

- **Language:** Rust
- **Infrastructure:** Docker Compose with PostgreSQL and Redis dependencies
- **Difficulty:** Principal
- **Module Patterns:** Doc comments, structured error handling, comprehensive validation functions

## Tasks

### Task 1: Variant Caller Service (Greenfield Module)

Implement a variant calling service (`src/variant.rs`) that identifies genetic variants (SNPs, insertions, deletions) from aligned sequence data and classifies them by clinical significance. The module must export 14 functions including variant type classification, quality filtering, germline detection, transition/transversion ratio calculation, and clinical significance classification. Includes interfaces for `Variant` struct with chromosome, position, reference/alternate alleles, quality score, depth, and allele frequency fields; `VariantType` enum (Snp, Insertion, Deletion, Mnp, Complex); and `ClinicalSignificance` enum (Benign, LikelyBenign, Uncertain, LikelyPathogenic, Pathogenic).

### Task 2: Genome Alignment Validator (Greenfield Module)

Implement an alignment validation service (`src/alignment.rs`) that checks quality and correctness of sequence alignments against reference genomes. The module must parse CIGAR strings, compute alignment statistics, validate mapping quality, detect chimeric reads, and assess soft-clipping ratios. Includes interfaces for `Alignment` struct with read identifier, chromosome, position, CIGAR string, mapping quality, and flags for proper pairs/duplicates/supplementary alignments; `CigarOp` enum for CIGAR operation types; `AlignmentStats` struct for batch statistics; and `ValidationResult` enum for alignment validity assessment.

### Task 3: Population Frequency Calculator (Greenfield Module)

Implement a population genetics service (`src/population.rs`) for calculating allele frequencies, Hardy-Weinberg equilibrium statistics, and population stratification metrics. The module must support genotype parsing, allele frequency computation, Hardy-Weinberg chi-squared testing, inbreeding coefficient calculation, and fixation index (Fst) computation between populations. Includes interfaces for `Genotype` enum (HomozygousRef, Heterozygous, HomozygousAlt, Missing); `AlleleFrequency` struct with variant identifier and genotype counts; `HweResult` struct with chi-squared test outputs; and `StratificationMetrics` struct for population-level analysis.

## Getting Started

Start infrastructure and run greenfield-specific tests:

```bash
# Start infrastructure
docker compose up -d

# Run greenfield module tests
cargo test variant
cargo test alignment
cargo test population

# Run full test suite including greenfield modules
cargo test
```

## Success Criteria

1. All 3 modules implemented with required trait contracts
2. Minimum 60 test cases across all modules (15+ per module)
3. Integration with existing QC and aggregation infrastructure
4. All 1168+ existing tests continue to pass
5. Complete doc comments on all public types and functions
6. Proper edge case handling (empty inputs, zero denominators, invalid data)

Implementation meets all acceptance criteria defined in [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md). Harbor verification writes reward `1.0` when modules are complete and integrated.
