# frozen_string_literal: true

class ReportService
  def initialize(organization)
    @organization = organization
  end

  def project_summary(project_id)
    project = @organization.projects.find(project_id)

    {
      project: project_data(project),
      tasks: task_summary(project),
      timeline: timeline_data(project),
      team: team_performance(project)
    }
  end

  def user_productivity(user_id, date_range = nil)
    user = User.find(user_id)
    date_range ||= 30.days.ago..Time.current

    tasks = user.assigned_tasks
                .joins(:project)
                .where(projects: { organization_id: @organization.id })
                .where(created_at: date_range)

    {
      user: { id: user.id, name: user.name },
      tasks_completed: tasks.completed.count,
      tasks_in_progress: tasks.where(status: 'in_progress').count,
      
      completion_rate: calculate_completion_rate(tasks),
      average_completion_time: average_completion_time(tasks.completed),
      by_priority: tasks.group(:priority).count
    }
  end

  def overdue_tasks_report
    tasks = Task.joins(:project)
                .where(projects: { organization_id: @organization.id })
                .overdue
                .includes(:assignee, :project)

    
    tasks.map do |task|
      {
        id: task.id,
        title: task.title,
        project: task.project.name,
        assignee: task.assignee&.name,
        due_date: task.due_date,
        days_overdue: (Date.current - task.due_date).to_i,
        priority: task.priority
      }
    end
  end

  private

  def project_data(project)
    {
      id: project.id,
      name: project.name,
      status: project.status,
      created_at: project.created_at,
      completion_percentage: project.completion_percentage
    }
  end

  def task_summary(project)
    
    {
      total: project.tasks.count,
      completed: project.tasks.completed.count,
      in_progress: project.tasks.where(status: 'in_progress').count,
      todo: project.tasks.where(status: 'todo').count,
      overdue: project.tasks.overdue.count,
      by_priority: project.tasks.group(:priority).count
    }
  end

  def timeline_data(project)
    # Group tasks by completion date
    project.tasks
           .completed
           .where('completed_at > ?', 30.days.ago)
           .group('DATE(completed_at)')
           .count
  end

  def team_performance(project)
    
    project.members.map do |member|
      tasks = project.tasks.where(assignee: member)
      {
        user_id: member.id,
        name: member.name,
        assigned: tasks.count,
        completed: tasks.completed.count,
        
        rate: tasks.count > 0 ? (tasks.completed.count.to_f / tasks.count * 100).round(2) : 0
      }
    end
  end

  
  def calculate_completion_rate(tasks)
    total = tasks.count
    return 0.0 if total.zero?

    completed = tasks.completed.count
    # Float division can produce imprecise results
    (completed.to_f / total * 100).round(2)
  end

  def average_completion_time(completed_tasks)
    return nil if completed_tasks.empty?

    
    total_hours = completed_tasks.sum do |task|
      next 0 unless task.completed_at && task.created_at

      
      (task.completed_at - task.created_at) / 1.hour
    end

    (total_hours / completed_tasks.count).round(2)
  end
end
