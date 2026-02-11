# frozen_string_literal: true

class ProjectStatsJob < ApplicationJob
  queue_as :default

  
  # unique :until_executed

  def perform(project_id)
    project = Project.find(project_id)

    stats = calculate_stats(project)

    
    project.update_columns(
      tasks_count: stats[:total],
      completed_tasks_count: stats[:completed],
      overdue_tasks_count: stats[:overdue],
      stats_updated_at: Time.current
    )

    
    broadcast_stats_update(project)
  rescue ActiveRecord::RecordNotFound
    # Project was deleted, ignore
  end

  private

  def calculate_stats(project)
    {
      total: project.tasks.count,
      completed: project.tasks.completed.count,
      in_progress: project.tasks.where(status: 'in_progress').count,
      overdue: project.tasks.overdue.count
    }
  end

  def broadcast_stats_update(project)
    
    ActionCable.server.broadcast(
      "project_#{project.id}",
      { type: 'stats_updated', data: project.reload.as_json }
    )
  end
end
