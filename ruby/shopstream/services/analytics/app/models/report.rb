# frozen_string_literal: true

class Report < ApplicationRecord
  VALID_TYPES = %w[sales_summary customer_analytics inventory orders product_performance].freeze

  validates :name, presence: true
  validates :report_type, presence: true, inclusion: { in: VALID_TYPES }
  validates :status, presence: true

  serialize :parameters, coder: JSON

  scope :pending, -> { where(status: 'pending') }
  scope :in_progress, -> { where(status: 'in_progress') }
  scope :completed, -> { where(status: 'completed') }
  scope :failed, -> { where(status: 'failed') }
  scope :by_type, ->(type) { where(report_type: type) }
  scope :created_by, ->(user_id) { where(created_by_id: user_id) }

  def start!
    update!(status: 'in_progress', started_at: Time.current, progress: 0)
  end

  def complete!(output_path: nil)
    update!(
      status: 'completed',
      completed_at: Time.current,
      progress: 100,
      output_path: output_path || self.output_path
    )
  end

  def fail!(error_message:)
    update!(status: 'failed', error_message: error_message)
  end

  def update_progress!(percent)
    update!(progress: [percent, 100].min)
  end

  def completed?
    status == 'completed'
  end

  def in_progress?
    status == 'in_progress'
  end

  def failed?
    status == 'failed'
  end

  def duration
    return nil unless started_at
    end_time = completed_at || Time.current
    end_time - started_at
  end

  def parsed_parameters
    parameters.is_a?(String) ? JSON.parse(parameters) : (parameters || {})
  rescue JSON::ParserError
    {}
  end
end
