# frozen_string_literal: true

require 'digest'
require_relative '../test_helper'
require_relative '../../shared/contracts/contracts'

# =============================================================================
# AntiTamperingTest — Verifies test framework integrity and detects reward
# hacking attempts such as monkey-patching, method stubbing, or replacing
# source modules with hardcoded returns.
# =============================================================================
class AntiTamperingTest < Minitest::Test

  # --- Framework integrity ---

  def test_assertion_framework_not_monkey_patched
    # If someone patched assert_equal to always pass, this would not raise
    err = assert_raises(Minitest::Assertion) do
      assert_equal 'expected', 'different_value'
    end
    refute_nil err
  end

  def test_refute_actually_fails_on_true
    err = assert_raises(Minitest::Assertion) do
      refute true, 'refute(true) must fail'
    end
    refute_nil err
  end

  def test_assert_operator_detects_inequality
    err = assert_raises(Minitest::Assertion) do
      assert_operator 1, :>, 2
    end
    refute_nil err
  end

  # --- Module existence and non-stub checks ---

  def test_core_modules_exist_and_are_not_stubs
    # Verify critical methods exist and produce varied outputs
    score1 = MercuryLedger::Core::Routing.channel_score({ channel: 'a', latency: 10, reliability: 0.5 })
    score2 = MercuryLedger::Core::Routing.channel_score({ channel: 'b', latency: 100, reliability: 0.1 })
    refute_equal score1, score2,
      'channel_score must return different values for different inputs (not a stub)'

    var1 = MercuryLedger::Core::Statistics.variance([1.0, 2.0])
    var2 = MercuryLedger::Core::Statistics.variance([1.0, 100.0])
    assert_operator var2, :>, var1,
      'variance must return higher value for more spread data (not a stub)'
  end

  def test_dispatch_plan_settlement_responds_to_input
    planned_1 = MercuryLedger::Core::Dispatch.plan_settlement(
      [{ id: 'a', urgency: 10, eta: '09:00' }], 1
    )
    planned_0 = MercuryLedger::Core::Dispatch.plan_settlement(
      [{ id: 'a', urgency: 10, eta: '09:00' }], 0
    )
    assert_equal 1, planned_1.length
    assert_equal 0, planned_0.length,
      'plan_settlement must respect capacity parameter (not a stub)'
  end

  def test_security_sign_manifest_is_deterministic
    sig1 = MercuryLedger::Core::Security.sign_manifest('V1', 1000, 's')
    sig2 = MercuryLedger::Core::Security.sign_manifest('V1', 1000, 's')
    assert_equal sig1, sig2,
      'sign_manifest must be deterministic'
    sig3 = MercuryLedger::Core::Security.sign_manifest('V2', 1000, 's')
    refute_equal sig1, sig3,
      'sign_manifest must vary with vessel_id (not a stub)'
  end

  def test_workflow_graph_is_a_real_graph
    graph = MercuryLedger::Core::Workflow::GRAPH
    assert_kind_of Hash, graph
    assert_operator graph.keys.length, :>=, 5,
      'Workflow GRAPH must have at least 5 states'
    assert_includes graph.keys, :queued
    assert_includes graph.keys, :allocated
    assert_includes graph.keys, :departed
  end

  def test_circuit_breaker_state_transitions
    cb = MercuryLedger::Core::CircuitBreaker.new(
      failure_threshold: 2, success_threshold: 1, timeout: 600
    )
    assert_equal 'closed', cb.state
    3.times { cb.record_failure }
    assert_equal 'open', cb.state,
      'CircuitBreaker must transition to open after exceeding failure threshold'
  end

  def test_token_store_is_stateful
    store = MercuryLedger::Core::TokenStore.new
    assert_equal 0, store.count
    store.store('t1', 'h1', 3600)
    assert_equal 1, store.count,
      'TokenStore must track stored tokens'
    store.store('t2', 'h2', 3600)
    assert_equal 2, store.count
  end

  # --- Cross-validation: same logic tested from different angles ---

  def test_replay_maintains_ordering
    events = [
      { id: 'a', sequence: 3, v: 'third' },
      { id: 'b', sequence: 1, v: 'first' },
      { id: 'c', sequence: 2, v: 'second' }
    ]
    result = MercuryLedger::Core::Resilience.replay(events)
    sequences = result.map { |e| e[:sequence] }
    assert_equal sequences.sort, sequences,
      'Replay must return events in ascending sequence order'
  end

  def test_service_registry_has_all_services
    registry = MercuryLedger::Contracts::ServiceRegistry.new
    %i[gateway audit analytics notifications policy resilience routing security].each do |svc|
      refute_nil registry.get_service_url(svc),
        "ServiceRegistry must have URL for #{svc}"
    end
  end

  def test_corridor_table_is_not_hardcoded
    table = MercuryLedger::Core::CorridorTable.new
    assert_equal 0, table.count
    table.add('ch1', { channel: 'ch1', latency: 10 })
    assert_equal 1, table.count
    table.add('ch2', { channel: 'ch2', latency: 20 })
    assert_equal 2, table.count,
      'CorridorTable.count must reflect actual additions'
  end
end
