# frozen_string_literal: true

class User < ApplicationRecord
  has_secure_password validations: false

  has_many :sessions, dependent: :destroy
  has_many :api_keys, dependent: :destroy

  validates :email, presence: true, uniqueness: true, format: { with: URI::MailTo::EMAIL_REGEXP }
  validates :full_name, presence: true
  validates :password_digest, presence: true, if: :password_required?

  scope :active, -> { where(active: true) }
  scope :locked, -> { where('locked_until > ?', Time.current) }

  def locked?
    locked_until.present? && locked_until > Time.current
  end

  def lock!(duration = 1.hour)
    update!(locked_until: duration.from_now)
  end

  def unlock!
    update!(locked_until: nil, failed_login_attempts: 0)
  end

  def record_failed_login!
    increment!(:failed_login_attempts)
    lock! if failed_login_attempts >= 5
  end

  def record_successful_login!
    update!(
      failed_login_attempts: 0,
      locked_until: nil,
      last_login_at: Time.current
    )
  end

  private

  def password_required?
    password_digest.blank?
  end
end
