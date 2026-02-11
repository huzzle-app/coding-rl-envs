# frozen_string_literal: true

class NotificationTemplate < ApplicationRecord
  validates :name, presence: true, uniqueness: true
  validates :notification_type, presence: true
  validates :channel, presence: true
  validates :body_template, presence: true

  serialize :default_variables, coder: JSON

  scope :active, -> { where(active: true) }
  scope :by_type, ->(type) { where(notification_type: type) }
  scope :by_channel, ->(channel) { where(channel: channel) }

  def render(variables = {})
    merged_vars = (default_variables || {}).merge(variables.stringify_keys)

    {
      subject: render_template(subject_template, merged_vars),
      body: render_template(body_template, merged_vars)
    }
  end

  def active?
    active
  end

  def deactivate!
    update!(active: false)
  end

  class << self
    def find_template(notification_type:, channel:)
      active.find_by(notification_type: notification_type, channel: channel)
    end
  end

  private

  def render_template(template, variables)
    return nil if template.nil?

    result = template.dup
    variables.each do |key, value|
      result.gsub!("{{#{key}}}", value.to_s)
    end
    result
  end
end
