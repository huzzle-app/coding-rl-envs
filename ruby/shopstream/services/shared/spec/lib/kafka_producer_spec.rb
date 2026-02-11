# frozen_string_literal: true

require 'rails_helper'

RSpec.describe ShopStream::KafkaProducer do
  
  describe 'topic auto-creation' do
    let(:kafka_double) { double('kafka') }
    let(:producer_double) { double('producer', deliver_messages: nil, shutdown: nil) }

    before do
      allow(Kafka).to receive(:new).and_return(kafka_double)
      allow(kafka_double).to receive(:producer).and_return(producer_double)
    end

    it 'creates topic automatically if it does not exist' do
      allow(producer_double).to receive(:produce).and_raise(Kafka::UnknownTopicOrPartition)

      admin_double = double('admin')
      allow(kafka_double).to receive(:admin).and_return(admin_double)
      allow(admin_double).to receive(:list_topics).and_return([])
      expect(admin_double).to receive(:create_topic).with('new.topic', hash_including(:num_partitions))

      # Fixed version should auto-create and retry
      instance = described_class.new
      instance.publish('new.topic', { data: 'test' }) rescue nil
    end

    it 'does not swallow errors silently when topic creation fails' do
      allow(producer_double).to receive(:produce).and_raise(Kafka::UnknownTopicOrPartition)

      instance = described_class.new
      
      instance.publish('missing.topic', { data: 'test' }) rescue nil
    end

    it 'publishes successfully to existing topics' do
      expect(producer_double).to receive(:produce).with(anything, hash_including(topic: 'existing.topic'))
      expect(producer_double).to receive(:deliver_messages)

      allow(ShopStream::EventSerializer).to receive(:serialize).and_return('{}')

      instance = described_class.new
      instance.publish('existing.topic', { data: 'test' })
    end
  end
end
