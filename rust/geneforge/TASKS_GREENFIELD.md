# GeneForge - Greenfield Implementation Tasks

These tasks require implementing NEW modules from scratch for the GeneForge genomics platform. Each task must follow the existing architectural patterns found in `src/` modules (qc.rs, aggregator.rs, statistics.rs, pipeline.rs, consent.rs, resilience.rs, reporting.rs).

## Architectural Patterns to Follow

1. **Module Structure**: Each module should have a doc comment (`//! Description`)
2. **Data Types**: Use `#[derive(Debug, Clone)]` for structs, add `PartialEq, Eq` where comparison is needed
3. **Error Handling**: Return `Option<T>` for computations that may fail, with early returns for edge cases
4. **Validation Functions**: Use `fn validate_*(...) -> bool` or `fn *_acceptable(...) -> bool` patterns
5. **Naming Conventions**: Use snake_case for functions, PascalCase for types, SCREAMING_CASE for constants

---

## Task 1: Variant Caller Service

### Description
Implement a variant calling service that identifies genetic variants (SNPs, insertions, deletions) from aligned sequence data and classifies them by clinical significance.

### Module Location
Create `src/variant.rs` and add `pub mod variant;` to `src/lib.rs`

### Required Trait Contract

```rust
//! Variant calling and classification for genomic sequences

/// Represents a single nucleotide polymorphism or small indel
#[derive(Debug, Clone, PartialEq)]
pub struct Variant {
    /// Chromosome identifier (e.g., "chr1", "chrX")
    pub chromosome: String,
    /// 1-based position on the chromosome
    pub position: u64,
    /// Reference allele sequence
    pub reference: String,
    /// Alternate allele sequence
    pub alternate: String,
    /// Phred-scaled quality score
    pub quality: f64,
    /// Read depth at this position
    pub depth: u32,
    /// Allele frequency in the sample (0.0 to 1.0)
    pub allele_frequency: f64,
}

/// Clinical significance classification
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ClinicalSignificance {
    Benign,
    LikelyBenign,
    Uncertain,
    LikelyPathogenic,
    Pathogenic,
}

/// Variant type classification
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum VariantType {
    Snp,
    Insertion,
    Deletion,
    Mnp,  // Multi-nucleotide polymorphism
    Complex,
}

/// Result of variant filtering
#[derive(Debug, Clone)]
pub struct FilterResult {
    pub passed: bool,
    pub filters_failed: Vec<&'static str>,
}

/// Classifies the type of a variant based on ref/alt alleles
/// - SNP: ref and alt are single nucleotides and different
/// - Insertion: alt is longer than ref
/// - Deletion: ref is longer than alt
/// - MNP: ref and alt are same length but > 1
/// - Complex: everything else
pub fn classify_variant_type(variant: &Variant) -> VariantType;

/// Determines if a variant passes quality filters
/// - Quality must be >= 30.0
/// - Depth must be >= 10
/// - Allele frequency must be >= 0.15 for heterozygous calls
/// Returns FilterResult with list of failed filters
pub fn filter_variant(variant: &Variant) -> FilterResult;

/// Checks if variant is in a coding region
/// Coding regions are defined as positions where (position % 1000) < 700
/// (simplified model for testing purposes)
pub fn is_coding_region(chromosome: &str, position: u64) -> bool;

/// Calculates variant allele depth from total depth and allele frequency
/// Formula: depth * allele_frequency, rounded to nearest integer
pub fn variant_allele_depth(variant: &Variant) -> u32;

/// Determines if a variant is likely germline vs somatic
/// Germline: allele_frequency between 0.40 and 0.60 (heterozygous)
///           or >= 0.90 (homozygous)
/// Returns true for germline, false for likely somatic
pub fn is_germline(variant: &Variant) -> bool;

/// Calculates the transition/transversion ratio for a set of SNPs
/// Transitions: A<->G, C<->T
/// Transversions: all other substitutions
/// Returns None if no valid SNPs
pub fn ti_tv_ratio(variants: &[Variant]) -> Option<f64>;

/// Filters variants by minimum quality threshold
pub fn filter_by_quality(variants: &[Variant], min_quality: f64) -> Vec<&Variant>;

/// Counts variants per chromosome
/// Returns a sorted vector of (chromosome, count) tuples, sorted by chromosome name
pub fn variants_per_chromosome(variants: &[Variant]) -> Vec<(String, usize)>;

/// Assigns clinical significance based on allele frequency in population
/// - frequency < 0.0001: LikelyPathogenic
/// - frequency < 0.001: Uncertain
/// - frequency < 0.01: LikelyBenign
/// - frequency >= 0.01: Benign
/// If in_known_pathogenic_list is true, override to Pathogenic
pub fn classify_significance(
    population_frequency: f64,
    in_known_pathogenic_list: bool,
) -> ClinicalSignificance;

/// Calculates the percentage of variants that pass quality filters
pub fn pass_rate(variants: &[Variant]) -> f64;
```

### Acceptance Criteria

1. All functions implemented with correct logic
2. Unit tests in `tests/variant_tests.rs` covering:
   - Each variant type classification
   - Filter edge cases (boundary values for quality, depth, AF)
   - Ti/Tv ratio calculation with mixed variants
   - Clinical significance thresholds
   - Empty input handling
3. Integration with existing `QCMetrics` - variants should be filterable by sample QC status
4. Minimum 15 test cases

### Test Command
```bash
cargo test variant
```

---

## Task 2: Genome Alignment Validator

### Description
Implement an alignment validation service that checks the quality and correctness of sequence alignments against a reference genome. This is critical for downstream variant calling accuracy.

### Module Location
Create `src/alignment.rs` and add `pub mod alignment;` to `src/lib.rs`

### Required Trait Contract

```rust
//! Alignment validation for genomic sequences

/// Represents a single read alignment
#[derive(Debug, Clone)]
pub struct Alignment {
    /// Unique read identifier
    pub read_id: String,
    /// Chromosome the read maps to
    pub chromosome: String,
    /// 1-based start position
    pub start_position: u64,
    /// CIGAR string describing alignment (e.g., "50M", "30M2I18M")
    pub cigar: String,
    /// Mapping quality (0-60)
    pub mapping_quality: u8,
    /// Is this a proper pair in paired-end sequencing
    pub is_proper_pair: bool,
    /// Is this a duplicate read
    pub is_duplicate: bool,
    /// Is this a supplementary alignment
    pub is_supplementary: bool,
}

/// Alignment statistics for a batch of reads
#[derive(Debug, Clone, PartialEq)]
pub struct AlignmentStats {
    pub total_reads: usize,
    pub mapped_reads: usize,
    pub properly_paired: usize,
    pub duplicates: usize,
    pub supplementary: usize,
    pub mean_mapping_quality: f64,
}

/// Validation result for an alignment
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ValidationResult {
    Valid,
    LowMappingQuality,
    Duplicate,
    SupplementaryOnly,
    InvalidCigar,
    MultiplIssues(Vec<String>),
}

/// CIGAR operation types
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum CigarOp {
    Match(u32),      // M
    Insertion(u32),  // I
    Deletion(u32),   // D
    SoftClip(u32),   // S
    HardClip(u32),   // H
    Skip(u32),       // N (for RNA-seq)
}

/// Parses a CIGAR string into operations
/// Returns None if the CIGAR is malformed
/// Example: "50M2I30M" -> [Match(50), Insertion(2), Match(30)]
pub fn parse_cigar(cigar: &str) -> Option<Vec<CigarOp>>;

/// Calculates the aligned length from CIGAR operations
/// Counts M, D, and N operations (reference-consuming)
pub fn aligned_length(cigar_ops: &[CigarOp]) -> u32;

/// Calculates the number of mismatches/indels from CIGAR
/// Counts I and D operations only
pub fn indel_count(cigar_ops: &[CigarOp]) -> u32;

/// Validates a single alignment
/// - Mapping quality must be >= 20 for Valid
/// - Duplicates should be flagged
/// - Supplementary-only reads need special handling
/// - CIGAR must be parseable
pub fn validate_alignment(alignment: &Alignment) -> ValidationResult;

/// Checks if mapping quality is acceptable for variant calling
/// Minimum threshold: 30
pub fn mapping_quality_acceptable(mq: u8) -> bool;

/// Calculates the soft-clip ratio from CIGAR
/// soft_clipped_bases / total_read_length
/// High soft-clip ratio (> 0.2) may indicate misalignment
pub fn soft_clip_ratio(cigar_ops: &[CigarOp]) -> f64;

/// Computes alignment statistics for a batch of alignments
pub fn compute_stats(alignments: &[Alignment]) -> AlignmentStats;

/// Returns the mapping rate (mapped/total)
pub fn mapping_rate(stats: &AlignmentStats) -> f64;

/// Returns the duplication rate (duplicates/total)
pub fn duplication_rate(stats: &AlignmentStats) -> f64;

/// Filters alignments by minimum mapping quality
pub fn filter_by_mapping_quality(alignments: &[Alignment], min_mq: u8) -> Vec<&Alignment>;

/// Checks if an alignment spans a specific genomic region
/// Region is defined as chromosome:start-end (1-based, inclusive)
pub fn alignment_spans_region(
    alignment: &Alignment,
    chromosome: &str,
    region_start: u64,
    region_end: u64,
) -> bool;

/// Calculates read depth at a specific position from a set of alignments
/// Counts alignments that span the given position
pub fn depth_at_position(
    alignments: &[Alignment],
    chromosome: &str,
    position: u64,
) -> u32;

/// Identifies potentially chimeric reads (split across chromosomes)
/// Returns read_ids that appear on multiple chromosomes
pub fn find_chimeric_reads(alignments: &[Alignment]) -> Vec<String>;
```

### Acceptance Criteria

1. All functions implemented with correct logic
2. CIGAR parsing must handle all standard operations (M, I, D, S, H, N)
3. Unit tests in `tests/alignment_tests.rs` covering:
   - CIGAR parsing edge cases
   - Alignment validation rules
   - Statistics calculation accuracy
   - Region overlap detection
   - Chimeric read detection
4. Integration point: alignment stats should feed into `ExtendedQCMetrics`
5. Minimum 20 test cases

### Test Command
```bash
cargo test alignment
```

---

## Task 3: Population Frequency Calculator

### Description
Implement a population genetics service that calculates allele frequencies, Hardy-Weinberg equilibrium statistics, and population stratification metrics for cohort-level genomic analysis.

### Module Location
Create `src/population.rs` and add `pub mod population;` to `src/lib.rs`

### Required Trait Contract

```rust
//! Population genetics calculations for cohort analysis

/// Genotype at a variant position
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Genotype {
    HomozygousRef,    // 0/0
    Heterozygous,     // 0/1 or 1/0
    HomozygousAlt,    // 1/1
    Missing,          // ./.
}

/// Allele frequency data for a variant across a population
#[derive(Debug, Clone)]
pub struct AlleleFrequency {
    /// Variant identifier (e.g., "chr1:12345:A:G")
    pub variant_id: String,
    /// Number of samples with HomozygousRef
    pub hom_ref_count: usize,
    /// Number of samples with Heterozygous
    pub het_count: usize,
    /// Number of samples with HomozygousAlt
    pub hom_alt_count: usize,
    /// Number of samples with missing genotype
    pub missing_count: usize,
}

/// Hardy-Weinberg equilibrium test result
#[derive(Debug, Clone)]
pub struct HweResult {
    pub observed_het_freq: f64,
    pub expected_het_freq: f64,
    pub chi_squared: f64,
    pub p_value: f64,
    pub in_equilibrium: bool,
}

/// Population stratification metrics
#[derive(Debug, Clone)]
pub struct StratificationMetrics {
    /// Fixation index (Fst) between populations
    pub fst: f64,
    /// Inbreeding coefficient
    pub inbreeding_coefficient: f64,
    /// Number of populations analyzed
    pub population_count: usize,
}

/// Calculates the alternate allele frequency from genotype counts
/// Formula: (2*hom_alt + het) / (2 * total_called)
/// Returns None if no called genotypes
pub fn calculate_allele_frequency(af: &AlleleFrequency) -> Option<f64>;

/// Calculates the minor allele frequency (MAF)
/// MAF is min(alt_freq, 1 - alt_freq)
pub fn minor_allele_frequency(af: &AlleleFrequency) -> Option<f64>;

/// Parses a genotype string into Genotype enum
/// Accepts: "0/0", "0|0", "0/1", "1/0", "0|1", "1|0", "1/1", "1|1", "./.", ".|."
pub fn parse_genotype(gt_str: &str) -> Genotype;

/// Performs Hardy-Weinberg equilibrium test
/// Chi-squared test with 1 degree of freedom
/// in_equilibrium is true if p_value >= 0.05
pub fn hardy_weinberg_test(af: &AlleleFrequency) -> Option<HweResult>;

/// Calculates expected heterozygosity from allele frequency
/// Formula: 2 * p * q where p = alt_freq, q = 1 - alt_freq
pub fn expected_heterozygosity(alt_allele_freq: f64) -> f64;

/// Calculates observed heterozygosity from genotype counts
/// Formula: het_count / total_called
pub fn observed_heterozygosity(af: &AlleleFrequency) -> Option<f64>;

/// Calculates the inbreeding coefficient (F)
/// Formula: 1 - (observed_het / expected_het)
/// Positive F indicates excess homozygosity (inbreeding)
/// Negative F indicates excess heterozygosity (outbreeding)
pub fn inbreeding_coefficient(af: &AlleleFrequency) -> Option<f64>;

/// Filters variants by minimum allele frequency threshold
pub fn filter_by_maf(variants: &[AlleleFrequency], min_maf: f64) -> Vec<&AlleleFrequency>;

/// Filters variants that are in Hardy-Weinberg equilibrium
pub fn filter_hwe_passing(variants: &[AlleleFrequency], min_p_value: f64) -> Vec<&AlleleFrequency>;

/// Calculates call rate for a variant
/// Formula: (total - missing) / total
pub fn call_rate(af: &AlleleFrequency) -> f64;

/// Filters variants by minimum call rate
pub fn filter_by_call_rate(
    variants: &[AlleleFrequency],
    min_call_rate: f64,
) -> Vec<&AlleleFrequency>;

/// Calculates Fst (fixation index) between two populations
/// Formula: (Ht - Hs) / Ht
/// where Ht = total heterozygosity, Hs = subpopulation heterozygosity
pub fn calculate_fst(pop1: &[AlleleFrequency], pop2: &[AlleleFrequency]) -> Option<f64>;

/// Summarizes allele frequency distribution
/// Returns (count_rare, count_low_freq, count_common)
/// - Rare: MAF < 0.01
/// - Low frequency: 0.01 <= MAF < 0.05
/// - Common: MAF >= 0.05
pub fn allele_frequency_spectrum(variants: &[AlleleFrequency]) -> (usize, usize, usize);

/// Calculates the effective population size from heterozygosity
/// Ne = H / (4 * mutation_rate * (1 - H))
/// Assumes mutation_rate = 1e-8 per base per generation
pub fn effective_population_size(avg_heterozygosity: f64) -> Option<f64>;

/// Checks if a variant is polymorphic in the population
/// Returns true if there's at least one alternate allele
pub fn is_polymorphic(af: &AlleleFrequency) -> bool;
```

### Acceptance Criteria

1. All functions implemented with correct population genetics formulas
2. Chi-squared calculation must use standard formula for HWE test
3. Unit tests in `tests/population_tests.rs` covering:
   - Allele frequency calculations with edge cases
   - Hardy-Weinberg equilibrium testing
   - Genotype parsing (all valid formats)
   - Inbreeding coefficient interpretation
   - Fst calculation between populations
   - Empty/missing data handling
4. Integration with `CohortSummary` for cohort-level population analysis
5. Minimum 25 test cases

### Test Command
```bash
cargo test population
```

---

## General Requirements

### Code Quality
- All functions must have doc comments explaining their purpose
- Use `#[derive(Debug, Clone)]` on all public structs
- Handle edge cases (empty inputs, zero denominators, invalid data)
- Follow Rust naming conventions and idioms

### Testing
- Each module needs a corresponding test file in `tests/`
- Test boundary conditions and edge cases
- Include tests for integration with existing modules
- Run all tests: `cargo test`

### Integration Points
- `variant.rs` should work with `qc.rs` QCMetrics for sample-level filtering
- `alignment.rs` stats should feed into `qc.rs` ExtendedQCMetrics
- `population.rs` should integrate with `aggregator.rs` CohortSummary

### Documentation
- Add module to `src/lib.rs` with `pub mod`
- Include examples in doc comments where helpful
