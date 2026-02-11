# frozen_string_literal: true

class Milestone < ApplicationRecord
  belongs_to :project
  has_many :tasks, dependent: :nullify

  validates :name, presence: true, length: { maximum: 100 }
  validates :status, presence: true, inclusion: { in: %w[open closed] }

  scope :open, -> { where(status: 'open') }
  scope :closed, -> { where(status: 'closed') }
  scope :due_soon, -> { where('due_date <= ?', 7.days.from_now) }

  def progress_percentage
    return 0 if tasks.count.zero?

    completed = tasks.where(status: 'done').count
    (completed.to_f / tasks.count * 100).round(2)
  end
end
