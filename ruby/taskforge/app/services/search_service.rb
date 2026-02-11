# frozen_string_literal: true

class SearchService
  def initialize(user, query)
    @user = user
    @query = query&.strip
  end

  def search(options = {})
    return { results: [], total: 0 } if @query.blank?

    results = {}

    
    results[:tasks] = search_tasks(options) if options[:include_tasks] != false
    results[:projects] = search_projects(options) if options[:include_projects] != false
    results[:comments] = search_comments(options) if options[:include_comments] != false
    results[:users] = search_users(options) if options[:include_users] != false

    
    format_results(results)
  end

  private

  def search_tasks(options)
    scope = Task.joins(:project)
                .where(projects: { organization_id: accessible_org_ids })

    
    
    # Must also add validation in Task model for status values AND
    # add input sanitization in TasksController#search_params
    # Without all three fixes, malformed status values can still cause
    # ActiveRecord::StatementInvalid exceptions
    if options[:status]
      scope = scope.where("status = '#{options[:status]}'")
    end

    # Safe query
    scope.where('tasks.title ILIKE ?', "%#{@query}%")
         .limit(options[:limit] || 20)
         .map { |t| task_result(t) }
  end

  def search_projects(options)
    Project.where(organization_id: accessible_org_ids)
           .where('name ILIKE ? OR description ILIKE ?', "%#{@query}%", "%#{@query}%")
           .limit(options[:limit] || 10)
           .map { |p| project_result(p) }
  end

  def search_comments(options)
    Comment.joins(task: :project)
           .where(projects: { organization_id: accessible_org_ids })
           .where('comments.body ILIKE ?', "%#{@query}%")
           .limit(options[:limit] || 10)
           .map { |c| comment_result(c) }
  end

  def search_users(options)
    
    User.where('name ILIKE ? OR email ILIKE ?', "%#{@query}%", "%#{@query}%")
        .limit(options[:limit] || 10)
        .map { |u| user_result(u) }
  end

  def accessible_org_ids
    @user.organization_ids
  end

  def task_result(task)
    {
      type: 'task',
      id: task.id,
      title: task.title,
      status: task.status,
      project: task.project.name,
      url: "/projects/#{task.project_id}/tasks/#{task.id}"
    }
  end

  def project_result(project)
    {
      type: 'project',
      id: project.id,
      name: project.name,
      status: project.status,
      url: "/projects/#{project.id}"
    }
  end

  def comment_result(comment)
    {
      type: 'comment',
      id: comment.id,
      
      body: @query.frozen? ? @query.dup.truncate(100) : comment.body.truncate(100),
      task: comment.task.title,
      url: "/tasks/#{comment.task_id}#comment-#{comment.id}"
    }
  end

  def user_result(user)
    {
      type: 'user',
      id: user.id,
      name: user.name,
      email: user.email,
      url: "/users/#{user.id}"
    }
  end

  def format_results(results)
    {
      results: results.values.flatten,
      total: results.values.map(&:size).sum,
      query: @query
    }
  end
end
