package environment

import (
	"bufio"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"
	"time"
)

// ActionType represents the type of agent action
type ActionType string

const (
	ActionEdit    ActionType = "EDIT"
	ActionRun     ActionType = "RUN"
	ActionView    ActionType = "VIEW"
	ActionTest    ActionType = "TEST"
	ActionTestBug ActionType = "TEST_BUG"
)

// SpaceEntry describes a single dimension in an observation or action space
type SpaceEntry struct {
	Name        string
	Type        string // "string", "int", "float", "bool", "list"
	Description string
	Range       [2]float64 // For numeric types: [min, max]
	MaxLength   int        // For string/list types
}

// ObservationSpace defines the structure of observations returned by the environment
var ObservationSpace = []SpaceEntry{
	{Name: "test_output", Type: "string", Description: "Raw output from test execution", MaxLength: 100000},
	{Name: "test_results", Type: "object", Description: "Structured test results by category"},
	{Name: "total_tests", Type: "int", Description: "Total number of tests executed", Range: [2]float64{0, 600}},
	{Name: "passed_tests", Type: "int", Description: "Number of tests passed", Range: [2]float64{0, 600}},
	{Name: "failed_tests", Type: "int", Description: "Number of tests failed", Range: [2]float64{0, 600}},
	{Name: "pass_rate", Type: "float", Description: "Fraction of tests passing", Range: [2]float64{0.0, 1.0}},
	{Name: "bug_progress", Type: "object", Description: "Per-bug fix progress (0.0 to 1.0 per bug ID)"},
	{Name: "dependency_status", Type: "object", Description: "Which bug dependencies are met"},
	{Name: "categories", Type: "object", Description: "Per-category pass/fail breakdown"},
	{Name: "error", Type: "string", Description: "Error message if action failed", MaxLength: 10000},
	{Name: "step_number", Type: "int", Description: "Current step in episode", Range: [2]float64{0, 200}},
	{Name: "elapsed_time", Type: "string", Description: "Wall clock time since reset"},
	{Name: "reward", Type: "float", Description: "Reward for this step", Range: [2]float64{-1.0, 1.0}},
	{Name: "done", Type: "bool", Description: "Whether episode is complete"},
	{Name: "files_changed", Type: "list", Description: "List of files modified since last reset"},
}

// ActionSpace defines the valid action formats
var ActionSpace = []SpaceEntry{
	{Name: "EDIT", Type: "string", Description: "Edit a file. Format: EDIT:<filepath>:<line>:<content>", MaxLength: 100000},
	{Name: "RUN", Type: "string", Description: "Run a shell command. Format: RUN:<command>", MaxLength: 10000},
	{Name: "VIEW", Type: "string", Description: "View a file. Format: VIEW:<filepath>[:<start_line>:<end_line>]", MaxLength: 1000},
	{Name: "TEST", Type: "string", Description: "Run tests for a category. Format: TEST:<category> where category is unit|integration|security|chaos|performance|race|all", MaxLength: 100},
	{Name: "TEST_BUG", Type: "string", Description: "Run tests for a specific bug. Format: TEST_BUG:<bug_id> where bug_id is e.g. A1, F1, L2", MaxLength: 20},
}

// ValidationError describes why an action is invalid
type ValidationError struct {
	Action  string
	Reason  string
	Hint    string
}

func (e *ValidationError) Error() string {
	return fmt.Sprintf("invalid action %q: %s (hint: %s)", e.Action, e.Reason, e.Hint)
}

// Environment represents the TradeEngine RL debugging environment
type Environment struct {
	workDir       string
	startTime     time.Time
	testResults   map[string]bool
	bugsFixes     map[string]bool
	dockerUp      bool
	stepCount     int
	maxSteps      int
	filesChanged  []string
	previousObs   *Observation
	rewardCalc    *RewardCalculator
}

// NewEnvironment creates a new environment instance
func NewEnvironment(workDir string) *Environment {
	return NewEnvironmentWithMaxSteps(workDir, 200)
}

// NewEnvironmentWithMaxSteps creates a new environment with a custom step limit
func NewEnvironmentWithMaxSteps(workDir string, maxSteps int) *Environment {
	return &Environment{
		workDir:      workDir,
		testResults:  make(map[string]bool),
		bugsFixes:    make(map[string]bool),
		maxSteps:     maxSteps,
		rewardCalc:   NewRewardCalculator(),
		filesChanged: make([]string, 0),
	}
}

// GetObservationSpace returns the observation space definition
func (e *Environment) GetObservationSpace() []SpaceEntry {
	return ObservationSpace
}

// GetActionSpace returns the action space definition
func (e *Environment) GetActionSpace() []SpaceEntry {
	return ActionSpace
}

// ValidateAction checks if an action is valid before execution
func (e *Environment) ValidateAction(action string) *ValidationError {
	if action == "" {
		return &ValidationError{
			Action: action,
			Reason: "empty action",
			Hint:   "provide an action in format TYPE:content, e.g. EDIT:file.go:10:new_content or RUN:go test ./...",
		}
	}

	parts := strings.SplitN(action, ":", 2)
	if len(parts) < 2 {
		return &ValidationError{
			Action: action,
			Reason: "missing action type prefix",
			Hint:   "actions must start with EDIT:, RUN:, VIEW:, TEST:, or TEST_BUG:",
		}
	}

	actionType := ActionType(parts[0])
	content := parts[1]

	switch actionType {
	case ActionEdit:
		editParts := strings.SplitN(content, ":", 3)
		if len(editParts) < 3 {
			return &ValidationError{
				Action: action,
				Reason: "EDIT requires file:line:content format",
				Hint:   "use EDIT:<filepath>:<line_number>:<new_content>",
			}
		}
		if filepath.IsAbs(editParts[0]) || strings.Contains(editParts[0], "..") {
			return &ValidationError{
				Action: action,
				Reason: "path traversal not allowed",
				Hint:   "use relative paths within the project directory",
			}
		}
		filePath := filepath.Join(e.workDir, editParts[0])
		if _, err := os.Stat(filePath); os.IsNotExist(err) {
			return &ValidationError{
				Action: action,
				Reason: fmt.Sprintf("file does not exist: %s", editParts[0]),
				Hint:   "check the file path relative to the project root",
			}
		}
		// Reject edits to test files
		if strings.HasSuffix(editParts[0], "_test.go") ||
			strings.HasPrefix(editParts[0], "tests/") ||
			strings.HasPrefix(editParts[0], "test/") ||
			strings.Contains(editParts[0], "/tests/") ||
			strings.Contains(editParts[0], "/test/") {
			return &ValidationError{
				Action: action,
				Reason: "editing test files is not allowed",
				Hint:   "fix the source code, not the tests",
			}
		}

	case ActionRun:
		if content == "" {
			return &ValidationError{
				Action: action,
				Reason: "RUN requires a command",
				Hint:   "use RUN:<shell_command>",
			}
		}
		// Allowlist-based command validation
		runParts := strings.Fields(content)
		if len(runParts) > 0 {
			safeCommands := map[string]bool{
				"go": true, "docker": true, "cat": true, "ls": true,
				"grep": true, "find": true, "head": true, "tail": true, "wc": true,
			}
			if !safeCommands[runParts[0]] {
				return &ValidationError{
					Action: action,
					Reason: fmt.Sprintf("command not allowed: %s", runParts[0]),
					Hint:   "allowed commands: go, docker, cat, ls, grep, find, head, tail, wc",
				}
			}
		}

	case ActionView:
		if content == "" {
			return &ValidationError{
				Action: action,
				Reason: "VIEW requires a file path",
				Hint:   "use VIEW:<filepath> or VIEW:<filepath>:<start>:<end>",
			}
		}
		viewParts := strings.SplitN(content, ":", 3)
		if filepath.IsAbs(viewParts[0]) || strings.Contains(viewParts[0], "..") {
			return &ValidationError{
				Action: action,
				Reason: "path traversal not allowed",
				Hint:   "use relative paths within the project directory",
			}
		}

	case ActionTest:
		validCategories := map[string]bool{
			"unit": true, "integration": true, "security": true,
			"chaos": true, "performance": true, "race": true, "all": true,
		}
		if !validCategories[content] {
			return &ValidationError{
				Action: action,
				Reason: fmt.Sprintf("unknown test category: %s", content),
				Hint:   "valid categories: unit, integration, security, chaos, performance, race, all",
			}
		}

	case ActionTestBug:
		if _, ok := BugTestMapping[content]; !ok {
			return &ValidationError{
				Action: action,
				Reason: fmt.Sprintf("unknown bug ID: %s", content),
				Hint:   fmt.Sprintf("valid bug IDs: L1-L8, A1-A12, B1-B8, C1-C8, D1-D10, E1-E8, F1-F10, G1-G6, H1-H5, I1-I6, J1-J4"),
			}
		}

	default:
		return &ValidationError{
			Action: action,
			Reason: fmt.Sprintf("unknown action type: %s", parts[0]),
			Hint:   "valid action types: EDIT, RUN, VIEW, TEST, TEST_BUG",
		}
	}

	return nil
}

// Reset resets the environment to initial state
func (e *Environment) Reset() (*Observation, error) {
	e.startTime = time.Now()
	e.testResults = make(map[string]bool)
	e.bugsFixes = make(map[string]bool)
	e.stepCount = 0
	e.filesChanged = make([]string, 0)
	e.rewardCalc = NewRewardCalculator()

	// Reset git state
	cmd := exec.Command("git", "checkout", ".")
	cmd.Dir = e.workDir
	if err := cmd.Run(); err != nil {
		return nil, fmt.Errorf("failed to reset git state: %w", err)
	}
	cleanCmd := exec.Command("git", "clean", "-fd")
	cleanCmd.Dir = e.workDir
	cleanCmd.Run()

	// Restart Docker services
	if err := e.restartDocker(); err != nil {
		return nil, fmt.Errorf("failed to restart docker: %w", err)
	}

	// Run initial tests to provide baseline observation
	testResults, err := e.runTests()
	if err != nil {
		return &Observation{
			Error:      err.Error(),
			StepNumber: 0,
		}, nil
	}

	obs := e.buildObservation("", testResults, 0.0, false)
	return obs, nil
}

// restartDocker restarts all Docker services
func (e *Environment) restartDocker() error {
	// Stop containers
	stopCmd := exec.Command("docker", "compose", "down", "-v")
	stopCmd.Dir = e.workDir
	stopCmd.Run()

	// Start containers
	startCmd := exec.Command("docker", "compose", "up", "-d")
	startCmd.Dir = e.workDir
	if err := startCmd.Run(); err != nil {
		return err
	}

	// Wait for services to be healthy
	time.Sleep(10 * time.Second)
	e.dockerUp = true

	return nil
}

// Step executes an action and returns observation, reward, done
func (e *Environment) Step(action string) (Observation, float64, bool, error) {
	e.stepCount++

	// Check max steps
	if e.stepCount > e.maxSteps {
		obs := Observation{
			Error:      "maximum steps exceeded",
			StepNumber: e.stepCount,
			Done:       true,
		}
		return obs, -0.01, true, nil
	}

	// Validate action
	if valErr := e.ValidateAction(action); valErr != nil {
		return Observation{Error: valErr.Error(), StepNumber: e.stepCount}, -0.01, false, nil
	}

	// Execute the action
	output, err := e.executeAction(action)
	if err != nil {
		return Observation{TestOutput: output, Error: err.Error(), StepNumber: e.stepCount}, -0.01, false, nil
	}

	// Run tests (either targeted or full)
	var testResults *TestResults
	isFullRun := false
	if strings.HasPrefix(action, "TEST_BUG:") {
		bugID := action[9:]
		testResults, err = e.runTestsForBug(bugID)
	} else if strings.HasPrefix(action, "TEST:") {
		category := action[5:]
		if category == "all" {
			testResults, err = e.runTests()
			isFullRun = true
		} else {
			testResults, err = e.runTestsByCategory(category)
		}
	} else {
		testResults, err = e.runTests()
		isFullRun = true
	}

	if err != nil {
		return Observation{TestOutput: output, Error: err.Error(), StepNumber: e.stepCount}, -0.01, false, nil
	}

	// If targeted tests all pass, run full suite to confirm
	if !isFullRun && testResults.AllPassed {
		testResults, err = e.runTests()
		if err != nil {
			return Observation{TestOutput: output, Error: err.Error(), StepNumber: e.stepCount}, -0.01, false, nil
		}
		isFullRun = true
	}

	// Calculate reward
	reward := e.calculateReward(testResults)

	// Only mark done if a full test run confirms all tests pass
	done := isFullRun && testResults.AllPassed

	obs := e.buildObservation(output, testResults, reward, done)

	return *obs, reward, done, nil
}

// buildObservation constructs a full observation from test results
func (e *Environment) buildObservation(output string, results *TestResults, reward float64, done bool) *Observation {
	obs := &Observation{
		TestOutput:  output,
		TestResults: results,
		StepNumber:  e.stepCount,
		Elapsed:     time.Since(e.startTime).String(),
		Reward:      reward,
		Done:        done,
	}

	if results != nil {
		// Calculate bug progress
		obs.BugProgress = e.rewardCalc.GetBugProgress(results)

		// Calculate dependency status
		fixedBugs := make(map[string]bool)
		for bugID, progress := range obs.BugProgress {
			if progress >= 1.0 {
				fixedBugs[bugID] = true
			}
		}
		obs.DependencyStatus = make(map[string]bool)
		for bugID := range BugTestMapping {
			obs.DependencyStatus[bugID] = AreDependenciesMet(bugID, fixedBugs)
		}

		obs.FilesChanged = e.filesChanged

		// Calculate pass rate
		if results.TotalTests > 0 {
			obs.PassRate = float64(results.PassedTests) / float64(results.TotalTests)
		}
	}

	return obs
}

// executeAction executes the given action
func (e *Environment) executeAction(action string) (string, error) {
	parts := strings.SplitN(action, ":", 2)
	actionType := ActionType(parts[0])
	content := parts[1]

	switch actionType {
	case ActionEdit:
		return e.handleEdit(content)
	case ActionRun:
		return e.handleRun(content)
	case ActionView:
		return e.handleView(content)
	case ActionTest, ActionTestBug:
		return "", nil // Tests are run separately after action
	default:
		return "", fmt.Errorf("unknown action type: %s", parts[0])
	}
}

// handleEdit handles file edit actions
func (e *Environment) handleEdit(editSpec string) (string, error) {
	// Parse edit specification (file:line:content)
	parts := strings.SplitN(editSpec, ":", 3)
	if len(parts) < 3 {
		return "", fmt.Errorf("invalid edit spec: expected file:line:content")
	}

	relPath := parts[0]
	content := parts[2]

	// Path safety: reject absolute and traversal paths
	if filepath.IsAbs(relPath) || strings.Contains(relPath, "..") {
		return "", fmt.Errorf("path traversal not allowed")
	}

	filePath := filepath.Join(e.workDir, relPath)
	absPath, err := filepath.Abs(filePath)
	if err != nil {
		return "", fmt.Errorf("invalid path: %w", err)
	}
	absWorkDir, err := filepath.Abs(e.workDir)
	if err != nil {
		return "", fmt.Errorf("invalid work dir: %w", err)
	}
	if !strings.HasPrefix(absPath, absWorkDir+string(filepath.Separator)) && absPath != absWorkDir {
		return "", fmt.Errorf("path escapes work directory")
	}

	// Track file changes
	found := false
	for _, f := range e.filesChanged {
		if f == relPath {
			found = true
			break
		}
	}
	if !found {
		e.filesChanged = append(e.filesChanged, relPath)
	}

	// Ensure parent directory exists
	dir := filepath.Dir(absPath)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return "", fmt.Errorf("cannot create directory: %w", err)
	}

	// Write the file
	if err := os.WriteFile(absPath, []byte(content), 0644); err != nil {
		return "", fmt.Errorf("write failed: %w", err)
	}

	return "Edit applied to " + relPath, nil
}

// handleRun handles command execution with allowlisted commands
func (e *Environment) handleRun(command string) (string, error) {
	parts := strings.Fields(command)
	if len(parts) == 0 {
		return "", fmt.Errorf("empty command")
	}

	safeCommands := map[string]bool{
		"go": true, "docker": true, "cat": true, "ls": true,
		"grep": true, "find": true, "head": true, "tail": true, "wc": true,
	}
	if !safeCommands[parts[0]] {
		return "", fmt.Errorf("command not allowed: %s", parts[0])
	}

	cmd := exec.Command(parts[0], parts[1:]...)
	cmd.Dir = e.workDir
	output, err := cmd.CombinedOutput()
	return string(output), err
}

// handleView handles file viewing
func (e *Environment) handleView(viewSpec string) (string, error) {
	parts := strings.SplitN(viewSpec, ":", 3)
	relPath := parts[0]

	if filepath.IsAbs(relPath) || strings.Contains(relPath, "..") {
		return "", fmt.Errorf("path traversal not allowed")
	}

	filePath := filepath.Join(e.workDir, relPath)
	absPath, err := filepath.Abs(filePath)
	if err != nil {
		return "", fmt.Errorf("invalid path: %w", err)
	}
	absWorkDir, _ := filepath.Abs(e.workDir)
	if !strings.HasPrefix(absPath, absWorkDir+string(filepath.Separator)) && absPath != absWorkDir {
		return "", fmt.Errorf("path escapes work directory")
	}

	data, err := os.ReadFile(absPath)
	if err != nil {
		return "", fmt.Errorf("cannot read file: %w", err)
	}

	return string(data), nil
}

// runTestsForBug runs only the tests associated with a specific bug ID
func (e *Environment) runTestsForBug(bugID string) (*TestResults, error) {
	tests, ok := BugTestMapping[bugID]
	if !ok {
		return nil, fmt.Errorf("unknown bug ID: %s", bugID)
	}

	results := &TestResults{
		Categories: make(map[string]CategoryResult),
	}

	// Build a regex to match only the specified test functions
	testPattern := strings.Join(tests, "|")
	runArg := fmt.Sprintf("-run=%s", testPattern)

	cmd := exec.Command("go", "test", "./...", "-v", "-count=1", runArg)
	cmd.Dir = e.workDir
	output, _ := cmd.CombinedOutput()

	result := e.parseTestOutput(string(output), "targeted")
	results.Categories["targeted"] = result

	results.TotalTests = result.Total
	results.PassedTests = result.Passed
	results.FailedTests = result.Failed
	results.AllPassed = result.Failed == 0 && result.Total > 0

	return results, nil
}

// runTestsByCategory runs tests for a specific category
func (e *Environment) runTestsByCategory(category string) (*TestResults, error) {
	results := &TestResults{
		Categories: make(map[string]CategoryResult),
	}

	var result CategoryResult
	switch category {
	case "unit":
		result = e.runTestCategory("./tests/unit/...", "unit")
	case "integration":
		result = e.runTestCategory("./tests/integration/...", "integration")
	case "security":
		result = e.runTestCategory("./tests/security/...", "security")
	case "chaos":
		result = e.runTestCategory("./tests/chaos/...", "chaos")
	case "performance":
		result = e.runTestCategory("./tests/performance/...", "performance")
	case "race":
		result = e.runTestWithRace()
	default:
		return nil, fmt.Errorf("unknown category: %s", category)
	}

	results.Categories[category] = result
	results.TotalTests = result.Total
	results.PassedTests = result.Passed
	results.FailedTests = result.Failed
	results.AllPassed = result.Failed == 0 && result.Total > 0

	return results, nil
}

// runTests runs all tests and returns results
func (e *Environment) runTests() (*TestResults, error) {
	results := &TestResults{
		Categories: make(map[string]CategoryResult),
	}

	// Run unit tests
	unitResult := e.runTestCategory("./tests/unit/...", "unit")
	results.Categories["unit"] = unitResult

	// Run integration tests
	integrationResult := e.runTestCategory("./tests/integration/...", "integration")
	results.Categories["integration"] = integrationResult

	// Run security tests
	securityResult := e.runTestCategory("./tests/security/...", "security")
	results.Categories["security"] = securityResult

	// Run chaos tests
	chaosResult := e.runTestCategory("./tests/chaos/...", "chaos")
	results.Categories["chaos"] = chaosResult

	// Run performance tests
	perfResult := e.runTestCategory("./tests/performance/...", "performance")
	results.Categories["performance"] = perfResult

	// Run with race detector
	raceResult := e.runTestWithRace()
	results.Categories["race"] = raceResult

	// Calculate totals
	for _, cat := range results.Categories {
		results.TotalTests += cat.Total
		results.PassedTests += cat.Passed
		results.FailedTests += cat.Failed
	}

	results.AllPassed = results.FailedTests == 0 && results.TotalTests > 0

	return results, nil
}

// runTestCategory runs tests for a specific category
func (e *Environment) runTestCategory(path, category string) CategoryResult {
	cmd := exec.Command("go", "test", path, "-v", "-count=1")
	cmd.Dir = e.workDir
	output, _ := cmd.CombinedOutput()

	return e.parseTestOutput(string(output), category)
}

// runTestWithRace runs tests with race detector
func (e *Environment) runTestWithRace() CategoryResult {
	cmd := exec.Command("go", "test", "./...", "-race", "-v", "-count=1", "-short")
	cmd.Dir = e.workDir
	output, _ := cmd.CombinedOutput()

	return e.parseTestOutput(string(output), "race")
}

// parseTestOutput parses go test output
func (e *Environment) parseTestOutput(output, category string) CategoryResult {
	result := CategoryResult{
		Category: category,
	}

	passRegex := regexp.MustCompile(`--- PASS: (\S+)`)
	failRegex := regexp.MustCompile(`--- FAIL: (\S+)`)

	scanner := bufio.NewScanner(strings.NewReader(output))
	for scanner.Scan() {
		line := scanner.Text()

		if matches := passRegex.FindStringSubmatch(line); matches != nil {
			result.Passed++
			result.Total++
		}
		if matches := failRegex.FindStringSubmatch(line); matches != nil {
			result.Failed++
			result.Total++
			result.FailedTests = append(result.FailedTests, matches[1])
		}
	}

	return result
}

// calculateReward calculates the reward based on test results
func (e *Environment) calculateReward(results *TestResults) float64 {
	return e.rewardCalc.Calculate(results, e.testResults)
}

// GetInfo returns environment info
func (e *Environment) GetInfo() map[string]interface{} {
	return map[string]interface{}{
		"work_dir":      e.workDir,
		"elapsed_time":  time.Since(e.startTime).String(),
		"docker_up":     e.dockerUp,
		"total_bugs":    TotalBugs(),
		"total_tests":   TotalTests(),
		"step_count":    e.stepCount,
		"max_steps":     e.maxSteps,
		"files_changed": e.filesChanged,
		"bug_categories": BugCategories(),
		"dependency_count": len(BugDependencies),
	}
}

// GetBugDependencies returns the bug dependency graph for agent inspection
func (e *Environment) GetBugDependencies() map[string][]string {
	return BugDependencies
}

// GetUnblockedBugs returns bugs whose dependencies are all satisfied
func (e *Environment) GetUnblockedBugs(fixedBugs map[string]bool) []string {
	var unblocked []string
	for bugID := range BugTestMapping {
		if fixedBugs[bugID] {
			continue // Already fixed
		}
		if AreDependenciesMet(bugID, fixedBugs) {
			unblocked = append(unblocked, bugID)
		}
	}
	return unblocked
}

// Observation represents the observation returned by the environment
type Observation struct {
	TestOutput       string
	TestResults      *TestResults
	Error            string
	StepNumber       int
	Elapsed          string
	Reward           float64
	Done             bool
	PassRate         float64
	BugProgress      map[string]float64
	DependencyStatus map[string]bool
	FilesChanged     []string
}

// TestResults contains test execution results
type TestResults struct {
	Categories  map[string]CategoryResult
	TotalTests  int
	PassedTests int
	FailedTests int
	AllPassed   bool
}

// CategoryResult contains results for a test category
type CategoryResult struct {
	Category    string
	Total       int
	Passed      int
	Failed      int
	FailedTests []string
}

// GymStep is a Gymnasium-compatible step returning (observation, reward, done, error)
func (e *Environment) GymStep(action string) (Observation, float64, bool, error) {
	return e.Step(action)
}

// Close cleans up the environment
func (e *Environment) Close() error {
	// Stop Docker
	cmd := exec.Command("docker", "compose", "down")
	cmd.Dir = e.workDir
	return cmd.Run()
}

// Main entry point for standalone execution
func main() {
	workDir, err := os.Getwd()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error getting work dir: %v\n", err)
		os.Exit(1)
	}

	env := NewEnvironment(workDir)

	obs, err := env.Reset()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error resetting environment: %v\n", err)
		os.Exit(1)
	}

	fmt.Println("TradeEngine environment initialized")
	fmt.Printf("Observation/Action spaces defined\n")
	fmt.Printf("  Observation fields: %d\n", len(ObservationSpace))
	fmt.Printf("  Action types: %d\n", len(ActionSpace))
	fmt.Printf("  Total bugs: %d\n", TotalBugs())
	fmt.Printf("  Bug dependencies: %d entries\n", len(BugDependencies))
	fmt.Printf("  Max steps: %d\n", env.maxSteps)

	if obs.TestResults != nil {
		results := obs.TestResults
		fmt.Printf("\nInitial Test Results:\n")
		fmt.Printf("Total: %d, Passed: %d, Failed: %d\n",
			results.TotalTests, results.PassedTests, results.FailedTests)

		for name, cat := range results.Categories {
			fmt.Printf("  %s: %d/%d passed\n", name, cat.Passed, cat.Total)
		}
	}

	fmt.Printf("\nBug Dependency Chains:\n")
	chains := GetDependencyChains()
	for _, chain := range chains {
		fmt.Printf("  %s\n", strings.Join(chain, " -> "))
	}
}
