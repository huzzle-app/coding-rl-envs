# frozen_string_literal: true

class ApiKey < ApplicationRecord
  belongs_to :user

  validates :name, presence: true, uniqueness: { scope: :user_id }
  validates :key_hash, presence: true, uniqueness: true
  validates :key_prefix, presence: true

  scope :active, -> { where(active: true).where('expires_at IS NULL OR expires_at > ?', Time.current) }

  serialize :permissions, coder: JSON

  def expired?
    expires_at.present? && expires_at <= Time.current
  end

  def has_permission?(permission)
    permissions.include?(permission.to_s) || permissions.include?('*')
  end

  def revoke!
    update!(active: false)
  end

  def touch_usage!
    update!(last_used_at: Time.current)
  end

  class << self
    def generate_for(user, name:, permissions: ['read'], expires_in: nil)
      raw_key = "sk_#{SecureRandom.hex(32)}"
      key_hash = Digest::SHA256.hexdigest(raw_key)

      api_key = create!(
        user: user,
        name: name,
        key_hash: key_hash,
        key_prefix: raw_key[0..7],
        permissions: permissions,
        expires_at: expires_in ? expires_in.from_now : nil
      )

      { api_key: api_key, raw_key: raw_key }
    end

    def find_by_raw_key(raw_key)
      return nil unless raw_key&.start_with?('sk_')
      key_hash = Digest::SHA256.hexdigest(raw_key)
      active.find_by(key_hash: key_hash)
    end
  end
end
