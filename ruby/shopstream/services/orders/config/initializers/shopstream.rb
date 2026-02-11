# frozen_string_literal: true

# Load shared ShopStream library
require_relative '../../shared/lib/shopstream'

# Alias KafkaProducer for convenience
KafkaProducer = ShopStream::KafkaProducer unless defined?(KafkaProducer)
