# frozen_string_literal: true

class Project < ApplicationRecord
  include AASM
  has_paper_trail

  # Associations
  belongs_to :organization
  belongs_to :creator, class_name: 'User'
  has_many :tasks, dependent: :destroy
  has_many :milestones, dependent: :destroy
  has_many :project_memberships, dependent: :destroy
  has_many :members, through: :project_memberships, source: :user

  # Validations
  validates :name, presence: true, length: { maximum: 100 }
  validates :organization, presence: true

  # Friendly ID
  extend FriendlyId
  friendly_id :name, use: [:slugged, :scoped], scope: :organization

  # State machine
  aasm column: :status do
    state :planning, initial: true
    state :active
    state :on_hold
    state :completed
    state :archived

    event :start do
      transitions from: :planning, to: :active
      after { notify_members(:project_started) }
    end

    event :pause do
      transitions from: :active, to: :on_hold
    end

    event :resume do
      transitions from: :on_hold, to: :active
    end

    event :complete do
      transitions from: :active, to: :completed
      after { notify_members(:project_completed) }
    end

    event :archive do
      transitions from: [:completed, :on_hold], to: :archived
    end
  end

  # Scopes
  scope :active, -> { where(status: 'active') }
  scope :visible_to, ->(user) {
    joins(:project_memberships).where(project_memberships: { user_id: user.id })
  }

  
  def completion_percentage
    return 0 if tasks.count.zero?

    
    completed = tasks.completed.count
    total = tasks.count
    ((completed.to_f / total) * 100).round(2)
  end

  
  def stats
    @stats ||= begin
      # This is not thread-safe in multi-threaded servers
      {
        total_tasks: tasks.count,
        completed_tasks: tasks.completed.count,
        overdue_tasks: tasks.overdue.count,
        members: members.count
      }
    end
  end

  
  def cleanup_old_tasks!
    tasks.where('created_at < ?', 1.year.ago).each do |task|
      
      task.destroy if task.completed?
    end
  end

  
  def tasks_by_status
    # This query is slow without proper index
    tasks.group(:status).count
  end

  private

  def notify_members(event)
    members.find_each do |member|
      NotificationJob.perform_later(member.id, event, self.id)
    end
  end
end
