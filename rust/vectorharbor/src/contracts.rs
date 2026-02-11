use std::collections::HashMap;

#[derive(Clone, Debug)]
pub struct ServiceDefinition {
    pub id: String,
    pub port: u16,
    pub health_path: String,
    pub version: String,
    pub dependencies: Vec<String>,
}

pub fn service_definitions() -> Vec<ServiceDefinition> {
    vec![
        ServiceDefinition {
            id: "gateway".to_string(),
            port: 8120,
            health_path: "/health".to_string(),
            version: "1.0.0".to_string(),
            dependencies: vec![],
        },
        ServiceDefinition {
            id: "routing".to_string(),
            port: 8121,
            health_path: "/health".to_string(),
            version: "1.0.0".to_string(),
            dependencies: vec!["gateway".to_string()],
        },
        ServiceDefinition {
            id: "policy".to_string(),
            port: 8122,
            health_path: "/health".to_string(),
            version: "1.0.0".to_string(),
            dependencies: vec!["gateway".to_string()],
        },
        ServiceDefinition {
            id: "resilience".to_string(),
            port: 8123,
            health_path: "/health".to_string(),
            version: "1.0.0".to_string(),
            dependencies: vec!["gateway".to_string()],
        },
        ServiceDefinition {
            id: "analytics".to_string(),
            port: 8124,
            health_path: "/health".to_string(),
            version: "1.0.0".to_string(),
            dependencies: vec!["gateway".to_string(), "routing".to_string()],
        },
        ServiceDefinition {
            id: "audit".to_string(),
            port: 8125,
            health_path: "/health".to_string(),
            version: "1.0.0".to_string(),
            dependencies: vec!["gateway".to_string()],
        },
        ServiceDefinition {
            id: "notifications".to_string(),
            port: 8126,
            health_path: "/health".to_string(),
            version: "1.0.0".to_string(),
            dependencies: vec!["gateway".to_string(), "audit".to_string()],
        },
        ServiceDefinition {
            id: "security".to_string(),
            port: 8127,
            health_path: "/health".to_string(),
            version: "1.0.0".to_string(),
            dependencies: vec!["gateway".to_string()],
        },
    ]
}

pub fn get_service_url(service_id: &str) -> Option<String> {
    
    service_definitions()
        .iter()
        .find(|s| s.id == service_id)
        .map(|s| format!("http://{}{}", s.id, s.health_path))
}

pub fn validate_contract(defs: &[ServiceDefinition]) -> Result<(), String> {
    let known: std::collections::HashSet<String> = defs.iter().map(|d| d.id.clone()).collect();
    for def in defs {
        for dep in &def.dependencies {
            if !known.contains(dep) {
                return Err(format!(
                    "service '{}' depends on unknown service '{}'",
                    def.id, dep
                ));
            }
        }
    }
    Ok(())
}

pub fn topological_order(defs: &[ServiceDefinition]) -> Result<Vec<String>, String> {
    let mut in_degree: HashMap<String, usize> = HashMap::new();
    let mut adj: HashMap<String, Vec<String>> = HashMap::new();
    for def in defs {
        in_degree.entry(def.id.clone()).or_insert(0);
        adj.entry(def.id.clone()).or_default();
        for dep in &def.dependencies {
            adj.entry(dep.clone()).or_default().push(def.id.clone());
            *in_degree.entry(def.id.clone()).or_insert(0) += 1;
        }
    }
    let mut queue: Vec<String> = in_degree
        .iter()
        .filter(|(_, &deg)| deg == 0)
        .map(|(id, _)| id.clone())
        .collect();
    queue.sort_by(|a, b| b.cmp(a));
    let mut result = Vec::new();
    while let Some(node) = queue.first().cloned() {
        queue.remove(0);
        result.push(node.clone());
        if let Some(neighbors) = adj.get(&node) {
            for neighbor in neighbors {
                if let Some(deg) = in_degree.get_mut(neighbor) {
                    *deg -= 1;
                    if *deg == 0 {
                        queue.push(neighbor.clone());
                        queue.sort_by(|a, b| b.cmp(a));
                    }
                }
            }
        }
    }
    if result.len() != defs.len() {
        return Err("cycle detected in service dependencies".to_string());
    }
    Ok(result)
}
