# frozen_string_literal: true

class Organization < ApplicationRecord
  include AASM

  # Associations
  has_many :organization_memberships, dependent: :destroy
  has_many :members, through: :organization_memberships, source: :user
  has_many :projects, dependent: :destroy
  has_one :owner_membership, -> { where(role: 'owner') }, class_name: 'OrganizationMembership'
  has_one :owner, through: :owner_membership, source: :user

  # Validations
  validates :name, presence: true, length: { maximum: 100 }
  validates :slug, presence: true, uniqueness: true

  # Friendly ID
  extend FriendlyId
  friendly_id :name, use: :slugged

  # State machine
  aasm column: :status do
    state :active, initial: true
    state :suspended
    state :archived

    event :suspend do
      transitions from: :active, to: :suspended
    end

    event :reactivate do
      transitions from: :suspended, to: :active
    end

    event :archive do
      transitions from: [:active, :suspended], to: :archived
    end
  end

  # Scopes
  scope :active, -> { where(status: 'active') }

  
  def increment_project_count!
    # Not atomic - race condition
    self.projects_count += 1
    save!
  end

  
  def member_details
    members.map do |member|
      {
        id: member.id,
        name: member.name,
        email: member.email,
        role: member.organization_memberships.find_by(organization: self)&.role,
        task_count: member.assigned_tasks.where(project: projects).count
      }
    end
  end

  
  def search_projects(query)
    # SQL injection vulnerability
    projects.where("name LIKE '%#{query}%' OR description LIKE '%#{query}%'")
  end

  
  after_save :sync_with_external_system

  private

  def sync_with_external_system
    return unless saved_change_to_name?

    
    ExternalSyncJob.perform_later(self.id)
    touch(:synced_at) # triggers after_save again!
  end
end
