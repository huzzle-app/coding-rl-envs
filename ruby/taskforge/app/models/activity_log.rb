# frozen_string_literal: true

class ActivityLog < ApplicationRecord
  belongs_to :user, optional: true
  belongs_to :trackable, polymorphic: true, optional: true
  belongs_to :project, optional: true

  validates :action, presence: true

  scope :recent, -> { order(created_at: :desc) }
  scope :for_project, ->(project) { where(project: project) }
  scope :by_user, ->(user) { where(user: user) }

  def self.log(action:, user: nil, trackable: nil, project: nil, changes_data: {})
    create!(
      action: action,
      user: user,
      trackable: trackable,
      project: project,
      changes_data: changes_data
    )
  end
end
