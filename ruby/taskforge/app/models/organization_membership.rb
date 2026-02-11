# frozen_string_literal: true

class OrganizationMembership < ApplicationRecord
  belongs_to :organization
  belongs_to :user

  validates :role, presence: true, inclusion: { in: %w[owner admin member] }
  validates :organization_id, uniqueness: { scope: :user_id }

  scope :owners, -> { where(role: 'owner') }
  scope :admins, -> { where(role: 'admin') }
  scope :members, -> { where(role: 'member') }
end
