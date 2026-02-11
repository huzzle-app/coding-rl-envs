# frozen_string_literal: true

class Task < ApplicationRecord
  include AASM
  has_paper_trail

  # Associations
  belongs_to :project
  belongs_to :creator, class_name: 'User'
  belongs_to :assignee, class_name: 'User', optional: true
  belongs_to :milestone, optional: true
  belongs_to :parent, class_name: 'Task', optional: true
  has_many :subtasks, class_name: 'Task', foreign_key: :parent_id, dependent: :destroy
  has_many :comments, dependent: :destroy
  has_many :attachments, dependent: :destroy
  has_many :task_dependencies, dependent: :destroy
  has_many :dependencies, through: :task_dependencies, source: :dependency

  # Validations
  validates :title, presence: true, length: { maximum: 200 }
  validates :priority, inclusion: { in: %w[low medium high critical] }
  validates :estimated_hours, numericality: { greater_than_or_equal_to: 0 }, allow_nil: true

  # State machine
  aasm column: :status do
    state :todo, initial: true
    state :in_progress
    state :in_review
    state :completed
    state :cancelled

    event :start do
      transitions from: :todo, to: :in_progress
      after { log_activity(:started) }
    end

    event :submit_for_review do
      transitions from: :in_progress, to: :in_review
      after { notify_reviewers }
    end

    event :complete do
      transitions from: [:in_progress, :in_review], to: :completed
      after do
        log_activity(:completed)
        update_column(:completed_at, Time.current)
        
        complete_parent_if_all_subtasks_done
      end
    end

    event :reopen do
      transitions from: [:completed, :cancelled], to: :todo
      after { update_column(:completed_at, nil) }
    end

    event :cancel do
      transitions from: [:todo, :in_progress, :in_review], to: :cancelled
    end
  end

  # Scopes
  scope :completed, -> { where(status: 'completed') }
  scope :pending, -> { where.not(status: %w[completed cancelled]) }
  scope :overdue, -> { pending.where('due_date < ?', Date.current) }
  scope :due_soon, -> { pending.where(due_date: Date.current..3.days.from_now) }
  scope :unassigned, -> { where(assignee_id: nil) }
  scope :high_priority, -> { where(priority: %w[high critical]) }

  # Callbacks
  before_save :calculate_position
  after_save :update_project_stats
  after_destroy :update_project_stats

  
  def calculate_position
    return if position.present?

    # Not atomic - race condition when creating multiple tasks
    max_position = project.tasks.maximum(:position) || 0
    self.position = max_position + 1
  end

  def all_dependencies
    dependencies.map do |dep|
      {
        id: dep.id,
        title: dep.title,
        status: dep.status,
        assignee: dep.assignee&.name # N+1!
      }
    end
  end

  
  def add_tag(tag, options = [])
    
    options << :validated
    self.tags = (tags || []) + [tag]
    save
  end

  
  def assign_to(user)
    previous_assignee = assignee

    self.assignee = user
    save!

    
    NotificationService.notify(user, :task_assigned, self)
    NotificationService.notify(previous_assignee, :task_unassigned, self) if previous_assignee
  end

  def blocked?
    dependencies.pending.exists?
  end

  def can_start?
    !blocked? && todo?
  end

  private

  def complete_parent_if_all_subtasks_done
    return unless parent
    return if parent.subtasks.pending.exists?

    
    parent.complete! unless parent.completed?
  end

  def notify_reviewers
    project.members.where(role: 'reviewer').find_each do |reviewer|
      NotificationJob.perform_later(reviewer.id, :review_requested, self.id)
    end
  end

  def log_activity(action)
    ActivityLog.create!(
      user: assignee || creator,
      action: action,
      trackable: self,
      project: project
    )
  end

  def update_project_stats
    
    ProjectStatsJob.perform_later(project_id)
  end
end
