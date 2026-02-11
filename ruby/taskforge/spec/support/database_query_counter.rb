# frozen_string_literal: true

# Custom RSpec matcher for counting database queries
module DatabaseQueryCounter
  class QueryCounter
    attr_reader :query_count

    def initialize
      @query_count = 0
    end

    def call(_name, _start, _finish, _id, payload)
      return if payload[:name] == 'SCHEMA' || payload[:name] == 'TRANSACTION'
      return if payload[:sql]&.include?('pg_')
      return if payload[:sql]&.start_with?('SAVEPOINT')
      return if payload[:sql]&.start_with?('RELEASE SAVEPOINT')
      return if payload[:sql]&.start_with?('ROLLBACK')

      @query_count += 1
    end
  end

  def count_queries(&block)
    counter = QueryCounter.new
    subscription = ActiveSupport::Notifications.subscribe('sql.active_record', counter)
    block.call
    ActiveSupport::Notifications.unsubscribe(subscription)
    counter.query_count
  end
end

RSpec::Matchers.define :make_database_queries do |opts|
  match do |block|
    counter = DatabaseQueryCounter::QueryCounter.new
    subscription = ActiveSupport::Notifications.subscribe('sql.active_record', counter)
    block.call
    ActiveSupport::Notifications.unsubscribe(subscription)

    @actual_count = counter.query_count

    case opts
    when Range
      opts.include?(@actual_count)
    when Integer
      @actual_count == opts
    when Hash
      if opts[:count].is_a?(Range)
        opts[:count].include?(@actual_count)
      else
        @actual_count == opts[:count]
      end
    else
      false
    end
  end

  failure_message do |_block|
    expected = opts.is_a?(Hash) ? opts[:count] : opts
    "expected #{expected} database queries but got #{@actual_count}"
  end

  supports_block_expectations
end
