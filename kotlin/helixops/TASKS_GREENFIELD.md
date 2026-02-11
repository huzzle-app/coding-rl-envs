# HelixOps - Greenfield Implementation Tasks

This document defines greenfield implementation tasks for the HelixOps enterprise operations platform. Each task requires implementing a new module from scratch while following existing architectural patterns.

**Test Command:** `./gradlew test`

---

## Task 1: SSO Integration Service

### Overview

Implement a Single Sign-On (SSO) integration service that enables federated authentication with external identity providers (SAML 2.0, OIDC). The service must coordinate with the existing `auth` module for token issuance and session management.

### Module Location

```
sso/
  src/main/kotlin/com/mindvault/sso/
    SsoService.kt           # Main service implementation
    domain.kt               # Data classes and sealed types
    handlers.kt             # Ktor route handlers
    repository.kt           # Identity provider configuration storage
    service.kt              # Business logic
  src/test/kotlin/com/mindvault/sso/
    SsoTests.kt             # Unit and integration tests
```

### Interface Contract

```kotlin
package com.helixops.sso

import kotlinx.coroutines.flow.Flow
import java.time.Instant

/**
 * SSO Integration Service for federated authentication.
 *
 * Handles SAML 2.0 and OIDC protocol flows, identity provider discovery,
 * and session binding with the internal auth system.
 */
interface SsoService {

    /**
     * Initiates an SSO authentication flow for the given identity provider.
     *
     * @param providerId The registered identity provider ID
     * @param relayState Optional state to preserve across the redirect
     * @return AuthnRequest containing the redirect URL and request ID
     * @throws ProviderNotFoundException if the provider is not registered
     * @throws ProviderDisabledException if the provider is disabled
     */
    suspend fun initiateAuthnRequest(
        providerId: String,
        relayState: String? = null
    ): AuthnRequest

    /**
     * Processes an SSO response from an identity provider.
     *
     * Validates the assertion, extracts claims, and creates or links
     * the internal user account.
     *
     * @param providerId The identity provider that issued the response
     * @param samlResponse Base64-encoded SAML response (for SAML providers)
     * @param code Authorization code (for OIDC providers)
     * @param state State parameter for CSRF validation
     * @return SsoAuthResult containing the authenticated user and session
     * @throws InvalidAssertionException if the assertion signature is invalid
     * @throws AssertionExpiredException if the assertion has expired
     * @throws UserProvisioningException if user creation/linking fails
     */
    suspend fun processAuthnResponse(
        providerId: String,
        samlResponse: String? = null,
        code: String? = null,
        state: String? = null
    ): SsoAuthResult

    /**
     * Registers a new identity provider configuration.
     *
     * @param config The identity provider configuration
     * @return The registered provider with generated ID
     * @throws DuplicateProviderException if entityId/issuer already exists
     * @throws InvalidMetadataException if SAML metadata or OIDC discovery fails
     */
    suspend fun registerProvider(config: IdentityProviderConfig): IdentityProvider

    /**
     * Updates an existing identity provider configuration.
     *
     * @param providerId The provider ID to update
     * @param config The updated configuration fields
     * @return The updated provider
     * @throws ProviderNotFoundException if the provider does not exist
     */
    suspend fun updateProvider(
        providerId: String,
        config: IdentityProviderConfigUpdate
    ): IdentityProvider

    /**
     * Lists all registered identity providers with optional filtering.
     *
     * @param protocol Filter by protocol type (SAML, OIDC, or null for all)
     * @param enabled Filter by enabled status (or null for all)
     * @return List of matching identity providers
     */
    suspend fun listProviders(
        protocol: SsoProtocol? = null,
        enabled: Boolean? = null
    ): List<IdentityProvider>

    /**
     * Fetches and caches the identity provider's metadata.
     *
     * For SAML: fetches from metadata URL and extracts certificates
     * For OIDC: fetches from .well-known/openid-configuration
     *
     * @param providerId The provider to refresh
     * @return Updated metadata with refresh timestamp
     * @throws MetadataFetchException if the metadata URL is unreachable
     */
    suspend fun refreshProviderMetadata(providerId: String): ProviderMetadata

    /**
     * Initiates Single Logout (SLO) for the current session.
     *
     * @param sessionId The internal session ID to terminate
     * @param propagate Whether to send logout requests to the IdP
     * @return SloResult indicating success and any propagation failures
     */
    suspend fun initiateSingleLogout(
        sessionId: String,
        propagate: Boolean = true
    ): SloResult

    /**
     * Processes an incoming SLO request from an identity provider.
     *
     * @param providerId The identity provider initiating logout
     * @param logoutRequest The SAML LogoutRequest or OIDC logout token
     * @return SloResponse to send back to the IdP
     */
    suspend fun processSloRequest(
        providerId: String,
        logoutRequest: String
    ): SloResponse

    /**
     * Streams real-time SSO events for monitoring and audit.
     *
     * @param eventTypes Filter by event types (or empty for all)
     * @return Flow of SSO events
     */
    fun streamSsoEvents(eventTypes: Set<SsoEventType> = emptySet()): Flow<SsoEvent>

    /**
     * Validates an SSO session is still active with the IdP.
     *
     * @param sessionId The internal session to validate
     * @return SessionValidationResult with active status and remaining TTL
     */
    suspend fun validateSession(sessionId: String): SessionValidationResult
}
```

### Required Data Classes

```kotlin
package com.helixops.sso

import kotlinx.serialization.Serializable
import java.time.Instant

enum class SsoProtocol { SAML_2_0, OIDC }

enum class SsoEventType {
    AUTHN_REQUEST_INITIATED,
    AUTHN_RESPONSE_RECEIVED,
    AUTHN_SUCCESS,
    AUTHN_FAILURE,
    SLO_INITIATED,
    SLO_COMPLETED,
    PROVIDER_REGISTERED,
    PROVIDER_UPDATED,
    METADATA_REFRESHED
}

@Serializable
data class AuthnRequest(
    val requestId: String,
    val redirectUrl: String,
    val providerId: String,
    val relayState: String?,
    val createdAt: Long,
    val expiresAt: Long
)

@Serializable
data class SsoAuthResult(
    val userId: String,
    val sessionId: String,
    val providerId: String,
    val externalSubject: String,
    val claims: Map<String, String>,
    val sessionExpiresAt: Long,
    val isNewUser: Boolean
)

@Serializable
data class IdentityProviderConfig(
    val name: String,
    val protocol: SsoProtocol,
    val entityId: String,              // SAML Entity ID or OIDC Issuer
    val metadataUrl: String?,          // SAML metadata URL
    val ssoUrl: String?,               // Manual SSO endpoint (if no metadata)
    val sloUrl: String?,               // Manual SLO endpoint
    val clientId: String?,             // OIDC client ID
    val clientSecret: String?,         // OIDC client secret
    val scopes: Set<String> = setOf("openid", "profile", "email"),
    val attributeMappings: Map<String, String> = emptyMap(),
    val enabled: Boolean = true,
    val allowIdpInitiated: Boolean = false,
    val forceAuthn: Boolean = false
)

@Serializable
data class IdentityProviderConfigUpdate(
    val name: String? = null,
    val metadataUrl: String? = null,
    val ssoUrl: String? = null,
    val sloUrl: String? = null,
    val clientSecret: String? = null,
    val scopes: Set<String>? = null,
    val attributeMappings: Map<String, String>? = null,
    val enabled: Boolean? = null,
    val allowIdpInitiated: Boolean? = null,
    val forceAuthn: Boolean? = null
)

@Serializable
data class IdentityProvider(
    val id: String,
    val name: String,
    val protocol: SsoProtocol,
    val entityId: String,
    val ssoUrl: String,
    val sloUrl: String?,
    val certificates: List<String>,    // PEM-encoded X.509 certs
    val enabled: Boolean,
    val createdAt: Long,
    val updatedAt: Long,
    val lastMetadataRefresh: Long?
)

@Serializable
data class ProviderMetadata(
    val providerId: String,
    val ssoUrl: String,
    val sloUrl: String?,
    val certificates: List<String>,
    val supportedNameIdFormats: List<String>,
    val refreshedAt: Long,
    val expiresAt: Long
)

@Serializable
data class SloResult(
    val success: Boolean,
    val terminatedSessions: Int,
    val propagationFailures: List<PropagationFailure>
)

@Serializable
data class PropagationFailure(
    val providerId: String,
    val error: String,
    val timestamp: Long
)

@Serializable
data class SloResponse(
    val responseId: String,
    val inResponseTo: String,
    val status: String,
    val destination: String
)

@Serializable
data class SsoEvent(
    val eventId: String,
    val eventType: SsoEventType,
    val providerId: String?,
    val userId: String?,
    val sessionId: String?,
    val timestamp: Long,
    val metadata: Map<String, String>
)

@Serializable
data class SessionValidationResult(
    val isActive: Boolean,
    val sessionId: String,
    val remainingTtlSeconds: Long?,
    val lastValidatedAt: Long
)

sealed class SsoException(message: String) : Exception(message)
class ProviderNotFoundException(providerId: String) : SsoException("Provider not found: $providerId")
class ProviderDisabledException(providerId: String) : SsoException("Provider disabled: $providerId")
class DuplicateProviderException(entityId: String) : SsoException("Provider already exists: $entityId")
class InvalidMetadataException(reason: String) : SsoException("Invalid metadata: $reason")
class InvalidAssertionException(reason: String) : SsoException("Invalid assertion: $reason")
class AssertionExpiredException(assertionId: String) : SsoException("Assertion expired: $assertionId")
class UserProvisioningException(reason: String) : SsoException("User provisioning failed: $reason")
class MetadataFetchException(url: String, cause: Throwable?) : SsoException("Failed to fetch metadata: $url")
```

### Architectural Requirements

1. **Follow existing patterns from `auth` module:**
   - Use `ConcurrentHashMap` for in-memory caches with TTL
   - Use Kotlin coroutines with `Mutex` for thread-safe operations
   - Implement Ktor route handlers in separate `handlers.kt`
   - Use `kotlinx.serialization` for data classes

2. **Integration points:**
   - Call `AuthService.issueToken()` after successful SSO authentication
   - Use `shared/security/JwtProvider` for token signing
   - Publish events via `shared/events/EventBus`
   - Use `shared/cache/CacheManager` for metadata caching

3. **Security requirements:**
   - Validate SAML assertion signatures using provider certificates
   - Implement CSRF protection via state parameter for OIDC
   - Enforce assertion time validity (NotBefore, NotOnOrAfter)
   - Store client secrets encrypted (reference `AuthRepository` patterns)

### Acceptance Criteria

- [ ] All interface methods implemented with proper error handling
- [ ] Minimum 30 unit tests covering:
  - SAML AuthnRequest generation and response parsing
  - OIDC authorization code flow
  - Provider CRUD operations
  - Metadata refresh and caching
  - SLO initiation and processing
  - Error cases (expired assertions, invalid signatures, disabled providers)
- [ ] Integration tests with mock IdP responses
- [ ] Event streaming for audit trail
- [ ] Thread-safe concurrent access to provider registry
- [ ] Tests pass with `./gradlew test`

---

## Task 2: Document Template Engine

### Overview

Implement a document template engine that enables creating documents from templates with variable substitution, conditional sections, and repeating blocks. Integrates with the existing `documents` module for storage and versioning.

### Module Location

```
templates/
  src/main/kotlin/com/mindvault/templates/
    TemplateService.kt      # Main service implementation
    domain.kt               # Data classes and sealed types
    handlers.kt             # Ktor route handlers
    repository.kt           # Template storage
    parser.kt               # Template syntax parser
    renderer.kt             # Template rendering engine
  src/test/kotlin/com/mindvault/templates/
    TemplateTests.kt        # Unit and integration tests
```

### Interface Contract

```kotlin
package com.helixops.templates

import kotlinx.coroutines.flow.Flow
import java.time.Instant

/**
 * Document Template Engine for creating documents from reusable templates.
 *
 * Supports variable substitution, conditional sections, repeating blocks,
 * and nested template includes. Output can be rendered to multiple formats.
 */
interface TemplateService {

    /**
     * Creates a new template from source content.
     *
     * Parses the template syntax, validates all expressions, and stores
     * the compiled template for efficient rendering.
     *
     * @param request The template creation request
     * @return The created template with parsed metadata
     * @throws TemplateSyntaxException if the template contains invalid syntax
     * @throws DuplicateTemplateException if a template with the same name exists
     */
    suspend fun createTemplate(request: CreateTemplateRequest): Template

    /**
     * Updates an existing template, creating a new version.
     *
     * @param templateId The template ID to update
     * @param request The update request with new content
     * @return The updated template with incremented version
     * @throws TemplateNotFoundException if the template does not exist
     * @throws TemplateSyntaxException if the new content has invalid syntax
     */
    suspend fun updateTemplate(
        templateId: String,
        request: UpdateTemplateRequest
    ): Template

    /**
     * Retrieves a template by ID with optional version selection.
     *
     * @param templateId The template ID
     * @param version Optional specific version (defaults to latest)
     * @return The template or null if not found
     */
    suspend fun getTemplate(templateId: String, version: Int? = null): Template?

    /**
     * Lists templates with filtering and pagination.
     *
     * @param category Filter by category (or null for all)
     * @param tags Filter by tags (templates must have ALL specified tags)
     * @param page Page number (1-indexed)
     * @param pageSize Number of items per page
     * @return Paginated list of templates
     */
    suspend fun listTemplates(
        category: String? = null,
        tags: Set<String>? = null,
        page: Int = 1,
        pageSize: Int = 20
    ): TemplateListResult

    /**
     * Deletes a template and all its versions.
     *
     * @param templateId The template ID to delete
     * @return True if deleted, false if not found
     */
    suspend fun deleteTemplate(templateId: String): Boolean

    /**
     * Renders a template with the provided data context.
     *
     * Performs variable substitution, evaluates conditionals, expands
     * repeating blocks, and processes nested includes.
     *
     * @param templateId The template to render
     * @param context The data context for variable substitution
     * @param options Rendering options (format, strict mode, etc.)
     * @return The rendered document content
     * @throws TemplateNotFoundException if the template does not exist
     * @throws RenderException if rendering fails (missing variables, type errors)
     * @throws CircularIncludeException if template includes form a cycle
     */
    suspend fun render(
        templateId: String,
        context: RenderContext,
        options: RenderOptions = RenderOptions()
    ): RenderResult

    /**
     * Renders a template and saves the result as a document.
     *
     * @param templateId The template to render
     * @param context The data context
     * @param documentRequest Metadata for the created document
     * @return The created document ID and render result
     */
    suspend fun renderAndSave(
        templateId: String,
        context: RenderContext,
        documentRequest: CreateDocumentFromTemplateRequest
    ): DocumentRenderResult

    /**
     * Validates a template without saving it.
     *
     * Parses syntax, checks for undefined variables in strict mode,
     * and returns validation diagnostics.
     *
     * @param source The template source content
     * @return Validation result with any warnings or errors
     */
    suspend fun validateTemplate(source: String): TemplateValidationResult

    /**
     * Extracts all variables, conditionals, and includes from a template.
     *
     * Useful for building dynamic forms to collect render context.
     *
     * @param templateId The template to analyze
     * @return Template schema with all placeholders and their types
     */
    suspend fun extractSchema(templateId: String): TemplateSchema

    /**
     * Previews a render with sample data.
     *
     * Uses the template's default sample context if available.
     *
     * @param templateId The template to preview
     * @param sampleContext Optional override sample data
     * @return Preview render result (may have placeholder warnings)
     */
    suspend fun preview(
        templateId: String,
        sampleContext: RenderContext? = null
    ): RenderResult

    /**
     * Clones a template with a new name.
     *
     * @param sourceTemplateId The template to clone
     * @param newName The name for the cloned template
     * @return The cloned template
     */
    suspend fun cloneTemplate(
        sourceTemplateId: String,
        newName: String
    ): Template

    /**
     * Streams template change events for real-time updates.
     *
     * @return Flow of template events
     */
    fun streamTemplateEvents(): Flow<TemplateEvent>
}
```

### Required Data Classes

```kotlin
package com.helixops.templates

import kotlinx.serialization.Serializable

enum class OutputFormat { TEXT, HTML, MARKDOWN, JSON }

enum class TemplateEventType {
    TEMPLATE_CREATED,
    TEMPLATE_UPDATED,
    TEMPLATE_DELETED,
    TEMPLATE_RENDERED
}

@Serializable
data class CreateTemplateRequest(
    val name: String,
    val description: String,
    val category: String,
    val tags: Set<String> = emptySet(),
    val source: String,
    val sampleContext: Map<String, Any?> = emptyMap(),
    val outputFormat: OutputFormat = OutputFormat.TEXT
)

@Serializable
data class UpdateTemplateRequest(
    val name: String? = null,
    val description: String? = null,
    val category: String? = null,
    val tags: Set<String>? = null,
    val source: String? = null,
    val sampleContext: Map<String, Any?>? = null,
    val outputFormat: OutputFormat? = null
)

@Serializable
data class Template(
    val id: String,
    val name: String,
    val description: String,
    val category: String,
    val tags: Set<String>,
    val source: String,
    val compiledAst: String,           // Serialized AST for fast rendering
    val version: Int,
    val outputFormat: OutputFormat,
    val variables: List<TemplateVariable>,
    val createdAt: Long,
    val updatedAt: Long,
    val createdBy: String
)

@Serializable
data class TemplateVariable(
    val name: String,
    val type: VariableType,
    val required: Boolean,
    val defaultValue: String?,
    val description: String?
)

enum class VariableType { STRING, NUMBER, BOOLEAN, DATE, LIST, OBJECT }

@Serializable
data class TemplateListResult(
    val templates: List<Template>,
    val page: Int,
    val pageSize: Int,
    val totalItems: Int,
    val totalPages: Int
)

@Serializable
data class RenderContext(
    val variables: Map<String, Any?>,
    val locale: String = "en-US",
    val timezone: String = "UTC"
)

@Serializable
data class RenderOptions(
    val strictMode: Boolean = false,   // Fail on undefined variables
    val outputFormat: OutputFormat? = null,  // Override template default
    val maxIterations: Int = 1000,     // Limit for repeating blocks
    val maxIncludes: Int = 10,         // Limit for nested includes
    val escapeHtml: Boolean = true
)

@Serializable
data class RenderResult(
    val content: String,
    val outputFormat: OutputFormat,
    val renderedAt: Long,
    val warnings: List<RenderWarning>,
    val statistics: RenderStatistics
)

@Serializable
data class RenderWarning(
    val code: String,
    val message: String,
    val line: Int?,
    val column: Int?
)

@Serializable
data class RenderStatistics(
    val variablesSubstituted: Int,
    val conditionalsEvaluated: Int,
    val blocksExpanded: Int,
    val includesProcessed: Int,
    val renderTimeMs: Long
)

@Serializable
data class CreateDocumentFromTemplateRequest(
    val title: String,
    val ownerId: String,
    val tags: List<String> = emptyList()
)

@Serializable
data class DocumentRenderResult(
    val documentId: String,
    val renderResult: RenderResult
)

@Serializable
data class TemplateValidationResult(
    val isValid: Boolean,
    val errors: List<TemplateError>,
    val warnings: List<TemplateWarning>,
    val variables: List<TemplateVariable>
)

@Serializable
data class TemplateError(
    val code: String,
    val message: String,
    val line: Int,
    val column: Int,
    val snippet: String?
)

@Serializable
data class TemplateWarning(
    val code: String,
    val message: String,
    val line: Int?,
    val column: Int?
)

@Serializable
data class TemplateSchema(
    val templateId: String,
    val variables: List<TemplateVariable>,
    val conditionals: List<ConditionalBlock>,
    val repeatingBlocks: List<RepeatingBlock>,
    val includes: List<IncludeReference>
)

@Serializable
data class ConditionalBlock(
    val expression: String,
    val variables: List<String>,
    val line: Int
)

@Serializable
data class RepeatingBlock(
    val iteratorVariable: String,
    val collectionExpression: String,
    val line: Int
)

@Serializable
data class IncludeReference(
    val templateId: String,
    val line: Int
)

@Serializable
data class TemplateEvent(
    val eventId: String,
    val eventType: TemplateEventType,
    val templateId: String,
    val version: Int?,
    val userId: String?,
    val timestamp: Long,
    val metadata: Map<String, String>
)

sealed class TemplateException(message: String) : Exception(message)
class TemplateNotFoundException(templateId: String) : TemplateException("Template not found: $templateId")
class DuplicateTemplateException(name: String) : TemplateException("Template already exists: $name")
class TemplateSyntaxException(errors: List<TemplateError>) : TemplateException("Syntax errors: ${errors.size}")
class RenderException(message: String, val warnings: List<RenderWarning>) : TemplateException(message)
class CircularIncludeException(chain: List<String>) : TemplateException("Circular include: ${chain.joinToString(" -> ")}")
```

### Template Syntax Specification

The template engine should support the following syntax:

```
Variable substitution:     {{variableName}}
Nested property access:    {{user.profile.name}}
Default values:            {{title|"Untitled"}}

Conditionals:
  {{#if condition}}...{{/if}}
  {{#if condition}}...{{#else}}...{{/if}}
  {{#unless condition}}...{{/unless}}

Repeating blocks:
  {{#each items as item}}
    {{item.name}}: {{item.value}}
  {{/each}}

  {{#each items as item, index}}
    {{index}}: {{item}}
  {{/each}}

Includes:
  {{> partialTemplateId}}
  {{> partialTemplateId context=user}}

Built-in helpers:
  {{uppercase name}}
  {{lowercase name}}
  {{dateFormat date "yyyy-MM-dd"}}
  {{numberFormat amount "#,##0.00"}}
  {{truncate description 100}}
  {{join tags ", "}}
```

### Architectural Requirements

1. **Follow existing patterns from `documents` module:**
   - Use `Flow<T>` for streaming operations
   - Use `kotlinx.serialization` with custom serializers for complex types
   - Implement repository layer for persistence
   - Handle coroutine cancellation properly

2. **Integration points:**
   - Store rendered documents via `DocumentService.saveDocument()`
   - Use `shared/cache/CacheManager` for compiled template caching
   - Publish events via `shared/events/EventBus`
   - Use `shared/observability/Logging` for render metrics

3. **Performance requirements:**
   - Compile templates to AST on creation/update for fast rendering
   - Cache compiled templates with invalidation on update
   - Support streaming render for large templates
   - Limit recursion depth for includes and loops

### Acceptance Criteria

- [ ] All interface methods implemented with proper error handling
- [ ] Minimum 40 unit tests covering:
  - Template CRUD operations
  - Variable substitution (simple, nested, with defaults)
  - Conditional blocks (if/else/unless)
  - Repeating blocks with index
  - Nested includes with cycle detection
  - All built-in helpers
  - Error cases (syntax errors, missing variables, type mismatches)
- [ ] Integration tests with `DocumentService`
- [ ] Parser handles malformed input gracefully
- [ ] Render statistics and warnings captured
- [ ] Tests pass with `./gradlew test`

---

## Task 3: API Usage Analytics Service

### Overview

Implement an API usage analytics service that tracks request metrics, rate limiting counters, usage quotas, and billing-relevant consumption data. Integrates with the `gateway` module for request interception and the `billing` module for usage-based charges.

### Module Location

```
usage/
  src/main/kotlin/com/mindvault/usage/
    UsageService.kt         # Main service implementation
    domain.kt               # Data classes and sealed types
    handlers.kt             # Ktor route handlers
    repository.kt           # Usage data storage
    aggregator.kt           # Metrics aggregation logic
    ratelimit.kt            # Rate limiting implementation
  src/test/kotlin/com/mindvault/usage/
    UsageTests.kt           # Unit and integration tests
```

### Interface Contract

```kotlin
package com.helixops.usage

import kotlinx.coroutines.flow.Flow
import java.time.Instant

/**
 * API Usage Analytics Service for tracking consumption and enforcing limits.
 *
 * Provides real-time request tracking, rate limiting with multiple algorithms,
 * quota management, and usage aggregation for billing.
 */
interface UsageService {

    /**
     * Records an API request for tracking and rate limiting.
     *
     * Should be called from gateway middleware for every request.
     *
     * @param event The request event to record
     * @return RecordResult with rate limit status and remaining quota
     */
    suspend fun recordRequest(event: RequestEvent): RecordResult

    /**
     * Checks if a request should be rate limited without recording.
     *
     * Useful for pre-flight checks before expensive operations.
     *
     * @param clientId The client making the request
     * @param endpoint The API endpoint being accessed
     * @return RateLimitStatus with current limits and remaining capacity
     */
    suspend fun checkRateLimit(
        clientId: String,
        endpoint: String
    ): RateLimitStatus

    /**
     * Gets current usage statistics for a client.
     *
     * @param clientId The client ID
     * @param period The time period to aggregate (HOUR, DAY, MONTH)
     * @return UsageStatistics for the requested period
     */
    suspend fun getUsageStats(
        clientId: String,
        period: UsagePeriod
    ): UsageStatistics

    /**
     * Gets usage statistics aggregated by endpoint.
     *
     * @param clientId The client ID
     * @param period The time period
     * @return Map of endpoint to usage statistics
     */
    suspend fun getUsageByEndpoint(
        clientId: String,
        period: UsagePeriod
    ): Map<String, EndpointStatistics>

    /**
     * Gets historical usage data for trend analysis.
     *
     * @param clientId The client ID
     * @param startTime Start of the time range
     * @param endTime End of the time range
     * @param granularity Time bucket size
     * @return List of usage data points
     */
    suspend fun getUsageHistory(
        clientId: String,
        startTime: Long,
        endTime: Long,
        granularity: TimeGranularity
    ): List<UsageDataPoint>

    /**
     * Configures rate limits for a client.
     *
     * @param clientId The client ID
     * @param config The rate limit configuration
     * @return The applied configuration
     */
    suspend fun configureRateLimits(
        clientId: String,
        config: RateLimitConfig
    ): RateLimitConfig

    /**
     * Gets the current rate limit configuration for a client.
     *
     * @param clientId The client ID
     * @return The rate limit configuration or default if not customized
     */
    suspend fun getRateLimitConfig(clientId: String): RateLimitConfig

    /**
     * Configures usage quota for a client.
     *
     * @param clientId The client ID
     * @param quota The quota configuration
     * @return The applied quota
     */
    suspend fun configureQuota(
        clientId: String,
        quota: QuotaConfig
    ): QuotaConfig

    /**
     * Gets current quota status for a client.
     *
     * @param clientId The client ID
     * @return QuotaStatus with usage and remaining allowance
     */
    suspend fun getQuotaStatus(clientId: String): QuotaStatus

    /**
     * Resets rate limit counters for a client.
     *
     * Used for support/admin operations.
     *
     * @param clientId The client ID
     * @param endpoints Optional specific endpoints (null for all)
     * @return True if reset was performed
     */
    suspend fun resetRateLimits(
        clientId: String,
        endpoints: Set<String>? = null
    ): Boolean

    /**
     * Generates a usage report for billing.
     *
     * @param clientId The client ID
     * @param billingPeriodStart Start of billing period
     * @param billingPeriodEnd End of billing period
     * @return UsageReport with billable metrics
     */
    suspend fun generateBillingReport(
        clientId: String,
        billingPeriodStart: Long,
        billingPeriodEnd: Long
    ): UsageReport

    /**
     * Streams real-time usage events for monitoring.
     *
     * @param clientId Optional filter by client (null for all)
     * @param eventTypes Filter by event types (empty for all)
     * @return Flow of usage events
     */
    fun streamUsageEvents(
        clientId: String? = null,
        eventTypes: Set<UsageEventType> = emptySet()
    ): Flow<UsageEvent>

    /**
     * Gets top consumers for capacity planning.
     *
     * @param period The time period to analyze
     * @param limit Maximum number of results
     * @param metric The metric to rank by
     * @return List of top consumers with their usage
     */
    suspend fun getTopConsumers(
        period: UsagePeriod,
        limit: Int = 10,
        metric: UsageMetric = UsageMetric.REQUEST_COUNT
    ): List<ConsumerUsage>

    /**
     * Identifies usage anomalies for alerting.
     *
     * @param clientId Optional specific client (null for all)
     * @param lookbackHours Hours of history to analyze
     * @return List of detected anomalies
     */
    suspend fun detectAnomalies(
        clientId: String? = null,
        lookbackHours: Int = 24
    ): List<UsageAnomaly>
}
```

### Required Data Classes

```kotlin
package com.helixops.usage

import kotlinx.serialization.Serializable

enum class UsagePeriod { HOUR, DAY, WEEK, MONTH }

enum class TimeGranularity { MINUTE, HOUR, DAY }

enum class UsageMetric { REQUEST_COUNT, DATA_TRANSFER_BYTES, COMPUTE_UNITS, ERROR_COUNT }

enum class UsageEventType {
    REQUEST_RECORDED,
    RATE_LIMITED,
    QUOTA_WARNING,
    QUOTA_EXCEEDED,
    ANOMALY_DETECTED
}

enum class RateLimitAlgorithm {
    FIXED_WINDOW,
    SLIDING_WINDOW,
    TOKEN_BUCKET,
    LEAKY_BUCKET
}

@Serializable
data class RequestEvent(
    val clientId: String,
    val endpoint: String,
    val method: String,
    val statusCode: Int,
    val requestSizeBytes: Long,
    val responseSizeBytes: Long,
    val latencyMs: Long,
    val timestamp: Long = System.currentTimeMillis(),
    val metadata: Map<String, String> = emptyMap()
)

@Serializable
data class RecordResult(
    val recorded: Boolean,
    val rateLimited: Boolean,
    val quotaExceeded: Boolean,
    val remainingRequests: Long?,
    val remainingQuota: Long?,
    val retryAfterSeconds: Int?
)

@Serializable
data class RateLimitStatus(
    val clientId: String,
    val endpoint: String,
    val algorithm: RateLimitAlgorithm,
    val limit: Long,
    val remaining: Long,
    val resetAtMs: Long,
    val isLimited: Boolean
)

@Serializable
data class UsageStatistics(
    val clientId: String,
    val period: UsagePeriod,
    val periodStart: Long,
    val periodEnd: Long,
    val totalRequests: Long,
    val successfulRequests: Long,
    val failedRequests: Long,
    val totalDataTransferBytes: Long,
    val averageLatencyMs: Double,
    val p95LatencyMs: Double,
    val p99LatencyMs: Double,
    val uniqueEndpoints: Int
)

@Serializable
data class EndpointStatistics(
    val endpoint: String,
    val requestCount: Long,
    val errorCount: Long,
    val errorRate: Double,
    val averageLatencyMs: Double,
    val p95LatencyMs: Double,
    val totalDataTransferBytes: Long
)

@Serializable
data class UsageDataPoint(
    val timestamp: Long,
    val requestCount: Long,
    val errorCount: Long,
    val dataTransferBytes: Long,
    val averageLatencyMs: Double
)

@Serializable
data class RateLimitConfig(
    val clientId: String,
    val algorithm: RateLimitAlgorithm = RateLimitAlgorithm.SLIDING_WINDOW,
    val globalLimit: RateLimit,
    val endpointLimits: Map<String, RateLimit> = emptyMap(),
    val burstAllowance: Int = 0,
    val enabled: Boolean = true
)

@Serializable
data class RateLimit(
    val requests: Long,
    val windowSeconds: Int
)

@Serializable
data class QuotaConfig(
    val clientId: String,
    val monthlyRequestLimit: Long?,
    val monthlyDataTransferBytes: Long?,
    val dailyRequestLimit: Long?,
    val warningThresholdPercent: Int = 80,
    val hardLimit: Boolean = true,     // Block when exceeded vs allow with overage
    val resetDay: Int = 1              // Day of month for quota reset
)

@Serializable
data class QuotaStatus(
    val clientId: String,
    val periodStart: Long,
    val periodEnd: Long,
    val requestsUsed: Long,
    val requestsLimit: Long?,
    val requestsRemaining: Long?,
    val dataTransferUsed: Long,
    val dataTransferLimit: Long?,
    val dataTransferRemaining: Long?,
    val percentUsed: Double,
    val isWarning: Boolean,
    val isExceeded: Boolean
)

@Serializable
data class UsageReport(
    val clientId: String,
    val billingPeriodStart: Long,
    val billingPeriodEnd: Long,
    val generatedAt: Long,
    val summary: UsageStatistics,
    val endpointBreakdown: List<EndpointStatistics>,
    val dailyTrend: List<UsageDataPoint>,
    val billableMetrics: BillableMetrics
)

@Serializable
data class BillableMetrics(
    val totalRequests: Long,
    val billableRequests: Long,        // Excluding free tier
    val dataTransferGb: Double,
    val computeUnits: Long,
    val overage: OverageDetails?
)

@Serializable
data class OverageDetails(
    val requestsOverLimit: Long,
    val dataTransferOverLimitGb: Double
)

@Serializable
data class UsageEvent(
    val eventId: String,
    val eventType: UsageEventType,
    val clientId: String,
    val endpoint: String?,
    val timestamp: Long,
    val details: Map<String, String>
)

@Serializable
data class ConsumerUsage(
    val clientId: String,
    val metricValue: Long,
    val percentOfTotal: Double,
    val trend: UsageTrend
)

enum class UsageTrend { INCREASING, STABLE, DECREASING }

@Serializable
data class UsageAnomaly(
    val anomalyId: String,
    val clientId: String,
    val endpoint: String?,
    val anomalyType: AnomalyType,
    val severity: AnomalySeverity,
    val detectedAt: Long,
    val description: String,
    val baseline: Double,
    val observed: Double,
    val deviationPercent: Double
)

enum class AnomalyType {
    SPIKE_IN_REQUESTS,
    SPIKE_IN_ERRORS,
    LATENCY_DEGRADATION,
    UNUSUAL_ENDPOINT_ACCESS,
    POTENTIAL_ABUSE
}

enum class AnomalySeverity { LOW, MEDIUM, HIGH, CRITICAL }

sealed class UsageException(message: String) : Exception(message)
class RateLimitExceededException(val clientId: String, val retryAfterSeconds: Int) :
    UsageException("Rate limit exceeded for $clientId, retry after $retryAfterSeconds seconds")
class QuotaExceededException(val clientId: String, val quotaType: String) :
    UsageException("Quota exceeded for $clientId: $quotaType")
class ClientNotFoundException(clientId: String) : UsageException("Client not found: $clientId")
```

### Architectural Requirements

1. **Follow existing patterns:**
   - Use atomic counters (`AtomicLong`, `AtomicInteger`) for rate limiting
   - Use `ConcurrentHashMap` with LRU eviction for counter storage
   - Implement sliding window with sub-buckets for accuracy
   - Use coroutines for async aggregation jobs

2. **Integration points:**
   - Expose middleware for `GatewayService` request interception
   - Provide usage data to `BillingService` for invoicing
   - Publish events via `shared/events/EventBus`
   - Use `shared/observability/Logging` for metrics export

3. **Performance requirements:**
   - Sub-millisecond rate limit checks
   - Background aggregation to avoid blocking requests
   - Efficient time-series storage with rollup
   - Memory-bounded counter storage with eviction

4. **Rate limiting algorithms:**
   - Fixed Window: Simple counter reset at window boundaries
   - Sliding Window: Weighted average of current and previous windows
   - Token Bucket: Configurable refill rate and burst capacity
   - Leaky Bucket: Constant output rate smoothing

### Acceptance Criteria

- [ ] All interface methods implemented with proper error handling
- [ ] Minimum 45 unit tests covering:
  - Request recording and retrieval
  - All four rate limiting algorithms
  - Quota tracking and enforcement
  - Usage aggregation by period and granularity
  - Billing report generation
  - Anomaly detection logic
  - Concurrent access safety
  - Edge cases (counter overflow, time boundaries)
- [ ] Integration tests with simulated request load
- [ ] Rate limit checks complete in under 1ms
- [ ] Memory usage bounded with eviction policies
- [ ] Tests pass with `./gradlew test`

---

## General Implementation Guidelines

### Code Organization

Follow the existing module structure:
- `*Service.kt` - Main interface and implementation class
- `domain.kt` - Data classes, enums, sealed types, exceptions
- `handlers.kt` - Ktor route handlers
- `repository.kt` - Data persistence layer
- `*Tests.kt` - JUnit 5 tests with kotlin.test assertions

### Testing Patterns

Reference `AuthTests.kt` for testing patterns:
- Use `runTest` for coroutine tests
- Create fixture classes for deterministic testing
- Test both success and error paths
- Include edge cases and boundary conditions
- Use descriptive test names that explain the scenario

### Common Dependencies

```kotlin
// Already available in the project
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.Serializable
import io.ktor.server.routing.*
import org.junit.jupiter.api.Test
import kotlin.test.*
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicLong
```

### Error Handling

- Use sealed exception hierarchies for domain errors
- Throw specific exceptions, not generic `Exception`
- Include relevant context in exception messages
- Handle `CancellationException` properly (rethrow, don't catch)

### Thread Safety

- Use `Mutex` for coroutine-safe critical sections
- Use `ConcurrentHashMap` for shared mutable state
- Use atomic operations for counters
- Document thread-safety guarantees in KDoc
