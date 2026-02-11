package environment

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

// StepResult holds the outcome of an agent action.
type StepResult struct {
	Observation map[string]interface{}
	Reward      float64
	Done        bool
	Info        map[string]interface{}
}

// TestSummary holds parsed test run results.
type TestSummary struct {
	Total    int
	Passed   int
	Failed   int
	PassRate float64
	Targeted bool
	Output   string
}

// Environment manages the agent interaction loop.
type Environment struct {
	workDir         string
	maxSteps        int
	step            int
	mutatingSteps   int
	fullRunInterval int
	filesChanged    []string
	lastTestSummary TestSummary
}

var fileTestMap = map[string][]string{
	"internal/dispatch/":       {"./tests/unit/...", "./tests/integration/..."},
	"internal/estimator/":      {"./tests/unit/...", "./tests/integration/..."},
	"internal/topology/":       {"./tests/unit/..."},
	"internal/outage/":         {"./tests/unit/...", "./tests/integration/..."},
	"internal/demandresponse/": {"./tests/unit/...", "./tests/integration/..."},
	"internal/security/":       {"./tests/unit/..."},
	"internal/resilience/":     {"./tests/unit/...", "./tests/integration/..."},
	"internal/workflow/":       {"./tests/unit/...", "./tests/integration/..."},
	"internal/concurrency/":    {"./tests/unit/..."},
	"internal/events/":         {"./tests/unit/..."},
	"internal/consensus/":      {"./tests/unit/..."},
	"internal/config/":         {"./tests/unit/..."},
	"services/":                {"./tests/services/..."},
	"pkg/models/":              {"./tests/unit/...", "./tests/integration/..."},
	"shared/contracts/":        {"./tests/services/..."},
	"migrations/":              {"./tests/unit/..."},
}

// NewEnvironment creates a new environment instance.
func NewEnvironment(workDir string) *Environment {
	return &Environment{workDir: workDir, maxSteps: 260, fullRunInterval: 4, filesChanged: []string{}}
}

func (e *Environment) validatePath(rel string) (string, error) {
	if rel == "" || strings.Contains(rel, "..") || filepath.IsAbs(rel) {
		return "", fmt.Errorf("invalid path")
	}
	abs, err := filepath.Abs(filepath.Join(e.workDir, rel))
	if err != nil {
		return "", err
	}
	root, err := filepath.Abs(e.workDir)
	if err != nil {
		return "", err
	}
	if !strings.HasPrefix(abs, root+string(filepath.Separator)) && abs != root {
		return "", fmt.Errorf("path escapes workspace")
	}
	return abs, nil
}

func (e *Environment) validateAction(action map[string]string) error {
	t := action["type"]
	if t != "edit" && t != "read" && t != "run_command" {
		return fmt.Errorf("unknown action type")
	}
	if t == "edit" || t == "read" {
		rel := action["file"]
		if _, err := e.validatePath(rel); err != nil {
			return err
		}
		if t == "edit" && isTestPath(rel) {
			return fmt.Errorf("editing test files is not allowed")
		}
	}
	if t == "run_command" {
		parts := strings.Fields(action["command"])
		if len(parts) == 0 {
			return fmt.Errorf("empty command")
		}
		allow := map[string]bool{"go": true, "cat": true, "ls": true, "grep": true, "find": true, "head": true, "tail": true, "wc": true}
		if !allow[parts[0]] {
			return fmt.Errorf("command not allowed")
		}
	}
	return nil
}

func isTestPath(rel string) bool {
	normalized := strings.ReplaceAll(rel, "\\", "/")
	if strings.HasPrefix(normalized, "tests/") || strings.Contains(normalized, "/tests/") || strings.HasPrefix(normalized, "__tests__/") {
		return true
	}
	if strings.HasSuffix(normalized, "_test.go") {
		return true
	}
	return false
}

func (e *Environment) executeCommand(command string) (string, error) {
	parts := strings.Fields(command)
	cmd := exec.Command(parts[0], parts[1:]...)
	cmd.Dir = e.workDir
	out, err := cmd.CombinedOutput()
	return string(out), err
}

func (e *Environment) editFile(rel, content string) error {
	abs, err := e.validatePath(rel)
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(abs), 0o755); err != nil {
		return err
	}
	if err := os.WriteFile(abs, []byte(content), 0o644); err != nil {
		return err
	}
	e.filesChanged = append(e.filesChanged, rel)
	return nil
}

func (e *Environment) readFile(rel string) (string, error) {
	abs, err := e.validatePath(rel)
	if err != nil {
		return "", err
	}
	b, err := os.ReadFile(abs)
	if err != nil {
		return "", err
	}
	return string(b), nil
}

func parseGoTestSummary(output string, targeted bool) TestSummary {
	passed := strings.Count(output, "--- PASS:")
	failed := strings.Count(output, "--- FAIL:")
	total := passed + failed
	passRate := 0.0
	if total > 0 {
		passRate = float64(passed) / float64(total)
	}
	return TestSummary{Total: total, Passed: passed, Failed: failed, PassRate: passRate, Targeted: targeted, Output: output}
}

func (e *Environment) runFullTests() TestSummary {
	out, _ := e.executeCommand("go test -race -v ./...")
	return parseGoTestSummary(out, false)
}

func (e *Environment) testsForFile(rel string) []string {
	for prefix, tests := range fileTestMap {
		if strings.HasPrefix(rel, prefix) {
			return tests
		}
	}
	return nil
}

func (e *Environment) runTargetedTests(rel string) TestSummary {
	targets := e.testsForFile(rel)
	if len(targets) == 0 {
		return TestSummary{Targeted: true}
	}
	out, _ := e.executeCommand("go test -race -v " + strings.Join(uniqueStrings(targets), " "))
	return parseGoTestSummary(out, true)
}

func uniqueStrings(values []string) []string {
	seen := map[string]struct{}{}
	out := make([]string, 0, len(values))
	for _, value := range values {
		if _, ok := seen[value]; ok {
			continue
		}
		seen[value] = struct{}{}
		out = append(out, value)
	}
	return out
}

// Reset initializes the environment and runs a baseline test suite.
func (e *Environment) Reset() StepResult {
	e.step = 0
	e.mutatingSteps = 0
	e.filesChanged = []string{}
	e.lastTestSummary = e.runFullTests()
	summary := e.lastTestSummary
	obs := map[string]interface{}{"action_result": "", "reward": 0.0, "step": 0, "test_summary": map[string]interface{}{"total": summary.Total, "passed": summary.Passed, "failed": summary.Failed, "pass_rate": summary.PassRate, "targeted": summary.Targeted}}
	info := map[string]interface{}{"step": 0, "max_steps": e.maxSteps, "total_bugs": TotalBugs(), "target_tests": TotalTests(), "files_changed": e.filesChanged, "pass_rate": summary.PassRate, "tests_total": summary.Total, "tests_failed": summary.Failed, "targeted_run": summary.Targeted}
	return StepResult{Observation: obs, Reward: 0.0, Done: false, Info: info}
}

// Step executes one agent action and evaluates progress.
func (e *Environment) Step(action map[string]string) StepResult {
	e.step++
	if err := e.validateAction(action); err != nil {
		return StepResult{Observation: map[string]interface{}{"action_result": "", "step": e.step}, Reward: 0.0, Done: e.step >= e.maxSteps, Info: map[string]interface{}{"error": err.Error(), "step": e.step}}
	}
	actionType := action["type"]
	result := ""
	var err error
	switch actionType {
	case "edit":
		err = e.editFile(action["file"], action["content"])
		result = "edit applied"
	case "read":
		result, err = e.readFile(action["file"])
	case "run_command":
		result, err = e.executeCommand(action["command"])
	}

	summary := e.lastTestSummary
	if actionType == "edit" || actionType == "run_command" {
		e.mutatingSteps++
		targeted := TestSummary{Targeted: true}
		if actionType == "edit" {
			targeted = e.runTargetedTests(action["file"])
		}
		if targeted.Total > 0 && e.mutatingSteps%e.fullRunInterval != 0 && targeted.PassRate < 1.0 {
			summary = targeted
		} else {
			summary = e.runFullTests()
		}
	}

	reward := SparseReward(summary.PassRate)
	e.lastTestSummary = summary
	done := e.step >= e.maxSteps || (!summary.Targeted && summary.Total > 0 && summary.PassRate >= 1.0)

	info := map[string]interface{}{"step": e.step, "max_steps": e.maxSteps, "total_bugs": TotalBugs(), "target_tests": TotalTests(), "files_changed": e.filesChanged, "pass_rate": summary.PassRate, "tests_total": summary.Total, "tests_failed": summary.Failed, "targeted_run": summary.Targeted}
	if err != nil {
		info["error"] = err.Error()
	}
	obs := map[string]interface{}{"action_result": result, "reward": reward, "step": e.step, "test_summary": map[string]interface{}{"total": summary.Total, "passed": summary.Passed, "failed": summary.Failed, "pass_rate": summary.PassRate, "targeted": summary.Targeted}}
	return StepResult{Observation: obs, Reward: reward, Done: done, Info: info}
}
