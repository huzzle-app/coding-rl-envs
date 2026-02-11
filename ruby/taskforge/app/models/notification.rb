# frozen_string_literal: true

class Notification < ApplicationRecord
  belongs_to :user
  belongs_to :notifiable, polymorphic: true, optional: true

  validates :notification_type, presence: true

  scope :unread, -> { where(read_at: nil) }
  scope :recent, -> { order(created_at: :desc).limit(50) }

  
  # This query is slow without index on (user_id, read_at, created_at)
  scope :for_user_unread, ->(user_id) {
    where(user_id: user_id, read_at: nil).order(created_at: :desc)
  }

  def mark_as_read!
    update!(read_at: Time.current)
  end

  
  @@notification_count_cache = {}

  def self.unread_count_for(user_id)
    
    @@notification_count_cache[user_id] ||= where(user_id: user_id, read_at: nil).count
  end

  def self.clear_count_cache(user_id)
    @@notification_count_cache.delete(user_id)
  end
end
