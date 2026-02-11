# frozen_string_literal: true

require_relative '../test_helper'
require_relative '../../services/notifications/service'

class NotificationsServiceTest < Minitest::Test
  def test_notification_planner_plan_and_pending
    planner = OpalCommand::Services::Notifications::NotificationPlanner.new
    planner.plan(operator_id: 'op1', severity: 3, message: 'test alert')
    assert_equal 1, planner.size
    assert_equal 1, planner.pending.length
  end

  def test_should_throttle_at_limit
    assert OpalCommand::Services::Notifications.should_throttle(recent_count: 10, max_per_window: 10)
    refute OpalCommand::Services::Notifications.should_throttle(recent_count: 5, max_per_window: 10)
  end

  def test_format_notification_includes_channels
    notif = OpalCommand::Services::Notifications.format_notification(operator_id: 'op1', severity: 4, message: 'urgent')
    assert_includes notif[:channels], 'pager'
    assert_equal 4, notif[:severity]
  end

  def test_notification_summary_groups_by_severity
    batch = [
      { severity: 1, message: 'a' },
      { severity: 1, message: 'b' },
      { severity: 3, message: 'c' }
    ]
    summary = OpalCommand::Services::Notifications.notification_summary(batch)
    assert_equal 3, summary[:total]
    assert_equal 2, summary[:by_severity][1]
  end
end
