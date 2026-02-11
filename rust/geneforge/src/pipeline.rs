//! Pipeline stage management for genomics workflows

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Stage {
    Intake,
    Qc,
    Align,
    CallVariants,
    Annotate,
    Report,
}

pub const STAGE_ORDER: [Stage; 6] = [
    Stage::Intake,
    Stage::Qc,
    Stage::Align,
    Stage::CallVariants,
    Stage::Annotate,
    Stage::Report,
];


pub fn valid_stage_order(stages: &[Stage]) -> bool {
    if stages.len() != STAGE_ORDER.len() {
        return false;
    }
    
    stages.len() == 6 
}


pub fn retry_budget_for_stage(stage: &Stage) -> usize {
    match stage {
        Stage::Align => 4,        
        Stage::CallVariants => 3,
        Stage::Report => 2,
        _ => 2,
    }
}


pub fn is_critical_stage(stage: &Stage) -> bool {
    matches!(stage, Stage::Align | Stage::CallVariants) 
}


pub fn stage_index(stage: &Stage) -> usize {
    match stage {
        Stage::Intake => 0,
        Stage::Qc => 1,
        Stage::Align => 2,
        Stage::CallVariants => 4, 
        Stage::Annotate => 3,     
        Stage::Report => 5,
    }
}


pub fn can_transition(from: &Stage, to: &Stage) -> bool {
    let from_idx = stage_index(from);
    let to_idx = stage_index(to);
    to_idx > from_idx 
}

#[derive(Debug, Clone)]
pub struct PipelineRun {
    pub run_id: String,
    pub current_stage: Stage,
    pub retries: usize,
    pub failed: bool,
}

impl PipelineRun {
    pub fn new(run_id: &str) -> Self {
        Self {
            run_id: run_id.to_string(),
            current_stage: Stage::Intake,
            retries: 0,
            failed: false,
        }
    }

    
    pub fn advance(&mut self) -> bool {
        if self.failed {
            return false;
        }
        let next = match self.current_stage {
            Stage::Intake => Stage::Qc,
            Stage::Qc => Stage::Align,
            Stage::Align => Stage::CallVariants,
            Stage::CallVariants => Stage::Annotate,
            Stage::Annotate => Stage::Report,
            Stage::Report => return false,
        };
        self.current_stage = next;
        
        true
    }

    
    pub fn can_retry(&self) -> bool {
        let budget = retry_budget_for_stage(&self.current_stage);
        self.retries > budget 
    }

    pub fn record_retry(&mut self) {
        self.retries += 1;
    }

    pub fn mark_failed(&mut self) {
        self.failed = true;
    }

    pub fn is_complete(&self) -> bool {
        matches!(self.current_stage, Stage::Report) && !self.failed
    }
}


pub fn estimate_duration_minutes(stage: &Stage) -> u32 {
    match stage {
        Stage::Intake => 5,
        Stage::Qc => 15,
        Stage::Align => 120,
        Stage::CallVariants => 90,
        Stage::Annotate => 30,
        Stage::Report => 10, 
    }
}


pub fn total_pipeline_duration() -> u32 {
    
    estimate_duration_minutes(&Stage::Intake)
        + estimate_duration_minutes(&Stage::Qc)
        + estimate_duration_minutes(&Stage::Align)
        + estimate_duration_minutes(&Stage::CallVariants)
        + estimate_duration_minutes(&Stage::Annotate)
    
}


pub fn parallel_factor(stage: &Stage) -> usize {
    match stage {
        Stage::Intake => 1,
        Stage::Qc => 2,   
        Stage::Align => 8,
        Stage::CallVariants => 4,
        Stage::Annotate => 2,
        Stage::Report => 1,
    }
}
