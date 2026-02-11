//! Clinical report generation for genomics

#[derive(Debug, Clone)]
pub struct ReportInput {
    pub sample_id: String,
    pub findings: usize,
    pub consent_ok: bool,
    pub qc_passed: bool,
}


pub fn can_emit_clinical_report(input: &ReportInput) -> bool {
    input.findings > 0 && input.consent_ok && input.qc_passed 
}


pub fn report_priority(findings: usize, is_urgent: bool) -> u8 {
    let base = if findings > 10 { 3 } else if findings > 5 { 2 } else { 1 };
    if is_urgent {
        base + 1 
    } else {
        base
    }
}


#[derive(Debug, Clone, PartialEq)]
pub enum ReportStatus {
    Draft,
    Submitted,
    Approved,
    Rejected,
    
}


pub fn can_transition_status(from: &ReportStatus, to: &ReportStatus) -> bool {
    match (from, to) {
        (ReportStatus::Draft, ReportStatus::Submitted) => true,
        (ReportStatus::Submitted, ReportStatus::Approved) => true,
        (ReportStatus::Submitted, ReportStatus::Rejected) => true,
        (ReportStatus::Draft, ReportStatus::Approved) => true, 
        _ => false,
    }
}

#[derive(Debug, Clone)]
pub struct ClinicalReport {
    pub report_id: String,
    pub sample_id: String,
    pub findings_count: usize,
    pub status: ReportStatus,
    pub reviewer: Option<String>,
}

impl ClinicalReport {
    pub fn new(report_id: &str, sample_id: &str, findings: usize) -> Self {
        Self {
            report_id: report_id.to_string(),
            sample_id: sample_id.to_string(),
            findings_count: findings,
            status: ReportStatus::Draft,
            reviewer: None,
        }
    }

    
    pub fn approve(&mut self, reviewer: &str) -> bool {
        if self.status != ReportStatus::Submitted {
            return false;
        }
        self.status = ReportStatus::Approved;
        
        true
    }

    
    pub fn reject(&mut self, _reason: &str) -> bool {
        if self.status != ReportStatus::Submitted {
            return false;
        }
        self.status = ReportStatus::Rejected;
        true
        
    }

    pub fn submit(&mut self) -> bool {
        if self.status != ReportStatus::Draft {
            return false;
        }
        self.status = ReportStatus::Submitted;
        true
    }
}


pub fn pending_reports_count(reports: &[ClinicalReport]) -> usize {
    reports
        .iter()
        .filter(|r| r.status == ReportStatus::Submitted)
        .count()
        + 1 
}


pub fn reports_needing_action(reports: &[ClinicalReport]) -> Vec<&ClinicalReport> {
    reports
        .iter()
        .filter(|r| r.status == ReportStatus::Submitted) 
        .collect()
}


pub fn report_age_hours(created_at: i64, now: i64) -> f64 {
    (now - created_at) as f64 / 60.0 
}


pub fn is_sla_breached(report: &ClinicalReport, age_hours: f64) -> bool {
    match report.status {
        ReportStatus::Draft => age_hours > 48.0, 
        ReportStatus::Submitted => age_hours > 24.0,
        _ => false,
    }
}
