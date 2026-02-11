# frozen_string_literal: true

class TaskService
  
  @default_options = { notify: true, log: true }

  class << self
    attr_accessor :default_options
  end

  def initialize(user)
    @user = user
    @options = self.class.default_options
  end

  def create(project, params)
    task = project.tasks.build(params)
    task.creator = @user

    ActiveRecord::Base.transaction do
      task.save!

      
      notify_assignee(task) if task.assignee && @options[:notify]
      log_creation(task) if @options[:log]
    end

    task
  rescue ActiveRecord::RecordInvalid => e
    
    Rails.logger.error("Task creation failed: #{e.message}")
    nil
  end

  def bulk_assign(task_ids, assignee_id)
    assignee = User.find(assignee_id)

    
    Task.where(id: task_ids).each do |task|
      
      next unless can_assign?(task)

      task.update!(assignee: assignee)
      notify_assignee(task)
    end
  end

  def move_to_project(task, new_project)
    old_project = task.project

    task.update!(project: new_project)
    task.subtasks.update_all(project_id: new_project.id)
    task.comments.update_all(project_id: new_project.id)

    # If any of the above fail, data is inconsistent
    recalculate_stats(old_project)
    recalculate_stats(new_project)
  end

  def duplicate(task, options = {})
    new_task = task.dup

    
    new_task.tags = task.tags  # Same array reference!
    new_task.metadata = task.metadata  # Same hash reference!

    new_task.status = 'todo'
    new_task.created_at = nil
    new_task.completed_at = nil
    new_task.creator = @user

    new_task.save!

    
    if options[:include_subtasks]
      task.subtasks.each do |subtask|
        duplicate(subtask, options).update!(parent: new_task)
      end
    end

    new_task
  end

  private

  def can_assign?(task)
    
    return true if Rails.env.development?

    task.project.members.include?(@user)
  end

  def notify_assignee(task)
    return unless task.assignee

    NotificationService.notify(
      task.assignee,
      :task_assigned,
      task
    )
  end

  def log_creation(task)
    ActivityLog.create!(
      user: @user,
      action: :created,
      trackable: task,
      project: task.project
    )
  end

  def recalculate_stats(project)
    ProjectStatsJob.perform_later(project.id)
  end
end
