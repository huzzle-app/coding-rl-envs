# frozen_string_literal: true

# ShopStream shared library loader
module ShopStream
  class Error < StandardError; end
  class ServiceError < Error; end
  class EventError < Error; end
  class CacheError < Error; end
end

require_relative 'kafka_consumer'
require_relative 'kafka_producer'
require_relative 'event_serializer'
require_relative 'event_processor'
require_relative 'event_store'
require_relative 'dlq_processor'
require_relative 'http_client'
require_relative 'request_context'
require_relative 'api_client'
require_relative 'request_logger'
require_relative 'cache_serializer'
