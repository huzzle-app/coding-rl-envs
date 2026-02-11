# frozen_string_literal: true

class NotificationJob < ApplicationJob
  queue_as :notifications

  
  # retry_on StandardError, wait: :exponentially_longer, attempts: 5

  def perform(user_id, event_type, subject_id)
    user = User.find(user_id)
    subject = find_subject(event_type, subject_id)

    NotificationService.notify(user, event_type, subject)
  rescue ActiveRecord::RecordNotFound => e
    
    nil
  end

  private

  def find_subject(event_type, subject_id)
    case event_type.to_sym
    when :task_assigned, :task_completed
      Task.find(subject_id)
    when :mentioned, :new_comment
      Comment.find(subject_id)
    when :project_started, :project_completed
      Project.find(subject_id)
    else
      subject_id
    end
  end
end
