cmake_minimum_required(VERSION 3.20)
project(signalstream LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ---------------------------------------------------------------------------
# Sanitizer options
# ---------------------------------------------------------------------------
option(ENABLE_ASAN  "Enable AddressSanitizer"           OFF)
option(ENABLE_UBSAN "Enable UndefinedBehaviorSanitizer"  OFF)
option(ENABLE_TSAN  "Enable ThreadSanitizer"             OFF)
option(ENABLE_SANITIZERS "Enable ASan + UBSan (convenience)" OFF)

if(ENABLE_SANITIZERS)
  set(ENABLE_ASAN  ON)
  set(ENABLE_UBSAN ON)
endif()

if(ENABLE_ASAN AND ENABLE_TSAN)
  message(FATAL_ERROR "ASan and TSan cannot be used together")
endif()

set(_SAN_FLAGS "")
if(ENABLE_ASAN)
  list(APPEND _SAN_FLAGS "-fsanitize=address")
endif()
if(ENABLE_UBSAN)
  list(APPEND _SAN_FLAGS "-fsanitize=undefined")
endif()
if(ENABLE_TSAN)
  list(APPEND _SAN_FLAGS "-fsanitize=thread")
endif()

if(_SAN_FLAGS)
  add_compile_options(${_SAN_FLAGS} -fno-omit-frame-pointer)
  add_link_options(${_SAN_FLAGS})
endif()

# ---------------------------------------------------------------------------
# Library & test executable
# ---------------------------------------------------------------------------
add_library(signalstream
  src/config.cpp
  src/ingest.cpp
  src/router.cpp
  src/aggregate.cpp
  src/storage.cpp
  src/query.cpp
  src/alert.cpp
  src/gateway.cpp
  src/security.cpp
  src/telemetry.cpp
  src/concurrency.cpp
  src/events.cpp
  src/transform.cpp
  src/memory.cpp
)

target_include_directories(signalstream PUBLIC include)

add_executable(signalstream_tests tests/test_main.cpp)
target_link_libraries(signalstream_tests PRIVATE signalstream)

enable_testing()

# ---------------------------------------------------------------------------
# Helper: add_signalstream_test — wraps add_test with sanitizer env vars,
# category labels, and optional timeout.
#   Usage: add_signalstream_test(<name> LABEL <label> [TIMEOUT <seconds>])
# ---------------------------------------------------------------------------
function(add_signalstream_test NAME)
  cmake_parse_arguments(PARSE_ARGV 1 ARG "" "LABEL;TIMEOUT" "")
  add_test(NAME ${NAME} COMMAND signalstream_tests ${NAME})

  # Sanitizer environment variables
  set(_ENV "")
  if(ENABLE_ASAN)
    list(APPEND _ENV "ASAN_OPTIONS=detect_leaks=1:halt_on_error=1:abort_on_error=1")
  endif()
  if(ENABLE_UBSAN)
    list(APPEND _ENV "UBSAN_OPTIONS=print_stacktrace=1:halt_on_error=1")
  endif()
  if(ENABLE_TSAN)
    list(APPEND _ENV "TSAN_OPTIONS=halt_on_error=1:second_deadlock_stack=1")
  endif()
  if(_ENV)
    set_tests_properties(${NAME} PROPERTIES ENVIRONMENT "${_ENV}")
  endif()

  # Category label (for ctest -L <label>)
  if(ARG_LABEL)
    set_tests_properties(${NAME} PROPERTIES LABELS "${ARG_LABEL}")
  endif()

  # Per-test timeout (for tests that spawn threads / could hang)
  if(ARG_TIMEOUT)
    set_tests_properties(${NAME} PROPERTIES TIMEOUT ${ARG_TIMEOUT})
  endif()
endfunction()

# ---------------------------------------------------------------------------
# Setup/Configuration tests (L bugs)
# ---------------------------------------------------------------------------
add_signalstream_test(setup_static_init                LABEL setup)
add_signalstream_test(setup_service_registry            LABEL setup)
add_signalstream_test(setup_db_config_validation        LABEL setup)
add_signalstream_test(setup_health_check                LABEL setup)
add_signalstream_test(setup_config_singleton            LABEL setup)

# ---------------------------------------------------------------------------
# Concurrency tests (A bugs)
# ---------------------------------------------------------------------------
add_signalstream_test(concurrency_aba_problem           LABEL concurrency)
add_signalstream_test(concurrency_memory_ordering       LABEL concurrency)
add_signalstream_test(concurrency_false_sharing         LABEL concurrency)
add_signalstream_test(concurrency_data_race             LABEL concurrency TIMEOUT 5)
add_signalstream_test(concurrency_spurious_wakeup       LABEL concurrency TIMEOUT 5)
add_signalstream_test(concurrency_reader_starvation     LABEL concurrency TIMEOUT 5)
add_signalstream_test(concurrency_tls_destruction       LABEL concurrency TIMEOUT 5)
add_signalstream_test(concurrency_mutex_exception       LABEL concurrency TIMEOUT 5)
add_signalstream_test(concurrency_writer_starvation     LABEL concurrency TIMEOUT 5)
add_signalstream_test(concurrency_spinlock_backoff      LABEL concurrency TIMEOUT 5)
add_signalstream_test(concurrency_thread_pool           LABEL concurrency)
add_signalstream_test(concurrency_atomic_counter        LABEL concurrency)

# ---------------------------------------------------------------------------
# Memory tests (B bugs)
# ---------------------------------------------------------------------------
add_signalstream_test(memory_alignment                  LABEL memory)
add_signalstream_test(memory_use_after_free             LABEL memory)
add_signalstream_test(memory_string_view_dangling       LABEL memory)
add_signalstream_test(memory_iterator_invalidation      LABEL memory)
add_signalstream_test(memory_array_delete               LABEL memory)
add_signalstream_test(memory_padding_memcmp             LABEL memory)
add_signalstream_test(memory_buffer_management          LABEL memory)

# ---------------------------------------------------------------------------
# Smart pointer tests (C bugs)
# ---------------------------------------------------------------------------
add_signalstream_test(smartptr_cycle                    LABEL smartptr)
add_signalstream_test(smartptr_unique_copy              LABEL smartptr)
add_signalstream_test(smartptr_shared_from_this         LABEL smartptr)
add_signalstream_test(smartptr_weak_expired             LABEL smartptr)
add_signalstream_test(smartptr_destructor_throw         LABEL smartptr)
add_signalstream_test(smartptr_ownership                LABEL smartptr)

# ---------------------------------------------------------------------------
# Undefined behavior tests (D bugs)
# ---------------------------------------------------------------------------
add_signalstream_test(ub_signed_overflow                LABEL ub)
add_signalstream_test(ub_strict_aliasing                LABEL ub)
add_signalstream_test(ub_uninitialized                  LABEL ub)
add_signalstream_test(ub_sequence_point                 LABEL ub)
add_signalstream_test(ub_dangling_reference             LABEL ub)
add_signalstream_test(ub_null_dereference               LABEL ub)

# ---------------------------------------------------------------------------
# Event/Distributed tests (E bugs)
# ---------------------------------------------------------------------------
add_signalstream_test(event_ordering                    LABEL event)
add_signalstream_test(event_idempotency                 LABEL event)
add_signalstream_test(event_subscription_leak           LABEL event)
add_signalstream_test(event_snapshot_atomic             LABEL event)
add_signalstream_test(event_compression_buffer          LABEL event)
add_signalstream_test(event_dead_letter                 LABEL event)
add_signalstream_test(event_publish_consume             LABEL event)

# ---------------------------------------------------------------------------
# Numerical tests (F bugs)
# ---------------------------------------------------------------------------
add_signalstream_test(numerical_float_equality          LABEL numerical)
add_signalstream_test(numerical_integer_overflow        LABEL numerical)
add_signalstream_test(numerical_time_window             LABEL numerical)
add_signalstream_test(numerical_nan_handling            LABEL numerical)
add_signalstream_test(numerical_accumulate_type         LABEL numerical)
add_signalstream_test(numerical_division_zero           LABEL numerical)
add_signalstream_test(numerical_precision_loss          LABEL numerical)
add_signalstream_test(numerical_percentile              LABEL numerical)
add_signalstream_test(numerical_aggregates              LABEL numerical)

# ---------------------------------------------------------------------------
# Database/Query tests (G bugs)
# ---------------------------------------------------------------------------
add_signalstream_test(query_connection_leak             LABEL query)
add_signalstream_test(query_sql_injection               LABEL query)
add_signalstream_test(query_statement_leak              LABEL query)
add_signalstream_test(query_iterator_invalidation       LABEL query)
add_signalstream_test(query_n_plus_one                  LABEL query)
add_signalstream_test(query_connection_string           LABEL query)
add_signalstream_test(query_build                       LABEL query)
add_signalstream_test(query_range                       LABEL query)

# ---------------------------------------------------------------------------
# Distributed state tests (H bugs)
# ---------------------------------------------------------------------------
add_signalstream_test(distributed_check_then_act        LABEL distributed TIMEOUT 5)
add_signalstream_test(distributed_lock_lease            LABEL distributed)
add_signalstream_test(distributed_circuit_breaker       LABEL distributed)
add_signalstream_test(distributed_retry_backoff         LABEL distributed)
add_signalstream_test(distributed_split_brain           LABEL distributed)
add_signalstream_test(distributed_leader_election       LABEL distributed)

# ---------------------------------------------------------------------------
# Security tests (I bugs)
# ---------------------------------------------------------------------------
add_signalstream_test(security_buffer_overflow          LABEL security)
add_signalstream_test(security_path_traversal           LABEL security)
add_signalstream_test(security_rate_limit_bypass        LABEL security)
add_signalstream_test(security_jwt_none                 LABEL security)
add_signalstream_test(security_timing_attack            LABEL security)
add_signalstream_test(security_weak_rng                 LABEL security)
add_signalstream_test(security_cors_wildcard            LABEL security)
add_signalstream_test(security_password_hash            LABEL security)
add_signalstream_test(security_session_validation       LABEL security)

# ---------------------------------------------------------------------------
# Observability tests (J bugs)
# ---------------------------------------------------------------------------
add_signalstream_test(observability_trace_context       LABEL observability)
add_signalstream_test(observability_metric_cardinality  LABEL observability)
add_signalstream_test(observability_metric_registration LABEL observability)
add_signalstream_test(observability_log_level           LABEL observability)
add_signalstream_test(observability_log_injection       LABEL observability)
add_signalstream_test(observability_telemetry           LABEL observability)

# ---------------------------------------------------------------------------
# Template/Modern C++ tests (K bugs)
# ---------------------------------------------------------------------------
add_signalstream_test(template_sfinae                   LABEL template)
add_signalstream_test(template_adl                      LABEL template)
add_signalstream_test(template_constexpr                LABEL template)
add_signalstream_test(template_perfect_forward          LABEL template)
add_signalstream_test(template_variant_visit            LABEL template)
add_signalstream_test(template_ctad                     LABEL template)
add_signalstream_test(template_concept                  LABEL template)
add_signalstream_test(template_requires_clause          LABEL template)

# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------
add_signalstream_test(integration_data_pipeline         LABEL integration)
add_signalstream_test(integration_alert_workflow        LABEL integration)
add_signalstream_test(integration_auth_flow             LABEL integration)
add_signalstream_test(integration_routing               LABEL integration)
add_signalstream_test(integration_storage               LABEL integration)

# ---------------------------------------------------------------------------
# Object pool tests
# ---------------------------------------------------------------------------
add_signalstream_test(pool_acquire_release              LABEL pool)
add_signalstream_test(pool_metrics                      LABEL pool)
add_signalstream_test(pool_capacity                     LABEL pool)

# ---------------------------------------------------------------------------
# Latent bugs
# ---------------------------------------------------------------------------
add_signalstream_test(latent_negative_aggregate         LABEL latent)
add_signalstream_test(latent_batch_reorder              LABEL latent)

# ---------------------------------------------------------------------------
# Domain logic bugs
# ---------------------------------------------------------------------------
add_signalstream_test(domain_percentile_exact           LABEL domain)
add_signalstream_test(domain_nan_alert_suppression      LABEL domain)

# ---------------------------------------------------------------------------
# Multi-step bugs
# ---------------------------------------------------------------------------
add_signalstream_test(multistep_ratelimit_boundary      LABEL multistep)
add_signalstream_test(multistep_ratelimit_window        LABEL multistep)

# ---------------------------------------------------------------------------
# State machine bugs
# ---------------------------------------------------------------------------
add_signalstream_test(statemachine_healthcheck_degraded  LABEL statemachine)
add_signalstream_test(statemachine_circuit_reverse       LABEL statemachine)

# ---------------------------------------------------------------------------
# Concurrency bugs (continued)
# ---------------------------------------------------------------------------
add_signalstream_test(concurrency_event_fifo_order      LABEL concurrency)
add_signalstream_test(concurrency_span_collision        LABEL concurrency)
add_signalstream_test(concurrency_rwlock_underflow      LABEL concurrency)
add_signalstream_test(concurrency_trace_corruption      LABEL concurrency)

# ---------------------------------------------------------------------------
# Integration bugs
# ---------------------------------------------------------------------------
add_signalstream_test(integration_inactive_route        LABEL integration)
add_signalstream_test(integration_pipeline_negative     LABEL integration)

# ---------------------------------------------------------------------------
# Complex bugs
# ---------------------------------------------------------------------------
add_signalstream_test(domain_ema_decay                  LABEL complex)
add_signalstream_test(statemachine_circuit_probe_limit  LABEL complex)
add_signalstream_test(multistep_event_dedup_collision   LABEL complex)
add_signalstream_test(integration_token_refresh_collision LABEL complex)
add_signalstream_test(concurrency_pool_shutdown_drain   LABEL complex)
add_signalstream_test(latent_sample_variance            LABEL complex)

# ---------------------------------------------------------------------------
# Hyper-matrix chunks (127 entries x 100 scenarios each = 12678 total)
# Replaces single hyper_matrix entry for granular CTest signal
# ---------------------------------------------------------------------------
set(_HYPER_TOTAL 12678)
set(_HYPER_CHUNK 100)
set(_HYPER_START 0)
while(_HYPER_START LESS _HYPER_TOTAL)
  if(_HYPER_START LESS 10)
    set(_CHUNK_LABEL "hyper_chunk_000${_HYPER_START}")
  elseif(_HYPER_START LESS 100)
    set(_CHUNK_LABEL "hyper_chunk_00${_HYPER_START}")
  elseif(_HYPER_START LESS 1000)
    set(_CHUNK_LABEL "hyper_chunk_0${_HYPER_START}")
  else()
    set(_CHUNK_LABEL "hyper_chunk_${_HYPER_START}")
  endif()
  add_signalstream_test(${_CHUNK_LABEL} LABEL hyper TIMEOUT 30)
  math(EXPR _HYPER_START "${_HYPER_START} + ${_HYPER_CHUNK}")
endwhile()
