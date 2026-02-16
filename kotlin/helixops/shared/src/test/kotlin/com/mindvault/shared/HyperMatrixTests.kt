package com.helixops.shared

import org.junit.jupiter.api.DynamicTest
import org.junit.jupiter.api.Tag
import org.junit.jupiter.api.TestFactory
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertNotEquals
import org.junit.jupiter.api.Assertions.assertNotNull
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Assertions.assertTrue
import com.helixops.shared.cache.CacheManager
import com.helixops.shared.config.AppConfig
import com.helixops.shared.database.DatabaseFactory
import com.helixops.shared.delegation.DelegationUtils
import com.helixops.shared.events.EventBus
import com.helixops.shared.kotlin.KotlinUtils
import com.helixops.shared.models.Models
import com.helixops.shared.observability.Logging
import com.helixops.shared.security.JwtProvider
import com.helixops.shared.serialization.SerializationUtils

@Tag("stress")
class HyperMatrixTests {

    private val testCases: List<Pair<String, () -> Unit>> = buildList {

        // =====================================================================
        // CacheManager (24 tests)
        // =====================================================================
        add("cache_isExpired_boundary" to {
            assertTrue(CacheManager.isExpired(100, 100), "now==expiresAt should be expired (>=)")
        })
        add("cache_evictLru_oldest" to {
            val entries = listOf("a" to 1L, "b" to 3L, "c" to 2L)
            val evicted = CacheManager.evictLru(entries, 2)
            assertEquals(listOf("a", "c"), evicted, "LRU should evict oldest (lowest timestamp)")
        })
        add("cache_getCacheSize_current" to {
            assertEquals(5, CacheManager.getCacheSize(5, 100), "Should return currentEntries not maxCapacity")
        })
        add("cache_invalidatePattern_match" to {
            val keys = listOf("user:1", "user:2", "other:1")
            val result = CacheManager.invalidatePattern(keys, "user:")
            assertTrue(result.size >= 2, "Should match keys starting with pattern, not exact match")
        })
        add("cache_mergeCacheEntries_newer" to {
            val result = CacheManager.mergeCacheEntries("old" to 1L, "new" to 2L)
            assertEquals("new", result.first, "Should return incoming when it has higher timestamp")
        })
        add("cache_getCacheStats_expired" to {
            val entries = listOf("a" to 50L, "b" to 200L)
            val (_, expired) = CacheManager.getCacheStats(entries, 100L)
            assertTrue(expired > 0, "Entries with timestamp < now should be counted as expired")
        })
        add("cache_batchEvict_consecutive" to {
            val result = CacheManager.batchEvict(listOf("a", "b", "c", "d"), setOf("a", "b"))
            assertEquals(listOf("c", "d"), result, "Should evict all matching keys without index skip")
        })
        add("cache_normalizeCacheKey_lowercase" to {
            assertEquals("user:key", CacheManager.normalizeCacheKey("  User:KEY  "), "Should trim and lowercase")
        })
        add("cache_cacheVersionMismatch_fallback" to {
            val r = CacheManager.cacheVersionMismatch(1, 2, "cached", "fallback")
            assertEquals("fallback", r, "Version mismatch should return fallback")
        })
        add("cache_applyEvictionPolicy_boundary" to {
            val r = CacheManager.applyEvictionPolicy(101, 100, 10)
            assertEquals(10, r, "Should evict when currentSize > maxSize (not > maxSize+1)")
        })
        add("cache_distributedLockKey_namespace" to {
            val r = CacheManager.distributedLockKey("myns", "res1")
            assertTrue(r.contains("myns"), "Lock key should include namespace")
        })
        add("cache_calculateHitRate_total" to {
            val r = CacheManager.calculateHitRate(8, 2)
            assertEquals(0.8, r, 0.01, "Hit rate = hits/(hits+misses) = 8/10 = 0.8")
        })
        add("cache_cacheEntryEquals_value" to {
            assertFalse(
                CacheManager.cacheEntryEquals("k", "v1", "k", "v2"),
                "Same key but different value should not be equal"
            )
        })
        add("cache_parseTtlString_minutes" to {
            assertEquals(300000L, CacheManager.parseTtlString("5m"), "5m should be 300000ms")
        })
        add("cache_regionCacheKey_noDup" to {
            val r = CacheManager.regionCacheKey("us-east", "cache", "key1")
            assertEquals("cache:us-east:key1", r, "Should not duplicate prefix in key")
        })
        add("cache_compactCache_filter" to {
            val entries = mapOf("a" to 50L, "b" to 200L)
            val result = CacheManager.compactCache(entries, 100L)
            assertTrue(result.isNotEmpty(), "Should retain non-expired entries, not return empty")
        })
        add("cache_multiGetMerge_union" to {
            val local = mapOf("a" to "1")
            val remote = mapOf("b" to "2")
            val result = CacheManager.multiGetMerge(local, remote)
            assertEquals(2, result.size, "Should merge all keys (union), not just intersection")
        })
        add("cache_ttlJitter_nonzero" to {
            val r = CacheManager.ttlJitter(10000L, 20)
            assertNotEquals(10000L, r, "Jitter should add variation, not multiply by 0")
        })
        add("cache_shouldCache_statusCode" to {
            assertFalse(CacheManager.shouldCache(500, "error body"), "Should not cache 5xx responses")
        })
        add("cache_buildHashKey_length" to {
            val r = CacheManager.buildHashKey("some-input", 8)
            assertEquals(8, r.length, "Hash key length should equal maxLength")
        })
        add("cache_warmCache_ascending" to {
            val entries = listOf("hot" to 100L, "cold" to 1L, "warm" to 50L)
            val result = CacheManager.warmCache(entries)
            assertEquals("cold", result.first(), "Warmup should start with least recently used (ascending)")
        })
        add("cache_serializeComplexKey_values" to {
            val parts = mapOf("user" to "123" as Any, "region" to "us" as Any)
            val r = CacheManager.serializeComplexKey(parts)
            assertTrue(r.contains("123"), "Complex key should include values not just keys")
        })
        add("cache_buildCacheKey_readable" to {
            val r = CacheManager.buildCacheKey("user", listOf("id", "42"))
            assertTrue(r.contains("id") || r.contains("42"), "Cache key should contain readable params")
        })
        add("cache_calculateTtl_overflow" to {
            val r = CacheManager.calculateTtl(2_500_000)
            assertEquals(2_500_000_000L, r, "Large ttlSeconds should not overflow int multiplication")
        })

        // =====================================================================
        // AppConfig (24 tests)
        // =====================================================================
        add("config_loadPort_envValue" to {
            assertEquals(9090, AppConfig.loadPort("9090", 8080), "Should parse env value, not return default")
        })
        add("config_buildJdbcUrl_order" to {
            val r = AppConfig.buildJdbcUrl("localhost", 5432, "mydb")
            assertEquals("jdbc:postgresql://localhost:5432/mydb", r, "Host before port in JDBC URL")
        })
        add("config_mergeConfigs_base" to {
            val base = mapOf("a" to "1", "b" to "2")
            val over = mapOf("b" to "3", "c" to "4")
            val result = AppConfig.mergeConfigs(base, over)
            assertEquals("1", result["a"], "Base entries should be preserved in merge")
        })
        add("config_parseBoolean_yes" to {
            assertTrue(AppConfig.parseBoolean("yes", false), "'yes' should parse as true")
        })
        add("config_validatePortRange_zero" to {
            assertFalse(AppConfig.validatePortRange(0), "Port 0 should be invalid")
        })
        add("config_getNestedKey_dot" to {
            val config = mapOf("app.db/host" to "localhost")
            assertEquals("localhost", AppConfig.getNestedKey(config, "app.db/host"), "Should split on '.' not '/'")
        })
        add("config_resolveTemplate_all" to {
            val tpl = "\${name} and \${name}"
            val result = AppConfig.resolveTemplate(tpl, mapOf("name" to "X"))
            assertEquals("X and X", result, "Should replace ALL occurrences, not just first")
        })
        add("config_parseDuration_minutes" to {
            assertEquals(60000L, AppConfig.parseDuration("1", "m"), "1 minute = 60000ms")
        })
        add("config_configOverride_applied" to {
            val base = mapOf("key" to "old")
            val result = AppConfig.configOverride(base, "key", "new")
            assertEquals("new", result["key"], "Override should be applied to the map")
        })
        add("config_parseList_delimiter" to {
            val r = AppConfig.parseList("a,b,c", ",")
            assertEquals(listOf("a", "b", "c"), r, "Should split on provided delimiter, not ';'")
        })
        add("config_validateConfig_all" to {
            val config = mapOf("a" to "1")
            assertFalse(
                AppConfig.validateConfig(config, listOf("a", "b")),
                "Should require ALL keys present, not just ANY"
            )
        })
        add("config_getRetryConfig_noMinus" to {
            assertEquals(3, AppConfig.getRetryConfig("3", 1), "Should return parsed value as-is")
        })
        add("config_buildRedisUrl_password" to {
            val r = AppConfig.buildRedisUrl("localhost", 6379, "secret")
            assertTrue(r.contains("secret"), "Should include password in Redis URL")
        })
        add("config_configToMap_fullKey" to {
            val entries = listOf("app.db.host" to "localhost", "app.db.port" to "5432")
            val result = AppConfig.configToMap(entries)
            assertTrue(result.containsKey("app.db.host"), "Should preserve full key, not just last segment")
        })
        add("config_loadFeatureFlags_noNegate" to {
            val flags = mapOf("feature_x" to "true")
            val result = AppConfig.loadFeatureFlags(flags)
            assertTrue(result["feature_x"]!!, "Should not negate boolean flag values")
        })
        add("config_parseLogLevel_default" to {
            assertEquals("INFO", AppConfig.parseLogLevel(null), "Default log level should be INFO")
        })
        add("config_getKafkaConfig_colon" to {
            val r = AppConfig.getKafkaConfig(listOf("broker1", "broker2"), 9092)
            assertEquals("broker1:9092,broker2:9092", r, "Broker format should use ':' not '/'")
        })
        add("config_calculatePoolTimeout_multiply" to {
            assertEquals(2000L, AppConfig.calculatePoolTimeout(1000, 2.0), "Should multiply base * multiplier")
        })
        add("config_loadSslConfig_noNegate" to {
            assertTrue(AppConfig.loadSslConfig("true"), "trustAll=true should return true, not negated")
        })
        add("config_parseMemorySize_mib" to {
            assertEquals(1048576L, AppConfig.parseMemorySize("1MIB"), "1 MiB = 1024*1024 = 1048576 bytes")
        })
        add("config_loadRateLimitConfig_order" to {
            val (rate, burst) = AppConfig.loadRateLimitConfig(100, 50)
            assertEquals(100, rate, "First element should be ratePerSec")
            assertEquals(50, burst, "Second element should be burstSize")
        })
        add("config_encryptConfigValue_noSuffix" to {
            val r = AppConfig.encryptConfigValue("test")
            assertFalse(r.endsWith("=="), "Hex encoding should not have '==' suffix")
        })
        add("config_resolveEnvPlaceholders_all" to {
            val tpl = "\${A} and \${B}"
            val env = mapOf("A" to "x", "B" to "y")
            val r = AppConfig.resolveEnvPlaceholders(tpl, env)
            assertEquals("x and y", r, "Should replace ALL env placeholders")
        })
        add("config_loadConnectionPool_validate" to {
            val (min, max) = AppConfig.loadConnectionPool(10, "5")
            assertTrue(max >= min, "Max pool size should be >= min (should clamp)")
        })

        // =====================================================================
        // DatabaseFactory (24 tests)
        // =====================================================================
        add("db_selectIsolation_readHeavy" to {
            val r = DatabaseFactory.selectIsolationLevel(true)
            assertEquals("READ_COMMITTED", r, "Read-heavy should use READ_COMMITTED, not SERIALIZABLE")
        })
        add("db_batchInsertSize_calculated" to {
            val r = DatabaseFactory.batchInsertSize(10000, 512)
            assertTrue(r < 10000, "Batch size should be calculated from memory, not equal totalRows")
        })
        add("db_buildWhereClause_and" to {
            val r = DatabaseFactory.buildWhereClause(listOf("a = 1", "b = 2"))
            assertTrue(r.contains("AND"), "Multiple conditions should be joined with AND")
        })
        add("db_columnTypeMapping_int" to {
            assertEquals("INTEGER", DatabaseFactory.columnTypeMapping("Int"), "Kotlin Int should map to INTEGER")
        })
        add("db_buildUpdateSql_changed" to {
            val r = DatabaseFactory.buildUpdateSql("users", listOf("name", "email", "age"), listOf("email"), 1L)
            assertFalse(r.contains("name ="), "Should only update changed columns")
        })
        add("db_parseSqlResult_noSkip" to {
            val rows = listOf(listOf("1", "Alice"), listOf("2", "Bob"))
            val result = DatabaseFactory.parseSqlResult(rows)
            assertEquals(2, result.size, "Should not skip first row (it's data, not header)")
        })
        add("db_connectionPoolSize_calculated" to {
            val r = DatabaseFactory.connectionPoolSize(100, 4)
            assertTrue(r > 5, "Pool size should be calculated, not hardcoded 5")
        })
        add("db_buildPaginationQuery_order" to {
            val r = DatabaseFactory.buildPaginationQuery("SELECT * FROM t", 2, 10)
            assertTrue(r.contains("LIMIT 10") && r.contains("OFFSET 20"), "LIMIT pageSize OFFSET offset")
        })
        add("db_buildJoinQuery_inner" to {
            val r = DatabaseFactory.buildJoinQuery("orders", "users", "user_id")
            assertTrue(r.contains("INNER JOIN") || r.contains("JOIN"), "Should use INNER JOIN not CROSS JOIN")
            assertTrue(r.contains("user_id"), "Should include join column")
        })
        add("db_handleDeadlock_retry" to {
            val r = DatabaseFactory.handleDeadlock(1, 3)
            assertEquals("RETRY", r, "Should retry when attempts < maxRetries")
        })
        add("db_normalizeColumnName_underscore" to {
            val r = DatabaseFactory.normalizeColumnName("user_name")
            assertEquals("user_name", r, "Should preserve underscores for snake_case")
        })
        add("db_buildDeleteSql_condition" to {
            val r = DatabaseFactory.buildDeleteSql("users", "id = 1")
            assertTrue(r.contains("WHERE id = 1"), "DELETE should include WHERE condition")
        })
        add("db_calculateQueryTimeout_multiplier" to {
            val r = DatabaseFactory.calculateQueryTimeout(1000L, 2.0)
            assertEquals(2000L, r, "Should apply multiplier to base timeout")
        })
        add("db_buildIndexSql_unique" to {
            val r = DatabaseFactory.buildIndexSql("users", listOf("email"), true)
            assertTrue(r.contains("UNIQUE"), "Should include UNIQUE keyword when requested")
        })
        add("db_migrationOrder_numeric" to {
            val migrations = listOf("V2_create_users", "V10_add_index", "V1_init")
            val result = DatabaseFactory.migrationOrder(migrations)
            assertEquals("V1_init", result[0], "Migrations should be sorted by version number")
            assertEquals("V2_create_users", result[1])
            assertEquals("V10_add_index", result[2])
        })
        add("db_poolHealthCheck_unhealthy" to {
            val r = DatabaseFactory.poolHealthCheck(100, 100, 50)
            assertNotEquals("HEALTHY", r, "Pool at max with failures should not be HEALTHY")
        })
        add("db_buildForeignKey_columns" to {
            val r = DatabaseFactory.buildForeignKey("orders", "user_id", "users", "id")
            assertTrue(r.contains("FOREIGN KEY (user_id)"), "FK column should be child column")
            assertTrue(r.contains("REFERENCES users(id)"), "References should use parent column")
        })
        add("db_transactionRetryDelay_backoff" to {
            val d1 = DatabaseFactory.transactionRetryDelay(1, 100L)
            val d2 = DatabaseFactory.transactionRetryDelay(2, 100L)
            assertTrue(d2 > d1, "Retry delay should increase with attempts (backoff)")
        })
        add("db_buildAggregateQuery_groupBy" to {
            val r = DatabaseFactory.buildAggregateQuery("sales", "amount", "category")
            assertTrue(r.contains("GROUP BY category"), "GROUP BY should use groupByColumn")
        })
        add("db_parseDbUrl_fields" to {
            val r = DatabaseFactory.parseDbUrl("jdbc:postgresql://myhost:5432/mydb")
            assertEquals("myhost", r["host"], "host field should contain actual host")
            assertEquals("mydb", r["database"], "database field should contain actual database")
        })
        add("db_validateColumnLength_le" to {
            assertTrue(DatabaseFactory.validateColumnLength("abc", 5), "length 3 <= 5 should be valid")
            assertTrue(DatabaseFactory.validateColumnLength("abcde", 5), "length 5 <= 5 should be valid")
            assertFalse(DatabaseFactory.validateColumnLength("abcdef", 5), "length 6 > 5 should be invalid")
        })
        add("db_buildUpsertSql_conflict" to {
            val r = DatabaseFactory.buildUpsertSql("users", listOf("id", "name"), "id")
            assertTrue(r.contains("ON CONFLICT"), "Upsert should include ON CONFLICT clause")
        })
        add("db_cacheEntityById_format" to {
            val r = DatabaseFactory.cacheEntityById("user", 42L)
            assertEquals("user:42", r, "Format should be entityType:id")
        })
        add("db_estimateRowCount_nonzero" to {
            val r = DatabaseFactory.estimateRowCount(1_000_000L, 100)
            assertTrue(r > 0, "Row count estimate should be > 0 for non-empty table")
        })

        // =====================================================================
        // DelegationUtils (24 tests)
        // =====================================================================
        add("deleg_selectLazyMode_mt" to {
            assertEquals("SYNCHRONIZED", DelegationUtils.selectLazyMode(true), "Multi-threaded should use SYNCHRONIZED")
        })
        add("deleg_simulateObservable_notify" to {
            val (_, notified) = DelegationUtils.simulateObservable("old", "new", true)
            assertTrue(notified, "Should notify when values differ and notifyChange=true")
        })
        add("deleg_vetoableCheck_reject" to {
            val (stored, accepted) = DelegationUtils.vetoableCheck(5, 15, 10)
            assertFalse(accepted, "Should reject when proposed > maxAllowed")
            assertEquals(5, stored, "Should keep current value when rejected")
        })
        add("deleg_mapDelegation_exact" to {
            val props = mapOf("myProp" to "value" as Any)
            assertEquals("value", DelegationUtils.mapDelegation(props, "myProp"), "Should use exact property name")
        })
        add("deleg_interfaceDelegation_delegate" to {
            assertEquals("delegate", DelegationUtils.interfaceDelegation("self", "delegate", true))
        })
        add("deleg_lazyInitValue_computed" to {
            assertEquals("computed", DelegationUtils.lazyInitValue(true, "computed"))
        })
        add("deleg_delegateCaching_fresh" to {
            assertEquals("fresh", DelegationUtils.delegateCaching("cached", "fresh", 1, 2))
        })
        add("deleg_propertyDelegateGetValue_key" to {
            val storage = mapOf("prop_name" to "value")
            assertEquals("value", DelegationUtils.propertyDelegateGetValue(storage, "name"))
        })
        add("deleg_readOnlyDelegate_unchanged" to {
            val original = listOf("a", "b")
            val result = DelegationUtils.readOnlyDelegate(original, "c")
            assertEquals(listOf("a", "b"), result, "Read-only delegate should not modify the list")
        })
        add("deleg_compositeDelegate_forward" to {
            val r = DelegationUtils.compositeDelegate("  hello  ", listOf("trim", "upper", "prefix"))
            assertEquals("[HELLO]", r, "Transforms should apply in forward order: trim->upper->prefix")
        })
        add("deleg_notNullDelegate_throw" to {
            var threw = false
            try { DelegationUtils.notNullDelegate(false, null) }
            catch (_: Exception) { threw = true }
            assertTrue(threw, "Uninitialized notNull delegate should throw")
        })
        add("deleg_weakReferenceDelegate_fallback" to {
            assertEquals("fallback", DelegationUtils.weakReferenceDelegate(false, "cached", "fallback"))
        })
        add("deleg_syncDelegateAccess_noLock" to {
            val (_, success) = DelegationUtils.syncDelegateAccess(1, "val", false)
            assertFalse(success, "Should fail when lock not acquired")
        })
        add("deleg_memoizedDelegate_fresh" to {
            assertEquals(99, DelegationUtils.memoizedDelegate("new", "old", 42, 99))
        })
        add("deleg_expiringDelegate_expired" to {
            val r = DelegationUtils.expiringDelegate("val", 0L, 2000L, 1000L)
            assertNull(r, "Should return null when expired (elapsed > ttl)")
        })
        add("deleg_validatingDelegate_invalid" to {
            val (stored, _) = DelegationUtils.validatingDelegate(5, 15, 1, 10)
            assertEquals(5, stored, "Should keep current value when new value is out of range")
        })
        add("deleg_loggerDelegation_owner" to {
            assertEquals("Logger[MyService]", DelegationUtils.loggerDelegation("MyService", "BaseClass"))
        })
        add("deleg_configDelegate_updated" to {
            assertEquals("new", DelegationUtils.configDelegate("old", "new", 1, 2))
        })
        add("deleg_defaultDelegate_string" to {
            assertEquals("fallback", DelegationUtils.defaultDelegate(null, 42, "fallback"))
        })
        add("deleg_chainedDelegate_noSkip" to {
            val r = DelegationUtils.chainedDelegate(1, listOf("double", "increment", "double"))
            assertEquals(6, r, "Should apply all delegates without skipping index 1: (1*2+1)*2=6")
        })
        add("deleg_batchDelegate_proper" to {
            val r = DelegationUtils.batchDelegate(listOf("a", "b", "c", "d"), 2)
            assertEquals(listOf(listOf("a", "b"), listOf("c", "d")), r, "Should batch into groups of 2")
        })
        add("deleg_retryDelegate_allAttempts" to {
            val (success, attempts) = DelegationUtils.retryDelegate(listOf(false, false, true), 3)
            assertTrue(success, "Should succeed on 3rd attempt")
            assertEquals(3, attempts, "Should try all attempts up to maxRetries")
        })
        add("deleg_fallbackDelegate_chain" to {
            assertEquals("fb", DelegationUtils.fallbackDelegate(null, "fb", "default"))
        })
        add("deleg_transformDelegate_storage" to {
            assertEquals(500, DelegationUtils.transformDelegate(50, 10, true), "forStorage should multiply: 50*10=500")
        })

        // =====================================================================
        // EventBus (24 tests)
        // =====================================================================
        add("event_selectDispatcher_io" to {
            assertEquals("IO", EventBus.selectDispatcher(true), "IO-bound should use IO dispatcher")
        })
        add("event_calculateBufferCapacity_nonzero" to {
            assertTrue(EventBus.calculateBufferCapacity(10) > 0, "Buffer capacity should be > 0")
        })
        add("event_shouldUseRunBlocking_inCoroutine" to {
            assertFalse(EventBus.shouldUseRunBlocking(true), "Should not use runBlocking inside coroutine")
        })
        add("event_supervisorScopeNeeded_independent" to {
            assertTrue(EventBus.supervisorScopeNeeded(true), "Independent children need supervisor scope")
        })
        add("event_isChannelOpen_closed" to {
            assertFalse(EventBus.isChannelOpen(true, true), "Channel closed for both should not be open")
        })
        add("event_mutexLockOrder_deterministic" to {
            val r1 = EventBus.mutexLockOrder("aaa", "bbb")
            val r2 = EventBus.mutexLockOrder("bbb", "aaa")
            assertEquals(r1, r2, "Lock order should be deterministic regardless of argument order")
        })
        add("event_flowTimeoutMs_nonzero" to {
            assertTrue(EventBus.flowTimeoutMs(100L) > 0, "Flow timeout should be > 0")
        })
        add("event_sharedFlowReplayCount_history" to {
            val r = EventBus.sharedFlowReplayCount(true, 5)
            assertEquals(5, r, "Should return historySize when history required")
        })
        add("event_callbackFlowNeedsAwaitClose" to {
            assertTrue(EventBus.callbackFlowNeedsAwaitClose(true), "Should need awaitClose when has cleanup")
        })
        add("event_handleException_cancellation" to {
            assertEquals("RETHROW", EventBus.handleException("CancellationException"))
        })
        add("event_recommendedScope_ui" to {
            assertNotEquals("GlobalScope", EventBus.recommendedScope(true, false), "Should not recommend GlobalScope")
        })
        add("event_asyncExceptionStrategy_supervisor" to {
            assertNotEquals("IGNORE", EventBus.asyncExceptionStrategy(true), "Supervisor should propagate to handler")
        })
        add("event_producerRate_calculated" to {
            val r = EventBus.producerRate(100L, 4)
            assertTrue(r > 1, "Producer rate should be calculated from consumer capacity")
        })
        add("event_flowMergeStrategy_latest" to {
            assertEquals("combine", EventBus.flowMergeStrategy(true), "needLatest should use combine")
        })
        add("event_debounceWindowMs_reasonable" to {
            val r = EventBus.debounceWindowMs(100L)
            assertTrue(r > 1, "Debounce window should be reasonable fraction of interval")
        })
        add("event_retryDelayMs_backoff" to {
            val d1 = EventBus.retryDelayMs(1, 100L)
            val d2 = EventBus.retryDelayMs(2, 100L)
            assertTrue(d1 > 0 && d2 > d1, "Retry delay should use exponential backoff")
        })
        add("event_parallelismDegree_bounded" to {
            val r = EventBus.parallelismDegree(8, 100)
            assertTrue(r in 1..100, "Parallelism should be bounded, not MAX_VALUE")
        })
        add("event_stateFlowInitialValue_loading" to {
            assertEquals("LOADING", EventBus.stateFlowInitialValue(true), "Loading on start should be LOADING")
        })
        add("event_selectContextForWork_cpu" to {
            assertEquals("Default", EventBus.selectContextForWork(true), "CPU-intensive should use Default")
        })
        add("event_isChildJob_match" to {
            assertTrue(EventBus.isChildJob("parent-1", "parent-1"), "Should be child when parentIds match")
        })
        add("event_timeoutDefault_value" to {
            assertEquals("default", EventBus.timeoutDefault(true, "default"), "Timed out should return default")
        })
        add("event_formatCoroutineName_full" to {
            val r = EventBus.formatCoroutineName("auth", "validate")
            assertTrue(r.contains("auth") && r.contains("validate"), "Should include service and operation")
        })
        add("event_shouldYield_interval" to {
            assertTrue(EventBus.shouldYield(100, 100), "Should yield at interval boundary")
        })
        add("event_semaphorePermits_bounded" to {
            val r = EventBus.semaphorePermits(4, 8)
            assertTrue(r in 2..8, "Permits should be bounded by resource limit")
        })

        // =====================================================================
        // KotlinUtils (24 tests)
        // =====================================================================
        add("kotlin_valueClassEquals_boxed" to {
            assertTrue(KotlinUtils.valueClassEquals(1000L, 1000L, true), "Boxed Long should use == not ===")
        })
        add("kotlin_buildConfig_noLeak" to {
            val r = KotlinUtils.buildConfig("outer", "inner")
            assertFalse(r.containsKey("leak"), "Should not leak outer scope value")
        })
        add("kotlin_reifiedTypeCheck_actual" to {
            val (typeName, _) = KotlinUtils.reifiedTypeCheck("hello", "String")
            assertEquals("String", typeName, "Should return actual type name, not 'Any'")
        })
        add("kotlin_contractIsNotNull_true" to {
            assertTrue(KotlinUtils.contractIsNotNull("not null"), "Non-null value should return true")
        })
        add("kotlin_contextReceiverCalc_primary" to {
            assertEquals(15, KotlinUtils.contextReceiverCalc(3, 2, 5), "Should use primary: 3*5=15")
        })
        add("kotlin_buildImmutableList_order" to {
            val r = KotlinUtils.buildImmutableList("c", "a", "b")
            assertEquals(listOf("c", "a", "b"), r, "Should preserve insertion order, not sort")
        })
        add("kotlin_scopeFunctionApply_order" to {
            assertEquals("hello_suffix", KotlinUtils.scopeFunctionApply("hello", "_suffix"))
        })
        add("kotlin_operatorPlus_reverse" to {
            assertEquals(3, KotlinUtils.operatorPlus(5, 8, true), "Reverse: b-a = 8-5 = 3")
        })
        add("kotlin_roundDecimal_round" to {
            val r = KotlinUtils.roundDecimal(3.456, 2)
            assertEquals(3.46, r, 0.001, "Should round (not floor) to 2 decimal places")
        })
        add("kotlin_destructurePair_correct" to {
            val r = KotlinUtils.destructurePair("first", "second")
            assertEquals("first", r["first"], "first key should map to first param")
            assertEquals("second", r["second"], "second key should map to second param")
        })
        add("kotlin_inlineClassValidate_minLength" to {
            val (_, valid) = KotlinUtils.inlineClassValidate("ab", 5)
            assertFalse(valid, "String shorter than minLength should be invalid")
        })
        add("kotlin_samConversion_true" to {
            val (_, result) = KotlinUtils.samConversion("task", true)
            assertTrue(result, "Should return provided returnValue")
        })
        add("kotlin_companionFactory_type" to {
            val (type, _) = KotlinUtils.companionFactory("PREMIUM", 42)
            assertEquals("PREMIUM", type, "Should use provided type, not DEFAULT")
        })
        add("kotlin_sealedWhen_error" to {
            val r = KotlinUtils.sealedWhen("ERROR")
            assertNotEquals("Unknown state", r, "ERROR should be a handled state")
        })
        add("kotlin_propertyInitOrder_derived" to {
            val r = KotlinUtils.propertyInitOrder(10, 3)
            assertEquals(30, r, "derived = multiplier * baseValue = 3*10=30")
        })
        add("kotlin_reflectProperty_value" to {
            val props = mapOf("name" to "Alice" as Any)
            val (_, value) = KotlinUtils.reflectProperty(props, "name")
            assertEquals("Alice", value, "Should return actual property value from map")
        })
        add("kotlin_coroutineBuilderChoice_async" to {
            val (value, builder) = KotlinUtils.coroutineBuilderChoice(42, true)
            assertEquals(42, value, "Async should return value")
            assertEquals("async", builder, "Should select async builder")
        })
        add("kotlin_flowOperatorOrder_filterFirst" to {
            val r = KotlinUtils.flowOperatorOrder(listOf(1, 2, 3, 4, 5), 3)
            assertEquals(listOf(8, 10), r, "filter(>3) then map(*2): [4,5]->[8,10]")
        })
        add("kotlin_channelFanout_distribute" to {
            val r = KotlinUtils.channelFanout(listOf("a", "b", "c", "d"), 2)
            assertTrue(r[0]!!.size <= 3 && r[1]!!.size >= 1, "Should distribute items across consumers")
        })
        add("kotlin_delegatedPropertyProvider_primary" to {
            val providers = mapOf("primary" to "A", "fallback" to "B")
            assertEquals("A", KotlinUtils.delegatedPropertyProvider(providers, "primary", "fallback"))
        })
        add("kotlin_resultMonadUnwrap_error" to {
            val (value, isSuccess) = KotlinUtils.resultMonadUnwrap(false, "ok", "err")
            assertFalse(isSuccess, "isSuccess=false should propagate")
            assertEquals("err", value, "Should return error value when not success")
        })
        add("kotlin_multiplatformActual_jvm" to {
            assertEquals("jvm_val", KotlinUtils.multiplatformActual("JVM", "jvm_val", "js_val", "native_val"))
        })
        add("kotlin_extensionVsMember_ext" to {
            val r = KotlinUtils.extensionVsMember("hello", false)
            assertTrue(r.startsWith("extension:"), "useMember=false should use extension")
        })
        add("kotlin_suspendLambdaCapture_inner" to {
            val r = KotlinUtils.suspendLambdaCapture("outer", "inner", false)
            assertEquals("inner", r, "captureOuter=false should return innerValue")
        })

        // =====================================================================
        // Models (24 tests)
        // =====================================================================
        add("models_documentEquals_byteArray" to {
            val a = Models.Document("1", byteArrayOf(1, 2, 3), 1)
            val b = Models.Document("1", byteArrayOf(1, 2, 3), 1)
            assertTrue(Models.documentEquals(a, b), "Same content ByteArrays should be equal")
        })
        add("models_copyMetadata_deepCopy" to {
            val original = Models.Metadata(mutableListOf("a", "b"), "author")
            val copy = Models.copyMetadata(original)
            copy.tags.add("c")
            assertEquals(2, original.tags.size, "Deep copy should not share tags list")
        })
        add("models_describeShape_triangle" to {
            val shape = Models.Shape.Triangle(10.0, 5.0)
            val desc = Models.describeShape(shape)
            assertTrue(desc.contains("Triangle"), "Should describe Triangle, not 'Unknown'")
        })
        add("models_parsePriority_lowercase" to {
            assertEquals(Models.Priority.HIGH, Models.parsePriority("high"), "Should handle lowercase")
        })
        add("models_swapCoordinates_correct" to {
            val c = Models.Coordinate(1, 2, 3)
            val (x, y, z) = Models.swapCoordinates(c)
            assertEquals(1, x, "x should remain x")
            assertEquals(2, y, "y should remain y")
            assertEquals(3, z, "z should remain z")
        })
        add("models_safeToString_redact" to {
            val p = Models.UserProfile("Alice", "a@b.com", "secret123")
            val s = Models.safeToString(p)
            assertFalse(s.contains("secret123"), "Password hash should be redacted")
        })
        add("models_copyPerson_deepAddress" to {
            val addr = Models.Address("Main St", "NYC", "10001")
            val person = Models.Person("Alice", 30, addr)
            val copy = Models.copyPerson(person)
            assertFalse(person.address === copy.address, "Deep copy should create new Address instance")
        })
        add("models_compareUserIds_value" to {
            val uid = Models.UserId(42L)
            assertTrue(Models.compareUserIds(uid, 42L), "Should compare by value")
        })
        add("models_isSuccessResult_pending" to {
            assertFalse(Models.isSuccessResult(Models.Result.Pending("p1")), "Pending is not Success")
        })
        add("models_createDefaultProduct_stock" to {
            val p = Models.createDefaultProduct("SKU1", "Widget")
            assertEquals(0, p.stock, "Default stock should be 0, not -1")
        })
        add("models_updateProductPrice_returns" to {
            val p = Models.Product("SKU1", "Widget", 10.0, 5)
            val updated = Models.updateProductPrice(p, 20.0)
            assertEquals(20.0, updated.price, 0.01, "Should return product with new price")
        })
        add("models_sortProductsByPrice_field" to {
            val products = listOf(
                Models.Product("a", "A", 30.0, 1),
                Models.Product("b", "B", 10.0, 3),
                Models.Product("c", "C", 20.0, 2)
            )
            val sorted = Models.sortProductsByPrice(products)
            assertEquals(10.0, sorted[0].price, 0.01, "Should sort by price, not stock")
        })
        add("models_compareVersions_minor" to {
            val a = Models.VersionInfo(1, 3, 0)
            val b = Models.VersionInfo(1, 2, 5)
            assertTrue(Models.compareVersions(a, b) > 0, "1.3.0 > 1.2.5 (minor comparison)")
        })
        add("models_paginateList_page1" to {
            val items = (1..20).toList()
            val r = Models.paginateList(items, 1, 5)
            assertEquals(listOf(1, 2, 3, 4, 5), r.items, "Page 1 should be first 5 items")
        })
        add("models_groupEntitiesByType_field" to {
            val entities = listOf(
                Models.Entity("1", "Alice", "admin", true),
                Models.Entity("2", "Bob", "user", true),
                Models.Entity("3", "Carol", "admin", true)
            )
            val grouped = Models.groupEntitiesByType(entities)
            assertEquals(2, grouped["admin"]?.size, "Should group by type field, not name")
        })
        add("models_diffEntities_active" to {
            val old = Models.Entity("1", "A", "t", true)
            val new = Models.Entity("1", "A", "t", false)
            val changes = Models.diffEntities(old, new)
            assertTrue(changes.any { it.field == "active" }, "Should detect active field change")
        })
        add("models_createEntity_type" to {
            val e = Models.createEntity("1", "Alice", "admin")
            assertEquals("admin", e.type, "type should be category param, not name")
        })
        add("models_mergeEntities_name" to {
            val base = Models.Entity("1", "Old", "t1", true)
            val over = Models.Entity("1", "New", "t2", false)
            val merged = Models.mergeEntities(base, over)
            assertEquals("New", merged.name, "Name should come from override")
        })
        add("models_validateEntity_type" to {
            val e = Models.Entity("1", "Alice", "", true)
            val errors = Models.validateEntity(e)
            assertTrue(errors.any { it.contains("type") }, "Should validate type field")
        })
        add("models_entityToMap_emptyName" to {
            val e = Models.Entity("1", "", "admin", true)
            val map = Models.entityToMap(e)
            assertTrue(map.containsKey("name"), "Should always include name in map")
        })
        add("models_userIdToString_numeric" to {
            val uid = Models.UserId(42L)
            assertEquals("42", Models.userIdToString(uid), "Should return numeric string")
        })
        add("models_resultToCode_pending" to {
            assertEquals(202, Models.resultToCode(Models.Result.Pending("p1")), "Pending should return 202")
        })
        add("models_serializePriority_meaningful" to {
            val low = Models.serializePriority(Models.Priority.LOW)
            val high = Models.serializePriority(Models.Priority.HIGH)
            assertTrue(high > low, "HIGH should serialize to higher value than LOW")
            assertTrue(low >= 1, "Serialized priority should be >= 1, not 0-based ordinal")
        })
        add("models_buildEntity_unnamed" to {
            val e = Models.buildEntity("1", null, "admin")
            assertEquals("unnamed", e.name, "Null name should become 'unnamed'")
        })

        // =====================================================================
        // Logging (24 tests)
        // =====================================================================
        add("log_buildMdcContext_parent" to {
            val parent = mapOf("traceId" to "t1")
            val child = Logging.buildMdcContext(parent, "spanId", "s1")
            assertEquals("t1", child["traceId"], "Child MDC should include parent entries")
        })
        add("log_logLevelPriority_order" to {
            val warn = Logging.logLevelPriority("WARN")
            val error = Logging.logLevelPriority("ERROR")
            assertTrue(warn < error, "WARN should have lower priority than ERROR")
        })
        add("log_formatLogEntry_order" to {
            val r = Logging.formatLogEntry("2024-01-01", "INFO", "hello")
            assertTrue(r.startsWith("2024-01-01"), "Log entry should start with timestamp")
        })
        add("log_extractTraceId_fallback" to {
            val headers = mapOf("traceparent" to "trace123")
            val r = Logging.extractTraceId(headers)
            assertEquals("trace123", r, "Should fall back to 'traceparent' header")
        })
        add("log_shouldLog_gte" to {
            assertTrue(Logging.shouldLog("ERROR", "ERROR"), "Same level should log (>=)")
            assertTrue(Logging.shouldLog("ERROR", "WARN"), "Higher level should log")
        })
        add("log_buildMetricName_noRequestId" to {
            val r = Logging.buildMetricName("auth", "login", "req-123")
            assertFalse(r.contains("req-123"), "Metric name should not include requestId")
        })
        add("log_buildSpanContext_parent" to {
            val r = Logging.buildSpanContext("parent-1", "trace-1", "span-1")
            assertTrue(r.containsKey("parentSpanId"), "Should include parentSpanId")
        })
        add("log_classifyError_timeout" to {
            assertEquals(408, Logging.classifyError("timeout"), "timeout should be 408 Request Timeout")
        })
        add("log_latencyBucket_150ms" to {
            assertEquals("slow", Logging.latencyBucket(150L), "150ms should be 'slow' (boundary at 200)")
        })
        add("log_formatTraceHeader_prefix" to {
            val r = Logging.formatTraceHeader("trace1", "span1", true)
            assertTrue(r.startsWith("00-"), "W3C trace header should start with '00-'")
        })
        add("log_shouldSampleLog_mod100" to {
            // Correct: 1050 % 100 = 50 < 55 = true. Buggy: 1050 % 10000 = 1050 < 55 = false
            assertTrue(Logging.shouldSampleLog(1050, 55), "1050 % 100 = 50 < 55 should sample")
        })
        add("log_buildSpanName_noUser" to {
            val r = Logging.buildSpanName("GET", "/api/users", "user-123")
            assertFalse(r.contains("user-123"), "Span name should not include userId")
        })
        add("log_shouldAlert_threshold" to {
            assertFalse(Logging.shouldAlert(1, 60), "1 error should not trigger alert (threshold > 1)")
        })
        add("log_shouldRotateLog_default" to {
            assertFalse(Logging.shouldRotateLog(2048), "2KB should not trigger rotation (default 10MB)")
        })
        add("log_aggregateMetrics_window" to {
            val ts = listOf(1000L, 2000L, 3000L, 70000L, 71000L)
            val buckets = Logging.aggregateMetrics(ts, 60000L)
            assertEquals(2, buckets.size, "Should create 2 buckets with 60s window")
        })
        add("log_formatHealthCheck_noDb" to {
            val r = Logging.formatHealthCheck("auth", "UP", "jdbc:postgresql://secret:5432/db")
            assertFalse(r.contains("secret"), "Health check should not expose connection string")
        })
        add("log_buildAuditLog_failure" to {
            val r = Logging.buildAuditLog("delete", false, "user1")
            assertNotNull(r, "Should return audit entry even for failures")
        })
        add("log_buildLatencyBuckets_exponential" to {
            val buckets = Logging.buildLatencyBuckets()
            assertTrue(buckets.last() >= 1000.0, "Latency buckets should cover up to seconds range")
        })
        add("log_formatException_depth" to {
            val frames = (1..20).map { "com.example.Class.method$it(File.kt:$it)" }
            val r = Logging.formatException("NPE", "null", frames)
            assertTrue(r.split("\n").size >= 10, "Should include at least 10 stack frames")
        })
        add("log_formatRequestLog_status" to {
            val r = Logging.formatRequestLog("GET", "/api", 150L, 200)
            assertTrue(r.contains("200"), "Request log should include status code")
        })
        add("log_buildStructuredLog_keys" to {
            val r = Logging.buildStructuredLog("INFO", "hello", mapOf("k" to "v"))
            assertTrue(r.containsKey("level"), "Should use 'level' not 'lvl'")
            assertTrue(r.containsKey("message"), "Should use 'message' not 'msg'")
        })
        add("log_mergeLogContexts_append" to {
            val base = mapOf("tags" to listOf("a"))
            val overlay = mapOf("tags" to listOf("b"))
            val merged = Logging.mergeLogContexts(base, overlay)
            assertEquals(listOf("a", "b"), merged["tags"], "Should append lists, not replace")
        })
        add("log_validateMetricTag_chars" to {
            assertFalse(Logging.validateMetricTag("tag with spaces!"), "Tags with special chars should be invalid")
        })
        add("log_isValidTraceId_length32" to {
            assertTrue(Logging.isValidTraceId("0123456789abcdef0123456789abcdef"), "32-char hex should be valid")
            assertFalse(Logging.isValidTraceId("0123456789abcdef"), "16-char hex should be invalid")
        })

        // =====================================================================
        // JwtProvider / Security (24 tests)
        // =====================================================================
        add("sec_validateToken_structure" to {
            assertFalse(JwtProvider.validateToken("just-a-string"), "Token without dots should be invalid")
        })
        add("sec_validateToken_parts" to {
            assertFalse(JwtProvider.validateToken("header.payload"), "JWT needs 3 dot-separated parts")
        })
        add("sec_sanitizeSqlInput_semicolon" to {
            val r = JwtProvider.sanitizeSqlInput("'; DROP TABLE users;--")
            assertFalse(r.contains(";"), "Should sanitize semicolons in SQL input")
        })
        add("sec_validatePath_traversal" to {
            assertFalse(
                JwtProvider.validatePath("/app/data", "/app/data/../etc/passwd"),
                "Should reject path traversal"
            )
        })
        add("sec_isInternalUrl_privateRange" to {
            assertTrue(JwtProvider.isInternalUrl("http://10.0.0.1/api"), "10.x should be internal")
            assertTrue(JwtProvider.isInternalUrl("http://192.168.1.1/api"), "192.168.x should be internal")
        })
        add("sec_hashPassword_algorithm" to {
            val h = JwtProvider.hashPassword("pass", "salt")
            assertFalse(h.startsWith("md5:"), "Should not use MD5 for password hashing")
        })
        add("sec_generateSalt_random" to {
            val s1 = JwtProvider.generateSalt(16)
            val s2 = JwtProvider.generateSalt(16)
            assertNotEquals(s1, s2, "Salt should be random, not deterministic")
        })
        add("sec_validateEmailRegex_tld" to {
            assertFalse(JwtProvider.validateEmailRegex("user@localhost"), "Email should require domain with TLD")
        })
        add("sec_rateLimitCheck_calculation" to {
            assertTrue(JwtProvider.rateLimitCheck(50, 100, 60), "50 requests in 60s with limit 100/min should be allowed")
        })
        add("sec_tokenExpiry_noOffset" to {
            val r = JwtProvider.tokenExpiry(1000L, 3600L, 5)
            assertEquals(4600L, r, "Expiry should be issuedAt + ttl, UTC offset should not be added")
        })
        add("sec_encodeBase64Url_urlSafe" to {
            val r = JwtProvider.encodeBase64Url("???")
            assertFalse(r.contains("/"), "Should use URL-safe base64 (no / character)")
        })
        add("sec_validateRedirectUrl_traversal" to {
            assertFalse(
                JwtProvider.validateRedirectUrl("//../../../etc/passwd", "example.com"),
                "Relative path traversal should be rejected"
            )
        })
        add("sec_sanitizeHtml_allScripts" to {
            val r = JwtProvider.sanitizeHtml("<SCRIPT>alert(1)</SCRIPT>")
            assertFalse(r.contains("SCRIPT", ignoreCase = true), "Should handle case-insensitive script tags")
        })
        add("sec_parseJwtPayload_urlSafe" to {
            // Payload with chars that differ in base64 vs base64url encoding
            val payload = java.util.Base64.getUrlEncoder().withoutPadding().encodeToString(
                """{"url":"http://a?b/c??d"}""".toByteArray()
            )
            val jwt = "header.$payload.signature"
            val r = JwtProvider.parseJwtPayload(jwt)
            assertTrue(r.contains("http://"), "Should decode URL-safe base64 payload correctly")
        })
        add("sec_validateOrigin_exact" to {
            assertFalse(
                JwtProvider.validateOrigin("https://evil.com.attacker.com", "https://evil.com"),
                "Should use exact domain match, not prefix"
            )
        })
        add("sec_maskSensitiveData_last4" to {
            val r = JwtProvider.maskSensitiveData("1234567890")
            assertTrue(r.startsWith("******"), "Should mask all but last 4 characters")
        })
        add("sec_isSecureProtocol_https" to {
            assertFalse(JwtProvider.isSecureProtocol("http://example.com"), "HTTP should not be secure")
            assertTrue(JwtProvider.isSecureProtocol("https://example.com"), "HTTPS should be secure")
        })
        add("sec_validateCertExpiry_notExpired" to {
            assertTrue(
                JwtProvider.validateCertExpiry(1000L, 5000L, 3000L),
                "Cert with issued<now<expiry should be valid"
            )
        })
        add("sec_generateOtp_sixDigits" to {
            val otp = JwtProvider.generateOtp(42L)
            assertEquals(6, otp.length, "OTP should be 6 digits")
        })
        add("sec_validatePasswordStrength_complexity" to {
            assertFalse(
                JwtProvider.validatePasswordStrength("aaaaaaaa"),
                "8 repeated chars should not be strong enough"
            )
        })
        add("sec_escapeXml_ampersand" to {
            val r = JwtProvider.escapeXml("a & b < c")
            assertTrue(r.contains("&amp;"), "Should escape ampersand")
        })
        add("sec_validateContentType_exact" to {
            assertFalse(
                JwtProvider.validateContentType("application/javascript", listOf("application/json")),
                "Should match exact mime type, not just prefix"
            )
        })
        add("sec_buildAuthHeader_basic" to {
            val r = JwtProvider.buildAuthHeader("user", "pass", "https://api.example.com")
            assertTrue(r.startsWith("Basic "), "Should use Basic auth header format")
        })
        add("sec_validateRedirectUrl_domain" to {
            assertFalse(
                JwtProvider.validateRedirectUrl("https://evil.com/redirect?to=example.com", "example.com"),
                "Should validate actual domain, not just contains"
            )
        })

        // =====================================================================
        // SerializationUtils (24 tests)
        // =====================================================================
        add("ser_serializeInstant_timezone" to {
            val r = SerializationUtils.serializeInstant(1700000000000L, "UTC")
            assertTrue(r.contains("UTC") || r.contains("Z"), "Should include timezone info")
        })
        add("ser_ignoreUnknownKeys_true" to {
            assertTrue(SerializationUtils.ignoreUnknownKeys(), "Should ignore unknown keys for forward compat")
        })
        add("ser_shouldSerializeField_transient" to {
            assertFalse(
                SerializationUtils.shouldSerializeField("password", setOf("password", "secret")),
                "Transient fields should not be serialized"
            )
        })
        add("ser_polymorphicSerialize_type" to {
            val r = SerializationUtils.polymorphicSerialize("Circle", mapOf("radius" to "5"))
            assertTrue(r.contains("type") || r.contains("Circle"), "Should include type discriminator")
        })
        add("ser_serializeEnum_name" to {
            assertEquals("HIGH", SerializationUtils.serializeEnum(2, "HIGH"), "Should serialize by name, not ordinal")
        })
        add("ser_deserializeNullable_default" to {
            assertEquals("default", SerializationUtils.deserializeNullable(null, "default"))
        })
        add("ser_jsonPrettyPrint_noTrailingComma" to {
            val r = SerializationUtils.jsonPrettyPrint(listOf("a" to "1", "b" to "2"))
            val lastEntryLine = r.lines().dropLast(1).last().trim()
            assertFalse(lastEntryLine.endsWith(","), "Last entry should not have trailing comma")
        })
        add("ser_serializeMapKeys_ordered" to {
            val map = mapOf("cat" to "3", "ant" to "1", "bee" to "2")
            val r = SerializationUtils.serializeMapKeys(map)
            assertEquals("\"ant\":\"1\",\"bee\":\"2\",\"cat\":\"3\"", r, "Keys should be in sorted order")
        })
        add("ser_parseJsonArray_empty" to {
            val r = SerializationUtils.parseJsonArray("[]")
            assertNotNull(r, "Empty array should return empty list, not null")
            assertTrue(r!!.isEmpty(), "Empty array should parse to empty list")
        })
        add("ser_serializeBigDecimal_precision" to {
            val r = SerializationUtils.serializeBigDecimal("123456789.123456789")
            assertEquals("123456789.123456789", r, "Should preserve full decimal precision")
        })
        add("ser_deserializeDate_order" to {
            val (year, month, day) = SerializationUtils.deserializeDate("2024-03-15")
            assertEquals(2024, year, "First should be year")
            assertEquals(3, month, "Second should be month")
            assertEquals(15, day, "Third should be day")
        })
        add("ser_buildJsonObject_closing" to {
            val r = SerializationUtils.buildJsonObject(listOf("a" to "1"))
            assertTrue(r.endsWith("}"), "JSON object should have closing brace")
        })
        add("ser_flattenJson_listIndex" to {
            val data = mapOf("tags" to listOf("a", "b") as Any)
            val r = SerializationUtils.flattenJson("", data)
            assertTrue(r.size >= 2 || r.keys.any { it.contains("[") || it.contains("0") },
                "List items should be flattened with indices")
        })
        add("ser_validateJsonSchema_fields" to {
            assertFalse(
                SerializationUtils.validateJsonSchema("""{"a":"1"}""", listOf("a", "b")),
                "Missing required field 'b' should fail validation"
            )
        })
        add("ser_jsonPathQuery_full" to {
            val data = mapOf("a" to mapOf("b" to "value") as Any)
            val r = SerializationUtils.jsonPathQuery(data, "a.b")
            assertEquals("value", r, "Should traverse all path segments")
        })
        add("ser_compactJson_strings" to {
            val r = SerializationUtils.compactJson("""{ "msg" : "hello world" }""")
            assertTrue(r.contains("hello world"), "Should preserve spaces within strings")
        })
        add("ser_serializeCollection_single" to {
            val r = SerializationUtils.serializeCollection(listOf("item"))
            assertTrue(r.startsWith("["), "Single item should still be wrapped in array")
        })
        add("ser_dateFormatPattern_year" to {
            val r = SerializationUtils.dateFormatPattern()
            assertTrue(r.contains("yyyy"), "Year pattern should be lowercase 'yyyy'")
        })
        add("ser_mergeJsonObjects_deep" to {
            val base = mapOf("a" to mapOf("x" to 1) as Any)
            val over = mapOf("a" to mapOf("y" to 2) as Any)
            val r = SerializationUtils.mergeJsonObjects(base, over)
            val merged = r["a"] as? Map<*, *>
            assertTrue(merged != null && merged.containsKey("x") && merged.containsKey("y"),
                "Should deep merge nested maps")
        })
        add("ser_xmlToJson_attributes" to {
            val attrs = mapOf("id" to "1", "class" to "main")
            val r = SerializationUtils.xmlToJson("div", attrs, "content")
            assertTrue(r.containsKey("id") || r.containsKey("@id") || r.keys.size > 2,
                "Should include XML attributes in output")
        })
        add("ser_batchLogs_remainder" to {
            val logs = listOf("a", "b", "c", "d", "e")
            val batches = Logging.batchLogs(logs, 2)
            assertEquals(3, batches.size, "Should include remainder batch: [a,b],[c,d],[e]")
        })
        add("ser_escapeJsonString_backslash" to {
            val r = SerializationUtils.escapeJsonString("path\\to\\file")
            assertTrue(r.contains("\\\\"), "Should escape backslashes")
        })
        add("ser_csvToJson_quoted" to {
            val r = SerializationUtils.csvToJson(listOf("name", "desc"), "\"Alice\",\"A, B\"")
            assertEquals("A, B", r["desc"], "Should handle quoted fields with commas")
        })
        add("ser_buildDashboardQuery_ms" to {
            val r = Logging.buildDashboardQuery("cpu_usage", 1000L, 2000L)
            assertTrue(r.contains("1000000") && r.contains("2000000"), "Should convert seconds to milliseconds (*1000)")
        })
    }

    @TestFactory
    fun hyperMatrix(): List<DynamicTest> {
        val total = 12000
        return (0 until total).map { idx ->
            val (name, test) = testCases[idx % testCases.size]
            DynamicTest.dynamicTest("hyper_case_$idx") { test() }
        }
    }
}
