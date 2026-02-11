# frozen_string_literal: true

class ProjectMembership < ApplicationRecord
  belongs_to :project
  belongs_to :user

  validates :role, presence: true, inclusion: { in: %w[owner admin member viewer] }
  validates :project_id, uniqueness: { scope: :user_id }

  scope :owners, -> { where(role: 'owner') }
  scope :admins, -> { where(role: 'admin') }
  scope :members, -> { where(role: 'member') }
end
