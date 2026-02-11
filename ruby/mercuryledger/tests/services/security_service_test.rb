# frozen_string_literal: true

require_relative '../test_helper'
require_relative '../../services/security/service'

class SecurityServiceTest < Minitest::Test
  def test_validate_command_auth_valid
    cmd = 'deploy:v1'
    secret = 'supersecret'
    sig = Digest::SHA256.hexdigest("#{secret}:#{cmd}")
    assert MercuryLedger::Services::Security.validate_command_auth(cmd, sig, secret)
  end

  def test_check_path_traversal_detects_dotdot
    assert MercuryLedger::Services::Security.check_path_traversal('../../etc/passwd')
    refute MercuryLedger::Services::Security.check_path_traversal('safe/path/file.txt')
  end

  def test_compute_risk_score_range
    score = MercuryLedger::Services::Security.compute_risk_score(3, true, true)
    assert_operator score, :>, 0
    assert_operator score, :<=, 1.0
  end

  def test_validate_secret_strength_requires_complexity
    refute MercuryLedger::Services::Security.validate_secret_strength('short')
    assert MercuryLedger::Services::Security.validate_secret_strength('Abcdefg1')
  end
end
