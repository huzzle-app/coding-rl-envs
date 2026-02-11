package environment

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"
)

// StepResult represents the result of taking an action in the environment.
type StepResult struct {
	Observation map[string]interface{}
	Reward      float64
	Done        bool
	Truncated   bool
	Info        map[string]interface{}
}

// TestResult represents a single test result.
type TestResult struct {
	Name     string
	Passed   bool
	Duration float64
	Category string   // unit, integration, security, race
	BugIDs   []string 
}

// ObservationSpace describes the shape of observations returned by the environment.
var ObservationSpace = map[string]interface{}{
	"type": "Dict",
	"spaces": map[string]interface{}{
		"test_results": map[string]interface{}{
			"type": "Dict",
			"keys": []string{"total", "passed", "failed", "pass_rate", "passed_tests", "failed_tests"},
		},
		"reward":         map[string]interface{}{"type": "Box", "low": 0.0, "high": 1.0, "shape": []int{1}},
		"step_count":     map[string]interface{}{"type": "Discrete", "n": 101},
		"action_result":  map[string]interface{}{"type": "Dict"},
		"bugs_remaining": map[string]interface{}{"type": "MultiBinary", "n": TotalBugs()},
	},
}

// ActionSpace describes the shape of actions accepted by the environment.
var ActionSpace = map[string]interface{}{
	"type": "Dict",
	"spaces": map[string]interface{}{
		"type":    map[string]interface{}{"type": "Discrete", "values": []string{"edit", "read", "run_command"}},
		"file":    map[string]interface{}{"type": "Text", "max_length": 256},
		"content": map[string]interface{}{"type": "Text", "max_length": 100000},
		"command": map[string]interface{}{"type": "Text", "max_length": 1000},
	},
}

// FileTestMap maps source file paths to the test files that cover them.
// Used for targeted test execution after a file is edited.
var FileTestMap = map[string][]string{
	"internal/services/storage/":       {"tests/unit/storage_test.go"},
	"internal/services/sync/":          {"tests/unit/sync_test.go"},
	"internal/services/notification/":  {"tests/unit/notification_test.go"},
	"internal/services/versioning/":    {"tests/unit/versioning_test.go"},
	"internal/middleware/":             {"tests/unit/middleware_test.go", "tests/unit/ratelimit_test.go"},
	"internal/config/":                {"tests/unit/config_test.go"},
	"internal/repository/":            {"tests/unit/repository_test.go", "tests/integration/file_operations_test.go"},
	"internal/handlers/":              {"tests/integration/file_operations_test.go", "tests/security/security_test.go"},
	"pkg/crypto/":                     {"tests/unit/crypto_test.go", "tests/security/security_test.go"},
	"pkg/utils/":                      {"tests/unit/path_test.go", "tests/security/security_test.go"},
	"cmd/server/":                     {"tests/integration/file_operations_test.go"},
}

// Environment represents the CloudVault RL environment.
//
// This environment provides:
//   - A buggy Go codebase with 25 interconnected bugs across 7 categories
//   - 125+ Go tests that verify bug fixes
//   - Sparse reward function with thresholds and regression penalties
//   - Bug dependency chains that require fixing bugs in correct order
//   - Setup bugs that prevent the project from compiling initially
//
// The agent must first fix setup/config bugs (L1, F1-F4) before tests can run.
type Environment struct {
	workDir            string
	dockerUp           bool
	testResults        map[string]bool
	previousResults    map[string]bool
	startTime          time.Time
	stepCount          int
	maxSteps           int
	done               bool
	truncated          bool
	timeout            int
	fullRunInterval    int
	stepsSinceFullRun  int
}

// NewEnvironment creates a new environment instance.
func NewEnvironment(workDir string) *Environment {
	if workDir == "" {
		workDir = "."
	}
	return &Environment{
		workDir:           workDir,
		testResults:       make(map[string]bool),
		previousResults:   make(map[string]bool),
		startTime:         time.Now(),
		maxSteps:          100,
		timeout:           300,
		fullRunInterval:   3,
		stepsSinceFullRun: 0,
	}
}

// Setup initializes the environment (starts Docker services).
func (e *Environment) Setup() error {
	cmd := exec.Command("docker", "compose", "up", "-d")
	cmd.Dir = e.workDir
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("failed to start docker: %w", err)
	}
	e.dockerUp = true

	// Wait for services to be healthy
	time.Sleep(10 * time.Second)
	return nil
}

// Teardown cleans up the environment.
func (e *Environment) Teardown() error {
	if e.dockerUp {
		cmd := exec.Command("docker", "compose", "down", "-v")
		cmd.Dir = e.workDir
		return cmd.Run()
	}
	return nil
}

// Reset resets the environment to the initial buggy state and returns the initial observation.
func (e *Environment) Reset() map[string]interface{} {
	e.restoreInitialState()
	e.stepCount = 0
	e.testResults = make(map[string]bool)
	e.previousResults = make(map[string]bool)
	e.done = false
	e.truncated = false
	e.stepsSinceFullRun = 0
	e.startTime = time.Now()

	// Run initial tests to get baseline
	results := e.runAllTests()
	e.testResults = results

	return map[string]interface{}{
		"test_results":     e.formatTestResults(results),
		"reward":           e.GetReward(),
		"step_count":       e.stepCount,
		"files_changed":    []string{},
		"project_structure": e.getProjectStructure(),
		"bugs_remaining":   e.countRemainingBugs(results),
	}
}

// Step executes an action and returns the result.
func (e *Environment) Step(action map[string]interface{}) StepResult {
	if e.done || e.truncated {
		return e.getTerminalResult()
	}

	e.stepCount++

	// Execute the action
	actionResult := e.executeAction(action)

	// Run tests based on action type
	actionType, _ := action["type"].(string)
	var results map[string]bool

	if actionType == "edit" || actionType == "run_command" {
		e.stepsSinceFullRun++
		changedFile, _ := action["file"].(string)

		// Run targeted tests first for instant feedback
		var targetedResults map[string]bool
		if changedFile != "" {
			targetedResults = e.runTargetedTests(changedFile)
		}

		// Full suite runs every fullRunInterval mutating steps
		allTargetedPass := len(targetedResults) > 0 && allPass(targetedResults)
		if e.stepsSinceFullRun >= e.fullRunInterval || allTargetedPass {
			results = e.runAllTests()
			e.stepsSinceFullRun = 0
		} else if len(targetedResults) > 0 {
			// Merge targeted results into previous full results
			results = make(map[string]bool)
			for k, v := range e.testResults {
				results[k] = v
			}
			for k, v := range targetedResults {
				results[k] = v
			}
		} else {
			results = e.runAllTests()
			e.stepsSinceFullRun = 0
		}
	} else {
		results = e.testResults
	}

	// Calculate reward
	passRate := e.getPassRateFromResults(results)
	reward := CalculateReward(passRate)
	bugBonus := CalculateBugBonus(results)
	regressionPenalty := CalculateRegressionPenalty(results, e.previousResults)

	totalReward := reward*0.40 + bugBonus*0.25 - regressionPenalty*0.15
	if totalReward < 0.0 {
		totalReward = 0.0
	}
	if totalReward > 1.0 {
		totalReward = 1.0
	}

	// Check termination conditions
	allTestsPass := allPass(results) && len(results) > 0
	e.done = allTestsPass
	e.truncated = e.stepCount >= e.maxSteps

	observation := map[string]interface{}{
		"test_results":   e.formatTestResults(results),
		"reward":         totalReward,
		"step_count":     e.stepCount,
		"action_result":  actionResult,
		"bugs_remaining": e.countRemainingBugs(results),
	}

	info := map[string]interface{}{
		"reward_breakdown": map[string]interface{}{
			"test_pass_score":    reward,
			"bug_bonus":          bugBonus,
			"regression_penalty": regressionPenalty,
		},
		"pass_rate": passRate,
	}

	e.previousResults = e.testResults
	e.testResults = results

	return StepResult{
		Observation: observation,
		Reward:      totalReward,
		Done:        e.done,
		Truncated:   e.truncated,
		Info:        info,
	}
}

// GymStep provides a Gymnasium-compatible step returning (obs, reward, done, truncated, info).
func (e *Environment) GymStep(action map[string]interface{}) (map[string]interface{}, float64, bool, bool, map[string]interface{}) {
	result := e.Step(action)
	return result.Observation, result.Reward, result.Done, result.Truncated, result.Info
}

// ValidateAction validates an action before execution.
// Returns nil if valid, or an error map if invalid.
func (e *Environment) ValidateAction(action map[string]interface{}) map[string]interface{} {
	actionType, _ := action["type"].(string)
	if actionType != "edit" && actionType != "read" && actionType != "run_command" {
		return map[string]interface{}{"success": false, "error": fmt.Sprintf("Invalid action type: %s", actionType)}
	}

	filePath, _ := action["file"].(string)
	if len(filePath) > 256 {
		return map[string]interface{}{"success": false, "error": "File path exceeds 256 characters"}
	}
	if strings.Contains(filePath, "..") || filepath.IsAbs(filePath) {
		return map[string]interface{}{"success": false, "error": "Path traversal not allowed"}
	}
	if filePath != "" {
		absPath, _ := filepath.Abs(filepath.Join(e.workDir, filePath))
		absWorkDir, _ := filepath.Abs(e.workDir)
		if !strings.HasPrefix(absPath, absWorkDir+string(filepath.Separator)) && absPath != absWorkDir {
			return map[string]interface{}{"success": false, "error": "Path escapes work directory"}
		}
	}

	// Reject edits to test files
	if actionType == "edit" && filePath != "" {
		if strings.HasSuffix(filePath, "_test.go") ||
			strings.HasPrefix(filePath, "tests/") ||
			strings.HasPrefix(filePath, "test/") ||
			strings.Contains(filePath, "/tests/") ||
			strings.Contains(filePath, "/test/") {
			return map[string]interface{}{"success": false, "error": "Editing test files is not allowed"}
		}
	}

	content, _ := action["content"].(string)
	if len(content) > 100000 {
		return map[string]interface{}{"success": false, "error": "Content exceeds 100K character limit"}
	}

	command, _ := action["command"].(string)
	if len(command) > 1000 {
		return map[string]interface{}{"success": false, "error": "Command exceeds 1000 character limit"}
	}

	return nil
}

// RunTests runs all tests and returns results (public interface).
func (e *Environment) RunTests() (map[string]bool, error) {
	results := e.runAllTests()
	e.testResults = results
	return results, nil
}

// GetPassRate returns the percentage of passing tests.
func (e *Environment) GetPassRate() float64 {
	return e.getPassRateFromResults(e.testResults)
}

// GetReward calculates the reward based on test pass rate.
func (e *Environment) GetReward() float64 {
	passRate := e.GetPassRate()
	return CalculateReward(passRate)
}

// runAllTests runs all tests and returns results.
func (e *Environment) runAllTests() map[string]bool {
	cmd := exec.Command("go", "test", "-race", "-v", "-json", "./...")
	cmd.Dir = e.workDir
	output, err := cmd.CombinedOutput()
	if err != nil {
		// Tests may have failed, which is expected
	}

	return parseGoTestJSON(string(output))
}

// runTargetedTests runs only the tests relevant to a changed file.
func (e *Environment) runTargetedTests(changedFile string) map[string]bool {
	testPaths := []string{}
	for prefix, tests := range FileTestMap {
		if strings.HasPrefix(changedFile, prefix) || changedFile == prefix {
			testPaths = append(testPaths, tests...)
		}
	}

	if len(testPaths) == 0 {
		return nil
	}

	// Deduplicate
	seen := map[string]bool{}
	unique := []string{}
	for _, p := range testPaths {
		if !seen[p] {
			seen[p] = true
			unique = append(unique, "./"+filepath.Dir(p))
		}
	}

	args := append([]string{"test", "-race", "-v", "-json"}, unique...)
	cmd := exec.Command("go", args...)
	cmd.Dir = e.workDir
	output, err := cmd.CombinedOutput()
	if err != nil {
		// Tests may have failed, which is expected
	}

	return parseGoTestJSON(string(output))
}

// parseGoTestJSON parses go test -json output into a map of test name -> passed.
func parseGoTestJSON(output string) map[string]bool {
	results := make(map[string]bool)
	lines := strings.Split(output, "\n")

	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}

		var entry struct {
			Action  string `json:"Action"`
			Package string `json:"Package"`
			Test    string `json:"Test"`
			Output  string `json:"Output"`
			Elapsed float64 `json:"Elapsed"`
		}

		if err := json.Unmarshal([]byte(line), &entry); err != nil {
			continue
		}

		if entry.Test == "" {
			continue // package-level events
		}

		switch entry.Action {
		case "pass":
			results[entry.Test] = true
		case "fail":
			results[entry.Test] = false
		case "skip":
			// Do not count skipped tests
		}
	}

	return results
}

// executeAction executes a single action.
func (e *Environment) executeAction(action map[string]interface{}) map[string]interface{} {
	validationError := e.ValidateAction(action)
	if validationError != nil {
		return validationError
	}

	actionType, _ := action["type"].(string)
	switch actionType {
	case "edit":
		return e.executeEdit(action)
	case "read":
		return e.executeRead(action)
	case "run_command":
		return e.executeCommand(action)
	default:
		return map[string]interface{}{"success": false, "error": fmt.Sprintf("Unknown action type: %s", actionType)}
	}
}

// executeEdit writes content to a file.
func (e *Environment) executeEdit(action map[string]interface{}) map[string]interface{} {
	filePath, _ := action["file"].(string)
	content, _ := action["content"].(string)

	fullPath := filepath.Join(e.workDir, filePath)
	absPath, _ := filepath.Abs(fullPath)
	absWorkDir, _ := filepath.Abs(e.workDir)
	if !strings.HasPrefix(absPath, absWorkDir+string(filepath.Separator)) && absPath != absWorkDir {
		return map[string]interface{}{"success": false, "error": "Path escapes work directory"}
	}

	dir := filepath.Dir(absPath)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return map[string]interface{}{"success": false, "error": err.Error()}
	}

	if err := os.WriteFile(absPath, []byte(content), 0644); err != nil {
		return map[string]interface{}{"success": false, "error": err.Error()}
	}

	return map[string]interface{}{"success": true, "file": absPath}
}

// executeRead reads a file and returns its contents.
func (e *Environment) executeRead(action map[string]interface{}) map[string]interface{} {
	filePath, _ := action["file"].(string)
	fullPath := filepath.Join(e.workDir, filePath)
	absPath, _ := filepath.Abs(fullPath)
	absWorkDir, _ := filepath.Abs(e.workDir)
	if !strings.HasPrefix(absPath, absWorkDir+string(filepath.Separator)) && absPath != absWorkDir {
		return map[string]interface{}{"success": false, "error": "Path escapes work directory"}
	}

	data, err := os.ReadFile(absPath)
	if err != nil {
		return map[string]interface{}{"success": false, "error": err.Error()}
	}

	return map[string]interface{}{"success": true, "content": string(data)}
}

// executeCommand runs a shell command safely.
func (e *Environment) executeCommand(action map[string]interface{}) map[string]interface{} {
	command, _ := action["command"].(string)
	if command == "" {
		return map[string]interface{}{"success": false, "error": "Empty command"}
	}

	parts := strings.Fields(command)
	if len(parts) == 0 {
		return map[string]interface{}{"success": false, "error": "Empty command"}
	}

	// Restrict to safe commands
	safeCommands := map[string]bool{
		"go": true, "cat": true, "ls": true, "grep": true, "head": true, "tail": true,
	}
	if !safeCommands[parts[0]] {
		return map[string]interface{}{"success": false, "error": "Command not allowed"}
	}

	// Block dangerous subcommands
	dangerousArgs := map[string]bool{
		"--delete": true, "rm": true, "eval": true, "exec": true,
	}
	for _, arg := range parts[1:] {
		if dangerousArgs[arg] {
			return map[string]interface{}{"success": false, "error": "Dangerous argument blocked"}
		}
	}

	cmd := exec.Command(parts[0], parts[1:]...)
	cmd.Dir = e.workDir
	output, err := cmd.CombinedOutput()

	success := err == nil
	return map[string]interface{}{
		"success":     success,
		"stdout":      string(output),
		"return_code": cmd.ProcessState.ExitCode(),
	}
}

// formatTestResults formats test results for the observation.
func (e *Environment) formatTestResults(results map[string]bool) map[string]interface{} {
	passed := []string{}
	failed := []string{}
	for name, pass := range results {
		if pass {
			passed = append(passed, name)
		} else {
			failed = append(failed, name)
		}
	}

	total := len(results)
	passRate := 0.0
	if total > 0 {
		passRate = float64(len(passed)) / float64(total)
	}

	return map[string]interface{}{
		"total":        total,
		"passed":       len(passed),
		"failed":       len(failed),
		"pass_rate":    passRate,
		"passed_tests": passed,
		"failed_tests": failed,
	}
}

// countRemainingBugs determines which bugs are still present based on test results.
func (e *Environment) countRemainingBugs(results map[string]bool) map[string]bool {
	bugs := make(map[string]bool)

	for bugID, testNames := range BugTestMapping {
		matchCount := 0
		passCount := 0
		for _, name := range testNames {
			if passed, ok := results[name]; ok {
				matchCount++
				if passed {
					passCount++
				}
			}
		}

		if matchCount == 0 {
			// No matching tests found: bug is NOT fixed
			bugs[bugID] = true
		} else {
			
			bugs[bugID] = passCount < matchCount
		}
	}

	return bugs
}

// getPassRateFromResults calculates pass rate from a results map.
func (e *Environment) getPassRateFromResults(results map[string]bool) float64 {
	if len(results) == 0 {
		return 0.0
	}

	passing := 0
	for _, passed := range results {
		if passed {
			passing++
		}
	}

	return float64(passing) / float64(len(results))
}

// getProjectStructure returns a list of Go source files in the project.
func (e *Environment) getProjectStructure() []string {
	structure := []string{}
	filepath.Walk(e.workDir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return nil
		}
		if info.IsDir() {
			return nil
		}
		if strings.HasSuffix(path, ".go") && !strings.Contains(path, "vendor") {
			rel, _ := filepath.Rel(e.workDir, path)
			structure = append(structure, rel)
		}
		return nil
	})
	return structure
}

// restoreInitialState restores the project to its initial buggy state using git.
func (e *Environment) restoreInitialState() {
	cmd := exec.Command("git", "checkout", ".")
	cmd.Dir = e.workDir
	cmd.Run()

	cmd2 := exec.Command("git", "clean", "-fd")
	cmd2.Dir = e.workDir
	cmd2.Run()
}

// getTerminalResult returns a result for a terminal state.
func (e *Environment) getTerminalResult() StepResult {
	return StepResult{
		Observation: map[string]interface{}{"terminal": true},
		Reward:      0.0,
		Done:        e.done,
		Truncated:   e.truncated,
		Info:        map[string]interface{}{"message": "Episode has ended"},
	}
}

// allPass returns true if all values in the map are true.
func allPass(results map[string]bool) bool {
	for _, v := range results {
		if !v {
			return false
		}
	}
	return true
}

// -- Properties for environment inspection --

// StepCount returns the current step count.
func (e *Environment) StepCount() int {
	return e.stepCount
}

// IsDone returns whether the episode is complete (all tests pass).
func (e *Environment) IsDone() bool {
	return e.done
}

// IsTruncated returns whether the episode was truncated (max steps reached).
func (e *Environment) IsTruncated() bool {
	return e.truncated
}

// GetBugDescriptions returns bug IDs present in the environment.
func GetBugDescriptions() map[string]string {
	descriptions := make(map[string]string)
	for bugID := range BugTestMapping {
		descriptions[bugID] = bugID
	}
	return descriptions
}

// GetSuccessCriteria returns the success criteria for the environment.
func GetSuccessCriteria() string {
	return "All 125+ Go tests must pass (with -race flag) to complete the challenge."
}

// GetSetupBugs returns setup-specific bug IDs.
func GetSetupBugs() []string {
	setupBugs := []string{}
	for _, bugID := range BugCategories["L-Setup"] {
		setupBugs = append(setupBugs, bugID)
	}
	for _, bugID := range BugCategories["F-Configuration"] {
		setupBugs = append(setupBugs, bugID)
	}
	return setupBugs
}

// CheckEnvironment verifies the environment is working.
func CheckEnvironment() error {
	if err := exec.Command("docker", "info").Run(); err != nil {
		return fmt.Errorf("docker not running: %w", err)
	}
	if err := exec.Command("go", "version").Run(); err != nil {
		return fmt.Errorf("go not installed: %w", err)
	}
	return nil
}


var BugCategories = map[string][]string{
	"A-Concurrency": {
		"A1-GoroutineLeak",
		"A2-RaceCondition",
		"A3-ChannelDeadlock",
		"A4-WaitGroupMisuse",
		"A5-MutexCopy",
	},
	"B-Memory": {
		"B1-SliceBounds",
		"B2-NilMapWrite",
		"B3-SliceAliasing",
		"B4-MemoryLeak",
	},
	"C-Database": {
		"C1-TransactionRollback",
		"C2-ConnectionLeak",
		"C3-PreparedStatementLeak",
		"C4-NPlus1Query",
	},
	"D-ErrorHandling": {
		"D1-IgnoredError",
		"D2-ErrorShadowing",
		"D3-NilInterfaceCheck",
	},
	"E-Security": {
		"E1-WeakCrypto",
		"E2-PathTraversal",
		"E3-SQLInjection",
		"E4-IDOR",
	},
	"F-Configuration": {
		"F1-ImportCycle",
		"F2-EnvParsing",
		"F3-ChunkSizeParsing",
		"F4-MissingValidation",
	},
	"L-Setup": {
		"L1-InitOrder",
		"L2-EnvTypeParsing",
	},
}

// TotalBugs returns the total number of bugs.
func TotalBugs() int {
	total := 0
	for _, bugs := range BugCategories {
		total += len(bugs)
	}
	return total
}

// GetBugLocations returns the file locations for each bug.
func GetBugLocations() map[string]string {
	return map[string]string{
		"A1-GoroutineLeak":         "internal/services/storage/storage.go",
		"A2-RaceCondition":         "internal/services/sync/sync.go",
		"A3-ChannelDeadlock":       "internal/services/notification/notify.go",
		"A4-WaitGroupMisuse":       "internal/services/storage/storage.go",
		"A5-MutexCopy":             "internal/middleware/ratelimit.go",
		"B1-SliceBounds":           "internal/services/storage/chunker.go",
		"B2-NilMapWrite":           "internal/services/sync/conflict.go",
		"B3-SliceAliasing":         "internal/services/storage/chunker.go",
		"B4-MemoryLeak":            "internal/services/storage/chunker.go",
		"C1-TransactionRollback":   "internal/services/versioning/version.go",
		"C2-ConnectionLeak":        "internal/repository/file_repo.go",
		"C3-PreparedStatementLeak": "internal/repository/file_repo.go",
		"C4-NPlus1Query":           "internal/repository/user_repo.go",
		"D1-IgnoredError":          "internal/handlers/files.go",
		"D2-ErrorShadowing":        "internal/services/sync/sync.go",
		"D3-NilInterfaceCheck":     "internal/middleware/auth.go",
		"E1-WeakCrypto":            "pkg/crypto/encrypt.go",
		"E2-PathTraversal":         "pkg/utils/path.go",
		"E3-SQLInjection":          "internal/repository/file_repo.go",
		"E4-IDOR":                  "internal/handlers/files.go",
		"F1-ImportCycle":            "cmd/server/main.go",
		"F2-EnvParsing":            "internal/config/config.go",
		"F3-ChunkSizeParsing":      "internal/config/config.go",
		"F4-MissingValidation":     "internal/config/config.go",
		"L1-InitOrder":             "cmd/server/main.go",
		"L2-EnvTypeParsing":        "internal/config/config.go",
	}
}

func main() {
	workDir := os.Getenv("CLOUDVAULT_DIR")
	if workDir == "" {
		workDir = "."
	}

	env := NewEnvironment(workDir)

	if err := CheckEnvironment(); err != nil {
		fmt.Printf("Environment check failed: %v\n", err)
		os.Exit(1)
	}

	if err := env.Setup(); err != nil {
		fmt.Printf("Setup failed: %v\n", err)
		os.Exit(1)
	}
	defer env.Teardown()

	results, err := env.RunTests()
	if err != nil {
		fmt.Printf("Tests failed: %v\n", err)
	}

	passRate := env.GetPassRate()
	reward := env.GetReward()

	fmt.Printf("Pass Rate: %.2f%%\n", passRate*100)
	fmt.Printf("Reward: %.4f\n", reward)
	fmt.Printf("Tests: %d\n", len(results))
	fmt.Printf("Total Bugs: %d\n", TotalBugs())
	fmt.Printf("Bug Dependencies: %d\n", len(BugDependencies))
}
