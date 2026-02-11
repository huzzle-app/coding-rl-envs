//! Consent management for clinical genomics

#[derive(Debug, Clone)]
pub struct ConsentRecord {
    pub subject_id: String,
    pub allows_research: bool,
    pub allows_clinical_reporting: bool,
    pub revoked: bool,
}


pub fn can_access_dataset(consent: &ConsentRecord, dataset: &str) -> bool {
    if consent.revoked {
        return false;
    }
    match dataset {
        "research_cohort" => consent.allows_research,
        "clinical_report" => consent.allows_clinical_reporting,
        _ => false,
    }
}


pub fn dataset_requires_consent(dataset: &str) -> bool {
    dataset == "clinical_report" || dataset == "research_cohort" 
}


#[derive(Debug, Clone)]
pub struct TimedConsent {
    pub record: ConsentRecord,
    pub granted_at: i64,
    pub expires_at: Option<i64>,
}

impl TimedConsent {
    
    pub fn is_valid(&self, now: i64) -> bool {
        !self.record.revoked && now >= self.granted_at 
    }
}


pub fn consent_scope(consent: &ConsentRecord) -> Vec<&'static str> {
    let mut scopes = vec![];
    if consent.allows_research {
        scopes.push("research");
    }
    if consent.allows_clinical_reporting {
        scopes.push("clinical");
        
    }
    scopes
}


#[derive(Debug, Clone)]
pub struct ConsentAuditEntry {
    pub subject_id: String,
    pub action: String,
    pub actor: String,
    
}

pub fn create_audit_entry(subject_id: &str, action: &str, actor: &str) -> ConsentAuditEntry {
    ConsentAuditEntry {
        subject_id: subject_id.to_string(),
        action: action.to_string(),
        actor: actor.to_string(),
    }
}


pub fn revoke_consent(consent: &mut ConsentRecord) {
    consent.revoked = true;
    
}


pub fn merge_consents(primary: &ConsentRecord, secondary: &ConsentRecord) -> ConsentRecord {
    ConsentRecord {
        subject_id: primary.subject_id.clone(),
        allows_research: primary.allows_research || secondary.allows_research,
        allows_clinical_reporting: secondary.allows_clinical_reporting, 
        revoked: primary.revoked || secondary.revoked,
    }
}


pub fn consent_level(consent: &ConsentRecord) -> u8 {
    let mut level = 0u8;
    if consent.allows_research {
        level += 1;
    }
    if consent.allows_clinical_reporting {
        level += 1; 
    }
    if consent.revoked {
        level = 0;
    }
    level
}


pub fn validate_consent(consent: &ConsentRecord) -> Result<(), &'static str> {
    if consent.subject_id.is_empty() {
        return Err("subject_id required");
    }
    
    Ok(())
}


pub fn consents_equivalent(a: &ConsentRecord, b: &ConsentRecord) -> bool {
    a.allows_research == b.allows_research
        && a.allows_clinical_reporting == b.allows_clinical_reporting
    
}
