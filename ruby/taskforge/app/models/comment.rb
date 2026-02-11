# frozen_string_literal: true

class Comment < ApplicationRecord
  belongs_to :user
  belongs_to :task
  has_many :mentions, dependent: :destroy

  validates :body, presence: true, length: { maximum: 5000 }

  after_create :notify_mentioned_users
  after_create :notify_task_watchers

  
  def parse_mentions
    
    mention_pattern = /@(\w+)/
    body.scan(mention_pattern).flatten.each do |username|
      user = User.find_by(username: username)
      mentions.create!(user: user) if user
    end
  end

  
  def self.recent_activity(project)
    
    joins(task: :project)
      .where(tasks: { project_id: project.id })
      .order(created_at: :desc)
  end

  private

  def notify_mentioned_users
    parse_mentions
    mentions.includes(:user).find_each do |mention|
      NotificationJob.perform_later(mention.user_id, :mentioned, id)
    end
  end

  def notify_task_watchers
    task.watchers.where.not(id: user_id).find_each do |watcher|
      NotificationJob.perform_later(watcher.id, :new_comment, id)
    end
  end
end
