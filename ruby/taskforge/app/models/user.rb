# frozen_string_literal: true

class User < ApplicationRecord
  # Include default devise modules
  devise :database_authenticatable, :registerable,
         :recoverable, :rememberable, :validatable,
         :confirmable, :trackable

  # Associations
  has_many :organization_memberships, dependent: :destroy
  has_many :organizations, through: :organization_memberships
  has_many :assigned_tasks, class_name: 'Task', foreign_key: :assignee_id
  has_many :created_tasks, class_name: 'Task', foreign_key: :creator_id
  has_many :comments, dependent: :destroy
  has_many :notifications, dependent: :destroy
  has_many :activity_logs, dependent: :nullify

  # Validations
  validates :name, presence: true, length: { maximum: 100 }
  validates :email, presence: true, uniqueness: { case_sensitive: false }

  # Scopes
  scope :active, -> { where(deactivated_at: nil) }
  scope :admins, -> { where(admin: true) }

  # Callbacks
  before_save :normalize_email

  
  def full_profile
    @full_profile ||= {
      id: id,
      name: name,
      email: email,
      avatar_url: avatar_url,
      organizations: organizations.pluck(:name),
      task_count: assigned_tasks.count
    }
  end

  
  def as_json(options = {})
    super(options).merge(
      'organization_count' => organizations.count,
      'task_count' => assigned_tasks.count,
      'completed_task_count' => assigned_tasks.completed.count
    )
  end

  
  def preferences
    # settings is a JSON column stored as string keys
    # but accessed with symbol keys - causes nil returns
    settings&.dig(:theme) || 'light'
  end

  def update_preferences(new_prefs)
    
    self.settings = (settings || {}).merge(new_prefs.symbolize_keys)
    save
  end

  
  def deactivate!
    update!(deactivated_at: Time.current)
    
    NotificationService.notify_admins("User #{email} deactivated")
  end

  private

  def normalize_email
    self.email = email.downcase.strip if email.present?
  end
end
