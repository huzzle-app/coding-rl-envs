# frozen_string_literal: true

class Event < ApplicationRecord
  validates :event_type, presence: true
  validates :occurred_at, presence: true

  serialize :properties, coder: JSON

  scope :by_type, ->(type) { where(event_type: type) }
  scope :for_user, ->(user_id) { where(user_id: user_id) }
  scope :for_entity, ->(type, id) { where(entity_type: type, entity_id: id) }
  scope :in_session, ->(session_id) { where(session_id: session_id) }
  scope :in_date_range, ->(range) { where(occurred_at: range) }
  scope :recent, -> { order(occurred_at: :desc) }

  before_validation :set_occurred_at

  def parsed_properties
    properties.is_a?(String) ? JSON.parse(properties) : properties
  rescue JSON::ParserError
    {}
  end

  class << self
    def track(event_type:, user_id: nil, entity_type: nil, entity_id: nil, properties: {}, session_id: nil, source: 'web')
      create!(
        event_type: event_type,
        user_id: user_id,
        entity_type: entity_type,
        entity_id: entity_id,
        properties: properties.to_json,
        session_id: session_id,
        source: source,
        occurred_at: Time.current
      )
    end

    def count_by_type(date_range = nil)
      scope = all
      scope = scope.in_date_range(date_range) if date_range
      scope.group(:event_type).count
    end

    def unique_users(date_range = nil)
      scope = where.not(user_id: nil)
      scope = scope.in_date_range(date_range) if date_range
      scope.distinct.count(:user_id)
    end
  end

  private

  def set_occurred_at
    self.occurred_at ||= Time.current
  end
end
