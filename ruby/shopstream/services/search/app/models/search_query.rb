# frozen_string_literal: true

class SearchQuery < ApplicationRecord
  validates :query, presence: true

  serialize :filters, coder: JSON

  scope :recent, -> { order(created_at: :desc) }
  scope :by_user, ->(user_id) { where(user_id: user_id) }
  scope :with_results, -> { where('result_count > 0') }
  scope :slow, -> { where('response_time_ms > ?', 1000) }

  def successful?
    result_count > 0
  end

  def slow?
    response_time_ms > 1000
  end

  class << self
    def log_search(query:, user_id: nil, ip_address: nil, result_count: 0, filters: {}, response_time_ms: nil)
      create!(
        query: query,
        user_id: user_id,
        ip_address: ip_address,
        result_count: result_count,
        filters: filters.to_json,
        response_time_ms: response_time_ms
      )
    end

    def popular_queries(limit: 10, since: 7.days.ago)
      where('created_at > ?', since)
        .group(:query)
        .order('COUNT(*) DESC')
        .limit(limit)
        .pluck(:query)
    end
  end
end
