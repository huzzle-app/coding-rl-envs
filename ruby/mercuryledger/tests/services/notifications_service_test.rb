# frozen_string_literal: true

require_relative '../test_helper'
require_relative '../../services/notifications/service'

class NotificationsServiceTest < Minitest::Test
  def test_plan_channels_includes_log_always
    channels = MercuryLedger::Services::Notifications.plan_channels(1)
    assert_includes channels, 'log'
  end

  def test_should_throttle_at_max
    assert MercuryLedger::Services::Notifications.should_throttle?(10, 10, 1)
    refute MercuryLedger::Services::Notifications.should_throttle?(5, 10, 1)
  end

  def test_format_notification_includes_prefix
    msg = MercuryLedger::Services::Notifications.format_notification('deploy', 5, 'rollback')
    assert_includes msg, '[CRITICAL]'
  end

  def test_escalation_delay_severity_5_is_zero
    assert_equal 0, MercuryLedger::Services::Notifications.escalation_delay(5)
    assert_operator MercuryLedger::Services::Notifications.escalation_delay(3), :>, 0
  end
end
