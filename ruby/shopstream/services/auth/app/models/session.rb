# frozen_string_literal: true

class Session < ApplicationRecord
  belongs_to :user

  validates :session_token, presence: true, uniqueness: true
  validates :expires_at, presence: true

  scope :active, -> { where('expires_at > ?', Time.current) }
  scope :expired, -> { where('expires_at <= ?', Time.current) }

  before_validation :generate_token, on: :create

  def expired?
    expires_at <= Time.current
  end

  def refresh!(duration = 24.hours)
    update!(
      expires_at: duration.from_now,
      last_accessed_at: Time.current
    )
  end

  def touch_access!
    update!(last_accessed_at: Time.current)
  end

  private

  def generate_token
    self.session_token ||= SecureRandom.urlsafe_base64(32)
  end
end
