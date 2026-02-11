# frozen_string_literal: true

class ProjectPolicy < ApplicationPolicy
  def index?
    true
  end

  def show?
    user_in_organization? || record.visibility == 'public'
  end

  def create?
    user_in_organization?
  end

  def update?
    project_admin?
  end

  def destroy?
    project_owner?
  end

  class Scope < Scope
    def resolve
      scope.joins(organization: :organization_memberships)
           .where(organization_memberships: { user_id: user.id })
    end
  end

  private

  def user_in_organization?
    record.organization.organization_memberships.exists?(user: user)
  end

  def project_admin?
    record.project_memberships.exists?(user: user, role: %w[owner admin])
  end

  def project_owner?
    record.project_memberships.exists?(user: user, role: 'owner')
  end
end
