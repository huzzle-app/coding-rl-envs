# frozen_string_literal: true

require_relative '../test_helper'
require_relative '../../services/risk/service'

class RiskServiceTest < Minitest::Test
  def test_validate_command_auth_good_signature
    secret = 'test_secret'
    command = 'launch_probe'
    sig = Digest::SHA256.hexdigest("#{secret}:#{command}")
    result = OpalCommand::Services::Risk.validate_command_auth(command: command, signature: sig, secret: secret, required_role: 'operator', user_roles: %w[operator admin])
    assert result[:valid]
  end

  def test_check_path_traversal_detects_dotdot
    result = OpalCommand::Services::Risk.check_path_traversal('../../etc/passwd')
    refute result[:safe]
  end

  def test_rate_limit_check_allows_under_limit
    result = OpalCommand::Services::Risk.rate_limit_check(request_count: 5, limit: 10)
    assert result[:allowed]
    assert_equal 5, result[:remaining]
  end

  def test_compute_risk_score_range
    score = OpalCommand::Services::Risk.compute_risk_score(failed_attempts: 5, geo_anomaly: true, time_anomaly: false)
    assert_operator score, :>=, 0
    assert_operator score, :<=, 100
  end
end
