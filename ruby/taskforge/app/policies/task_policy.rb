# frozen_string_literal: true

class TaskPolicy < ApplicationPolicy
  def index?
    true
  end

  def show?
    user_in_project?
  end

  def create?
    user_in_project?
  end

  def update?
    user_in_project?
  end

  def destroy?
    project_admin?
  end

  class Scope < Scope
    def resolve
      scope.joins(project: :project_memberships)
           .where(project_memberships: { user_id: user.id })
    end
  end

  private

  def user_in_project?
    record.project.project_memberships.exists?(user: user)
  end

  def project_admin?
    record.project.project_memberships.exists?(user: user, role: %w[owner admin])
  end
end
