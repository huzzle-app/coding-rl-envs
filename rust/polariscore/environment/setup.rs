use std::collections::HashMap;
use std::fs;
use std::path::{Component, Path, PathBuf};
use std::process::Command;

#[derive(Clone, Default, Debug)]
pub struct TestSummary {
    pub total: usize,
    pub passed: usize,
    pub failed: usize,
    pub pass_rate: f64,
    pub targeted: bool,
    pub output: String,
}

#[derive(Clone, Debug)]
pub struct StepResult {
    pub observation: HashMap<String, String>,
    pub reward: f64,
    pub done: bool,
    pub info: HashMap<String, String>,
}

pub struct PolarisCoreEnvironment {
    pub work_dir: String,
    pub max_steps: usize,
    pub step_count: usize,
    mutating_steps: usize,
    full_run_interval: usize,
    pub files_changed: Vec<String>,
    last_test_summary: TestSummary,
}

impl PolarisCoreEnvironment {
    pub fn new(work_dir: impl AsRef<Path>) -> Self {
        Self {
            work_dir: work_dir.as_ref().to_string_lossy().to_string(),
            max_steps: 500,
            step_count: 0,
            mutating_steps: 0,
            full_run_interval: 5,
            files_changed: Vec::new(),
            last_test_summary: TestSummary::default(),
        }
    }

    fn safe_path(&self, rel: &str) -> Result<PathBuf, String> {
        if rel.is_empty() {
            return Err("invalid path".to_string());
        }
        let rel_path = Path::new(rel);
        if rel_path.is_absolute() {
            return Err("invalid path".to_string());
        }
        for component in rel_path.components() {
            if matches!(component, Component::ParentDir | Component::RootDir) {
                return Err("invalid path".to_string());
            }
        }
        let root = Path::new(&self.work_dir)
            .canonicalize()
            .map_err(|e| e.to_string())?;
        let target = root.join(rel_path);
        if !target.starts_with(&root) {
            return Err("path escapes workspace".to_string());
        }
        Ok(target)
    }

    fn is_test_path(rel: &str) -> bool {
        let normalized = rel.replace('\\', "/");
        normalized.starts_with("tests/")
            || normalized.contains("/tests/")
            || normalized.starts_with("__tests__/")
            || normalized.ends_with("_test.rs")
    }

    fn validate_command(command: &str) -> Result<Vec<String>, String> {
        if command
            .chars()
            .any(|ch| [';', '&', '|', '`', '$', '>', '<'].contains(&ch))
        {
            return Err("unsupported shell metacharacters".to_string());
        }

        let parts: Vec<String> = command
            .split_whitespace()
            .map(|item| item.to_string())
            .collect();
        if parts.is_empty() {
            return Err("empty command".to_string());
        }
        let allowed = ["cargo", "cat", "ls", "grep", "find", "head", "tail", "wc"];
        if !allowed.contains(&parts[0].as_str()) {
            return Err("command not allowed".to_string());
        }
        Ok(parts)
    }

    fn validate_action(&self, action: &HashMap<String, String>) -> Result<(), String> {
        let action_type = action.get("type").map(String::as_str).unwrap_or("");
        if action_type != "edit" && action_type != "read" && action_type != "run_command" {
            return Err("unknown action type".to_string());
        }
        if action_type == "edit" || action_type == "read" {
            let rel = action.get("file").map(String::as_str).unwrap_or("");
            let _ = self.safe_path(rel)?;
            if action_type == "edit" && Self::is_test_path(rel) {
                return Err("editing test files is not allowed".to_string());
            }
        }
        if action_type == "run_command" {
            let command = action.get("command").map(String::as_str).unwrap_or("");
            let _ = Self::validate_command(command)?;
        }
        Ok(())
    }

    fn execute_command(&self, command: &str) -> Result<String, String> {
        let parts = Self::validate_command(command)?;
        let mut iter = parts.iter();
        let binary = iter.next().ok_or_else(|| "empty command".to_string())?;
        let args: Vec<&str> = iter.map(String::as_str).collect();
        let output = Command::new(binary)
            .args(args)
            .current_dir(&self.work_dir)
            .output()
            .map_err(|e| e.to_string())?;
        Ok(format!(
            "{}{}",
            String::from_utf8_lossy(&output.stdout),
            String::from_utf8_lossy(&output.stderr)
        ))
    }

    fn edit(&mut self, rel: &str, content: &str) -> Result<String, String> {
        let target = self.safe_path(rel)?;
        if let Some(parent) = target.parent() {
            fs::create_dir_all(parent).map_err(|e| e.to_string())?;
        }
        fs::write(&target, content).map_err(|e| e.to_string())?;
        self.files_changed.push(rel.to_string());
        Ok(format!("edited {}", rel))
    }

    fn read(&self, rel: &str) -> Result<String, String> {
        let target = self.safe_path(rel)?;
        fs::read_to_string(target).map_err(|e| e.to_string())
    }

    fn tests_for_file(&self, rel: &str) -> Vec<&'static str> {
        if rel.starts_with("src/allocator.rs") {
            return vec!["allocator_tests"];
        }
        if rel.starts_with("src/routing.rs") {
            return vec!["routing_tests", "workflow_integration_tests"];
        }
        if rel.starts_with("src/policy.rs") {
            return vec!["policy_tests", "chaos_replay_tests"];
        }
        if rel.starts_with("src/resilience.rs") {
            return vec!["resilience_tests", "chaos_replay_tests"];
        }
        if rel.starts_with("src/security.rs") {
            return vec!["security_tests"];
        }
        if rel.starts_with("src/queue.rs") || rel.starts_with("src/statistics.rs") {
            return vec!["queue_statistics_tests"];
        }
        if rel.starts_with("src/workflow.rs") || rel.starts_with("src/economics.rs") {
            return vec!["workflow_integration_tests"];
        }
        if rel.starts_with("services/") || rel.starts_with("shared/") {
            return vec!["services_contracts"];
        }
        if rel.starts_with("migrations/") {
            return vec!["services_contracts"];
        }
        Vec::new()
    }

    fn run_full_tests(&self) -> TestSummary {
        let output = self.execute_command("cargo test").unwrap_or_default();
        parse_cargo_test_summary(&output, false)
    }

    fn run_targeted_tests(&self, rel: &str) -> TestSummary {
        let targets = self.tests_for_file(rel);
        if targets.is_empty() {
            return TestSummary::default();
        }
        let mut command = String::from("cargo test");
        for target in targets {
            command.push_str(" --test ");
            command.push_str(target);
        }
        let output = self.execute_command(&command).unwrap_or_default();
        parse_cargo_test_summary(&output, true)
    }

    fn build_step_result(
        &self,
        action_result: String,
        summary: &TestSummary,
        reward: f64,
        done: bool,
        mut info: HashMap<String, String>,
    ) -> StepResult {
        let mut observation = HashMap::new();
        observation.insert("action_result".to_string(), action_result);
        observation.insert("step".to_string(), self.step_count.to_string());
        observation.insert("reward".to_string(), format!("{reward:.6}"));
        observation.insert("tests_total".to_string(), summary.total.to_string());
        observation.insert("tests_passed".to_string(), summary.passed.to_string());
        observation.insert("tests_failed".to_string(), summary.failed.to_string());
        observation.insert("pass_rate".to_string(), format!("{:.4}", summary.pass_rate));
        observation.insert("targeted_run".to_string(), summary.targeted.to_string());

        info.insert("step".to_string(), self.step_count.to_string());
        info.insert("max_steps".to_string(), self.max_steps.to_string());
        info.insert("total_bugs".to_string(), "1020".to_string());
        info.insert("target_tests".to_string(), "7800".to_string());
        info.insert("files_changed".to_string(), self.files_changed.join(","));
        info.insert("tests_total".to_string(), summary.total.to_string());
        info.insert("tests_failed".to_string(), summary.failed.to_string());
        info.insert("pass_rate".to_string(), format!("{:.4}", summary.pass_rate));
        info.insert("targeted_run".to_string(), summary.targeted.to_string());
        info.insert("test_output_chars".to_string(), summary.output.len().to_string());

        StepResult {
            observation,
            reward,
            done,
            info,
        }
    }

    pub fn reset(&mut self) -> StepResult {
        self.step_count = 0;
        self.mutating_steps = 0;
        self.files_changed.clear();
        self.last_test_summary = self.run_full_tests();
        let summary = self.last_test_summary.clone();
        self.build_step_result(String::new(), &summary, 0.0, false, HashMap::new())
    }

    pub fn step(&mut self, action: &HashMap<String, String>) -> StepResult {
        self.step_count += 1;
        if let Err(err) = self.validate_action(action) {
            let mut info = HashMap::new();
            info.insert("error".to_string(), err);
            return self.build_step_result(
                String::new(),
                &self.last_test_summary,
                0.0,
                self.step_count >= self.max_steps,
                info,
            );
        }

        let action_type = action.get("type").map(String::as_str).unwrap_or("");
        let mut info = HashMap::new();
        let action_result = match action_type {
            "edit" => self.edit(
                action.get("file").map(String::as_str).unwrap_or(""),
                action.get("content").map(String::as_str).unwrap_or(""),
            ),
            "read" => self.read(action.get("file").map(String::as_str).unwrap_or("")),
            "run_command" => {
                self.execute_command(action.get("command").map(String::as_str).unwrap_or(""))
            }
            _ => Err("unknown action type".to_string()),
        };

        let mut summary = self.last_test_summary.clone();
        if action_type == "edit" || action_type == "run_command" {
            self.mutating_steps += 1;
            let mut targeted = TestSummary::default();
            if action_type == "edit" {
                let rel = action.get("file").map(String::as_str).unwrap_or("");
                targeted = self.run_targeted_tests(rel);
            }
            if targeted.total > 0
                && self.mutating_steps % self.full_run_interval != 0
                && targeted.pass_rate < 1.0
            {
                summary = targeted;
            } else {
                summary = self.run_full_tests();
            }
        }

        let reward = sparse_reward(summary.pass_rate);
        self.last_test_summary = summary.clone();
        let done = self.step_count >= self.max_steps
            || (!summary.targeted && summary.total > 0 && summary.pass_rate >= 1.0);

        let rendered_result = match action_result {
            Ok(output) => output,
            Err(err) => {
                info.insert("error".to_string(), err);
                String::new()
            }
        };
        self.build_step_result(rendered_result, &summary, reward, done, info)
    }
}

fn parse_cargo_test_summary(output: &str, targeted: bool) -> TestSummary {
    let mut passed = 0usize;
    let mut failed = 0usize;
    for line in output.lines() {
        let trimmed = line.trim();
        if trimmed.starts_with("test result:") {
            passed += extract_count(trimmed, " passed;");
            failed += extract_count(trimmed, " failed;");
        }
    }
    if passed == 0 && failed == 0 {
        for line in output.lines() {
            let trimmed = line.trim_end();
            if trimmed.ends_with(" ... ok") {
                passed += 1;
            } else if trimmed.ends_with(" ... FAILED") {
                failed += 1;
            }
        }
    }
    let total = passed + failed;
    let pass_rate = if total > 0 {
        passed as f64 / total as f64
    } else {
        0.0
    };
    TestSummary {
        total,
        passed,
        failed,
        pass_rate,
        targeted,
        output: output.to_string(),
    }
}

fn extract_count(line: &str, marker: &str) -> usize {
    if let Some(idx) = line.find(marker) {
        return line[..idx]
            .split_whitespace()
            .last()
            .unwrap_or("0")
            .parse::<usize>()
            .unwrap_or(0);
    }
    0
}

fn sparse_reward(pass_rate: f64) -> f64 {
    const THRESHOLDS: [f64; 9] = [0.20, 0.36, 0.50, 0.64, 0.76, 0.87, 0.94, 0.98, 1.0];
    const REWARDS: [f64; 9] = [0.0, 0.02, 0.07, 0.14, 0.25, 0.40, 0.60, 0.82, 1.0];
    for idx in (0..THRESHOLDS.len()).rev() {
        if pass_rate >= THRESHOLDS[idx] {
            return REWARDS[idx];
        }
    }
    0.0
}
