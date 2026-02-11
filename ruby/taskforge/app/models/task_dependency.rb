# frozen_string_literal: true

class TaskDependency < ApplicationRecord
  belongs_to :task
  belongs_to :dependency, class_name: 'Task'

  validates :task_id, uniqueness: { scope: :dependency_id }
  validate :no_circular_dependency

  private

  def no_circular_dependency
    return if task_id.nil? || dependency_id.nil?

    if task_id == dependency_id
      errors.add(:base, 'A task cannot depend on itself')
    elsif creates_circular_dependency?
      errors.add(:base, 'This would create a circular dependency')
    end
  end

  def creates_circular_dependency?
    visited = Set.new
    check_dependency(dependency_id, visited)
  end

  def check_dependency(dep_id, visited)
    return false if dep_id.nil?
    return true if dep_id == task_id
    return false if visited.include?(dep_id)

    visited.add(dep_id)

    TaskDependency.where(task_id: dep_id).pluck(:dependency_id).any? do |next_dep|
      check_dependency(next_dep, visited)
    end
  end
end
