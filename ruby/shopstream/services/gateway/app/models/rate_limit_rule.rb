# frozen_string_literal: true

class RateLimitRule < ApplicationRecord
  validates :name, presence: true, uniqueness: true
  validates :key_type, presence: true
  validates :limit, presence: true, numericality: { greater_than: 0 }
  validates :window_seconds, presence: true, numericality: { greater_than: 0 }

  scope :enabled, -> { where(enabled: true) }
  scope :by_key_type, ->(type) { where(key_type: type) }

  def enabled?
    enabled
  end

  def reject_action?
    action == 'reject'
  end

  def throttle_action?
    action == 'throttle'
  end

  def to_config
    {
      limit: limit,
      window: window_seconds,
      action: action
    }
  end

  class << self
    def find_for_key_type(key_type)
      enabled.by_key_type(key_type).first
    end
  end
end
