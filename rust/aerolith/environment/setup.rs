use std::collections::HashMap;
use std::fs;
use std::path::{Component, Path, PathBuf};
use std::process::Command;

#[derive(Clone, Default)]
struct TestSummary {
    total: usize,
    passed: usize,
    failed: usize,
    pass_rate: f64,
    targeted: bool,
    output: String,
}

pub struct Environment {
    pub work_dir: String,
    pub step_count: usize,
    pub max_steps: usize,
    mutating_steps: usize,
    full_run_interval: usize,
    pub files_changed: Vec<String>,
    last_test_summary: TestSummary,
}

pub struct StepResult {
    pub observation: HashMap<String, String>,
    pub reward: f64,
    pub done: bool,
    pub info: HashMap<String, String>,
}

impl Environment {
    pub fn new(work_dir: &str) -> Self {
        Self { work_dir: work_dir.to_string(), step_count: 0, max_steps: 280, mutating_steps: 0, full_run_interval: 4, files_changed: Vec::new(), last_test_summary: TestSummary::default() }
    }

    fn safe_path(&self, rel: &str) -> Result<PathBuf, String> {
        if rel.is_empty() { return Err("invalid path".to_string()); }
        let rel_path = Path::new(rel);
        if rel_path.is_absolute() { return Err("invalid path".to_string()); }
        for component in rel_path.components() {
            if matches!(component, Component::ParentDir | Component::RootDir) { return Err("invalid path".to_string()); }
        }
        let root = Path::new(&self.work_dir).canonicalize().map_err(|e| e.to_string())?;
        let target = root.join(rel_path);
        if !target.starts_with(&root) { return Err("path escapes workspace".to_string()); }
        Ok(target)
    }

    fn validate_action(&self, action: &HashMap<String, String>) -> Result<(), String> {
        let action_type = action.get("type").map(String::as_str).unwrap_or("");
        if action_type != "edit" && action_type != "read" && action_type != "run_command" { return Err("unknown action type".to_string()); }
        if action_type == "edit" || action_type == "read" {
            let rel = action.get("file").map(String::as_str).unwrap_or("");
            let _ = self.safe_path(rel)?;
            if action_type == "edit" {
                let normalized = rel.replace('\\', "/");
                let is_test_path = normalized.starts_with("tests/")
                    || normalized.contains("/tests/")
                    || normalized.starts_with("__tests__/")
                    || normalized.ends_with("_test.rs");
                if is_test_path { return Err("editing test files is not allowed".to_string()); }
            }
        }
        if action_type == "run_command" {
            let command = action.get("command").map(String::as_str).unwrap_or("");
            let parts: Vec<&str> = command.split_whitespace().collect();
            if parts.is_empty() { return Err("empty command".to_string()); }
            let allowed = ["cargo", "cat", "ls", "grep", "find", "head", "tail", "wc"];
            if !allowed.contains(&parts[0]) { return Err("command not allowed".to_string()); }
        }
        Ok(())
    }

    pub fn edit(&mut self, rel: &str, content: &str) -> Result<String, String> {
        let target = self.safe_path(rel)?;
        if let Some(parent) = target.parent() { fs::create_dir_all(parent).map_err(|e| e.to_string())?; }
        fs::write(&target, content).map_err(|e| e.to_string())?;
        self.files_changed.push(rel.to_string());
        Ok(format!("edited {}", rel))
    }

    pub fn read(&self, rel: &str) -> Result<String, String> {
        let target = self.safe_path(rel)?;
        fs::read_to_string(target).map_err(|e| e.to_string())
    }

    fn execute_command(&self, command: &str) -> Result<String, String> {
        let parts: Vec<&str> = command.split_whitespace().collect();
        if parts.is_empty() { return Err("empty command".to_string()); }
        let output = Command::new(parts[0]).args(&parts[1..]).current_dir(&self.work_dir).output().map_err(|e| e.to_string())?;
        Ok(format!("{}{}", String::from_utf8_lossy(&output.stdout), String::from_utf8_lossy(&output.stderr)))
    }

    pub fn run_command(&self, command: &str) -> Result<String, String> {
        let parts: Vec<&str> = command.split_whitespace().collect();
        if parts.is_empty() { return Err("empty command".to_string()); }
        let allowed = ["cargo", "cat", "ls", "grep", "find", "head", "tail", "wc"];
        if !allowed.contains(&parts[0]) { return Err("command not allowed".to_string()); }
        self.execute_command(command)
    }

    fn tests_for_file(&self, rel: &str) -> Vec<&'static str> {
        if rel.starts_with("src/") || rel.starts_with("migrations/") { return vec!["platform_tests"]; }
        if rel.starts_with("services/") || rel.starts_with("shared/") { return vec!["services_contracts"]; }
        Vec::new()
    }

    fn run_full_tests(&self) -> TestSummary {
        let output = self.execute_command("cargo test").unwrap_or_default();
        parse_cargo_test_summary(&output, false)
    }

    fn run_targeted_tests(&self, rel: &str) -> TestSummary {
        let targets = self.tests_for_file(rel);
        if targets.is_empty() { return TestSummary::default(); }
        let mut command = String::from("cargo test");
        for target in targets { command.push_str(" --test "); command.push_str(target); }
        let output = self.execute_command(&command).unwrap_or_default();
        parse_cargo_test_summary(&output, true)
    }

    pub fn reset(&mut self) -> StepResult {
        self.step_count = 0;
        self.mutating_steps = 0;
        self.files_changed.clear();
        self.last_test_summary = self.run_full_tests();
        let summary = self.last_test_summary.clone();

        let mut observation = HashMap::new();
        observation.insert("action_result".to_string(), String::new());
        observation.insert("step".to_string(), "0".to_string());
        observation.insert("reward".to_string(), "0.000000".to_string());
        observation.insert("tests_total".to_string(), summary.total.to_string());
        observation.insert("tests_passed".to_string(), summary.passed.to_string());
        observation.insert("tests_failed".to_string(), summary.failed.to_string());
        observation.insert("pass_rate".to_string(), format!("{:.4}", summary.pass_rate));
        observation.insert("targeted_run".to_string(), summary.targeted.to_string());

        let mut info = HashMap::new();
        info.insert("step".to_string(), "0".to_string());
        info.insert("max_steps".to_string(), self.max_steps.to_string());
        info.insert("total_bugs".to_string(), "128".to_string());
        info.insert("target_tests".to_string(), "1220".to_string());
        info.insert("files_changed".to_string(), String::new());
        info.insert("tests_total".to_string(), summary.total.to_string());
        info.insert("tests_failed".to_string(), summary.failed.to_string());
        info.insert("pass_rate".to_string(), format!("{:.4}", summary.pass_rate));
        info.insert("targeted_run".to_string(), summary.targeted.to_string());
        info.insert("test_output_chars".to_string(), summary.output.len().to_string());

        StepResult { observation, reward: 0.0, done: false, info }
    }

    pub fn step(&mut self, action: &HashMap<String, String>) -> StepResult {
        self.step_count += 1;
        if let Err(err) = self.validate_action(action) {
            let mut observation = HashMap::new();
            observation.insert("action_result".to_string(), String::new());
            observation.insert("step".to_string(), self.step_count.to_string());
            let mut info = HashMap::new();
            info.insert("error".to_string(), err);
            info.insert("step".to_string(), self.step_count.to_string());
            return StepResult { observation, reward: 0.0, done: self.step_count >= self.max_steps, info };
        }

        let action_type = action.get("type").map(String::as_str).unwrap_or("");
        let mut info = HashMap::new();

        let action_result = match action_type {
            "edit" => self.edit(action.get("file").map(String::as_str).unwrap_or(""), action.get("content").map(String::as_str).unwrap_or("")),
            "read" => self.read(action.get("file").map(String::as_str).unwrap_or("")),
            "run_command" => self.run_command(action.get("command").map(String::as_str).unwrap_or("")),
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
            if targeted.total > 0 && self.mutating_steps % self.full_run_interval != 0 && targeted.pass_rate < 1.0 { summary = targeted; } else { summary = self.run_full_tests(); }
        }

        let reward = sparse_reward(summary.pass_rate);
        self.last_test_summary = summary.clone();
        let done = self.step_count >= self.max_steps || (!summary.targeted && summary.total > 0 && summary.pass_rate >= 1.0);

        let mut observation = HashMap::new();
        match action_result {
            Ok(output) => { observation.insert("action_result".to_string(), output); }
            Err(err) => { observation.insert("action_result".to_string(), String::new()); info.insert("error".to_string(), err); }
        }

        observation.insert("step".to_string(), self.step_count.to_string());
        observation.insert("reward".to_string(), format!("{reward:.6}"));
        observation.insert("tests_total".to_string(), summary.total.to_string());
        observation.insert("tests_passed".to_string(), summary.passed.to_string());
        observation.insert("tests_failed".to_string(), summary.failed.to_string());
        observation.insert("pass_rate".to_string(), format!("{:.4}", summary.pass_rate));
        observation.insert("targeted_run".to_string(), summary.targeted.to_string());

        info.insert("step".to_string(), self.step_count.to_string());
        info.insert("max_steps".to_string(), self.max_steps.to_string());
        info.insert("total_bugs".to_string(), "128".to_string());
        info.insert("target_tests".to_string(), "1220".to_string());
        info.insert("files_changed".to_string(), self.files_changed.join(","));
        info.insert("tests_total".to_string(), summary.total.to_string());
        info.insert("tests_failed".to_string(), summary.failed.to_string());
        info.insert("pass_rate".to_string(), format!("{:.4}", summary.pass_rate));
        info.insert("targeted_run".to_string(), summary.targeted.to_string());
        info.insert("test_output_chars".to_string(), summary.output.len().to_string());

        StepResult { observation, reward, done, info }
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
            if trimmed.ends_with(" ... ok") { passed += 1; } else if trimmed.ends_with(" ... FAILED") { failed += 1; }
        }
    }
    let total = passed + failed;
    let pass_rate = if total > 0 { passed as f64 / total as f64 } else { 0.0 };
    TestSummary { total, passed, failed, pass_rate, targeted, output: output.to_string() }
}

fn extract_count(line: &str, marker: &str) -> usize {
    if let Some(idx) = line.find(marker) {
        return line[..idx].split_whitespace().last().unwrap_or("0").parse::<usize>().unwrap_or(0);
    }
    0
}

fn sparse_reward(pass_rate: f64) -> f64 {
    const THRESHOLDS: [f64; 7] = [0.25, 0.40, 0.55, 0.70, 0.85, 0.95, 1.0];
    const REWARDS: [f64; 7] = [0.05, 0.12, 0.22, 0.38, 0.55, 0.78, 1.0];
    for i in (0..THRESHOLDS.len()).rev() { if pass_rate >= THRESHOLDS[i] { return REWARDS[i]; } }
    0.0
}
