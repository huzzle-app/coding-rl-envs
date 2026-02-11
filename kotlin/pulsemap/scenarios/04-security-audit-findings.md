# Security Audit Report: PulseMap API Assessment

## Executive Summary

**Audit Period**: February 12-16, 2024
**Auditor**: CyberShield Security Consulting
**Scope**: PulseMap API v2.4.1 (Kotlin/Ktor backend)
**Classification**: CONFIDENTIAL

---

## Critical Findings

### FINDING-001: SQL Injection in Sensor Search

**Severity**: CRITICAL
**CVSS Score**: 9.8
**CWE**: CWE-89 (SQL Injection)

**Description**:
The sensor search functionality in `SensorRepository` constructs SQL queries using Kotlin string templates rather than parameterized queries. This allows attackers to inject arbitrary SQL commands.

**Proof of Concept**:
```http
GET /api/v1/sensors?name=test'%20OR%201=1;%20DROP%20TABLE%20sensors;-- HTTP/1.1
Authorization: Bearer <token>
Host: api.pulsemap.io
```

**Server Log Evidence**:
```
2024-02-14T15:23:45.123Z ERROR Database query failed
org.postgresql.util.PSQLException: ERROR: syntax error at or near "OR"
  Position: 47
Query: SELECT * FROM sensors WHERE name = 'test' OR 1=1; DROP TABLE sensors;--'
```

**Impact**: Full database compromise, data exfiltration, data destruction

**Affected Code Pattern**:
```kotlin
// Vulnerable pattern found in repository
fun findByName(name: String): List<Sensor> {
    val query = "SELECT * FROM sensors WHERE name = '$name'"
    return exec(query)  // Direct string interpolation!
}
```

**Recommendation**: Use Exposed DSL or parameterized queries:
```kotlin
SensorsTable.select { SensorsTable.name eq name }
```

---

### FINDING-002: Path Traversal in Tile Serving

**Severity**: HIGH
**CVSS Score**: 8.6
**CWE**: CWE-22 (Path Traversal)

**Description**:
The static tile file serving endpoint does not validate path components, allowing attackers to read arbitrary files from the server filesystem.

**Proof of Concept**:
```http
GET /api/v1/tiles/static/../../../../../../etc/passwd HTTP/1.1
Authorization: Bearer <token>
Host: api.pulsemap.io

Response:
root:x:0:0:root:/root:/bin/bash
daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin
...
```

**Additional Attack Vectors**:
```
GET /tiles/static/..%2f..%2f..%2fetc/passwd
GET /tiles/static/....//....//....//etc/passwd
GET /tiles/static/%252e%252e%252f%252e%252e%252fetc/passwd
```

**Impact**:
- Read sensitive configuration files (`application.conf`, `.env`)
- Access database credentials
- Read other users' cached tile data
- Potential RCE via reading SSH keys

**Recommendation**: Validate that resolved canonical path stays within the intended `tiles/` directory.

---

### FINDING-003: Authorization Bypass in Interceptor

**Severity**: HIGH
**CVSS Score**: 8.1
**CWE**: CWE-862 (Missing Authorization)

**Description**:
The authentication interceptor in `AuthPlugin.kt` responds with `401 Unauthorized` but does not terminate the request pipeline. The route handler continues executing with the unauthorized request.

**Proof of Concept**:
```http
GET /api/v1/sensors/private HTTP/1.1
Host: api.pulsemap.io
# No Authorization header

Response:
HTTP/1.1 401 Unauthorized
Content-Type: application/json
# ...but also returns the private sensor data in body
```

**Code Pattern**:
```kotlin
intercept(ApplicationCallPipeline.Plugins) {
    if (!isAuthorized(call)) {
        call.respond(HttpStatusCode.Unauthorized, "Not authorized")
        // Missing: return@intercept
    }
    // Pipeline continues even after responding 401!
}
```

**Impact**: Complete bypass of authentication for all protected endpoints

---

## Medium Findings

### FINDING-004: Unsafe JSON Deserialization

**Severity**: MEDIUM
**CVSS Score**: 6.5
**CWE**: CWE-502 (Deserialization of Untrusted Data)

**Description**:
The ingestion routes manually deserialize JSON using `Json.decodeFromString` instead of using Ktor's content negotiation. This bypasses error handling and can leak internal error messages.

**Evidence**:
```http
POST /api/v1/ingest HTTP/1.1
Content-Type: application/json

{"readings": "not-an-array"}

Response:
HTTP/1.1 500 Internal Server Error
{
  "error": "kotlinx.serialization.json.internal.JsonDecodingException: Expected JsonArray at path $.readings"
}
```

**Impact**: Information disclosure via detailed error messages, inconsistent error handling

---

### FINDING-005: Unsafe Type Cast in Request Handling

**Severity**: MEDIUM
**CVSS Score**: 5.3
**CWE**: CWE-704 (Incorrect Type Conversion)

**Description**:
The batch ingestion endpoint uses unsafe `as` cast on JSON elements, causing `ClassCastException` when clients send malformed data.

**Proof of Concept**:
```http
POST /api/v1/ingest/batch HTTP/1.1
Content-Type: application/json

{"data": "string-instead-of-array"}

Response:
HTTP/1.1 500 Internal Server Error
java.lang.ClassCastException: class kotlinx.serialization.json.JsonPrimitive cannot be cast to class kotlinx.serialization.json.JsonArray
```

**Recommendation**: Use `as?` safe cast with proper null handling.

---

### FINDING-006: Missing Sealed Class Handler

**Severity**: MEDIUM
**CVSS Score**: 4.7
**CWE**: CWE-754 (Improper Check for Unusual Conditions)

**Description**:
The geometry area calculation uses a `when` expression on a sealed class but falls through to an `else` branch that throws an exception. When `MultiPolygon` geometry is submitted, the service crashes.

**Proof of Concept**:
```http
POST /api/v1/geometry/area HTTP/1.1
Content-Type: application/json

{
  "type": "MultiPolygon",
  "coordinates": [[[...]]]
}

Response:
HTTP/1.1 500 Internal Server Error
java.lang.IllegalArgumentException: Unknown geometry type: MultiPolygon
```

**Impact**: Denial of service for valid geometry types

---

### FINDING-007: Missing Polymorphic Serializer Registration

**Severity**: LOW
**CVSS Score**: 3.7
**CWE**: CWE-502 (Deserialization Issues)

**Description**:
The `RadiusFilter` subclass of the sealed `QueryFilter` interface is not registered in the polymorphic serializer module. Queries using radius filters fail silently or crash.

**Evidence**:
```
kotlinx.serialization.SerializationException: Polymorphic serializer was not found for class discriminator 'RadiusFilter'
```

---

## Low Findings

### FINDING-008: Null Safety Bypass via Platform Types

**Severity**: LOW
**Description**: The `GeometryService` calls a private method that returns nullable `Pair<Double, Double>?` but the caller dereferences without null check, causing NPE on invalid WKT strings.

### FINDING-009: TOCTOU Race in Tile Cache

**Severity**: LOW
**Description**: The tile cache uses `containsKey` followed by `get` with `!!`, creating a race condition where entries can be evicted between checks under concurrent access.

---

## Recommendations Summary

| Priority | Action | Finding |
|----------|--------|---------|
| P0 | Use parameterized queries for all database access | FINDING-001 |
| P0 | Validate file paths against canonical base directory | FINDING-002 |
| P0 | Add `return@intercept` after unauthorized response | FINDING-003 |
| P1 | Use Ktor content negotiation instead of manual JSON parsing | FINDING-004 |
| P1 | Replace unsafe `as` casts with `as?` safe casts | FINDING-005 |
| P1 | Handle all sealed class branches explicitly | FINDING-006 |
| P2 | Register all polymorphic serializer subclasses | FINDING-007 |
| P2 | Add null checks for platform type returns | FINDING-008 |
| P2 | Use atomic get-or-create pattern for cache access | FINDING-009 |

---

## Files to Review

Based on findings:
- `src/main/kotlin/com/pulsemap/repository/SensorRepository.kt` - SQL injection
- `src/main/kotlin/com/pulsemap/routes/TileRoutes.kt` - Path traversal
- `src/main/kotlin/com/pulsemap/plugins/AuthPlugin.kt` - Authorization bypass
- `src/main/kotlin/com/pulsemap/routes/IngestionRoutes.kt` - Unsafe cast, manual JSON
- `src/main/kotlin/com/pulsemap/model/GeometryType.kt` - Missing sealed branch
- `src/main/kotlin/com/pulsemap/config/SerializationConfig.kt` - Missing polymorphic registration
- `src/main/kotlin/com/pulsemap/service/GeometryService.kt` - Null safety
- `src/main/kotlin/com/pulsemap/service/TileService.kt` - TOCTOU race

---

**Report Prepared By**: Dr. Elena Rodriguez, Principal Security Researcher
**Reviewed By**: James Chen, CISO
**Date**: February 17, 2024
**Remediation Deadline**: March 1, 2024
