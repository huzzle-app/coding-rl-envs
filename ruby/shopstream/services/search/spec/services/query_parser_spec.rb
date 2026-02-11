# frozen_string_literal: true

require 'rails_helper'

RSpec.describe QueryParser do
  

  describe '#parse' do
    it 'extracts search terms' do
      parser = described_class.new
      result = parser.parse('laptop gaming')

      expect(result[:terms]).to include('laptop', 'gaming')
    end

    it 'extracts quoted phrases' do
      parser = described_class.new
      result = parser.parse('"red shoes" sneakers')

      expect(result[:phrases]).to include('red shoes')
      expect(result[:terms]).to include('sneakers')
    end

    it 'extracts filter expressions' do
      parser = described_class.new
      result = parser.parse('category:electronics price:50')

      expect(result[:filters]).to include('category' => 'electronics')
    end
  end

  describe 'ReDoS prevention' do
    it 'handles pathological input without exponential backtracking' do
      parser = described_class.new

      # Input that causes catastrophic backtracking with vulnerable regex
      malicious_input = 'a' * 30 + '!'

      start = Process.clock_gettime(Process::CLOCK_MONOTONIC)
      parser.parse(malicious_input)
      elapsed = Process.clock_gettime(Process::CLOCK_MONOTONIC) - start

      # Should complete in well under 1 second
      expect(elapsed).to be < 1.0
    end

    it 'handles nested quantifier attack input' do
      parser = described_class.new

      # Input that triggers nested quantifier backtracking
      malicious_input = 'a]' * 20

      start = Process.clock_gettime(Process::CLOCK_MONOTONIC)
      parser.parse(malicious_input)
      elapsed = Process.clock_gettime(Process::CLOCK_MONOTONIC) - start

      expect(elapsed).to be < 1.0
    end
  end

  describe '#validate_query' do
    it 'rejects queries longer than max length' do
      parser = described_class.new
      long_query = 'a' * 1001

      expect(parser.validate_query(long_query)).to be false
    end

    it 'validates balanced quotes without ReDoS' do
      parser = described_class.new

      # Unbalanced quotes with pathological pattern
      input = '"' * 30

      start = Process.clock_gettime(Process::CLOCK_MONOTONIC)
      parser.validate_query(input)
      elapsed = Process.clock_gettime(Process::CLOCK_MONOTONIC) - start

      expect(elapsed).to be < 1.0
    end
  end

  describe '#highlight_matches' do
    it 'highlights matching terms in text' do
      parser = described_class.new
      result = parser.highlight_matches('The red shoe is on sale', 'red shoe')

      expect(result).to include('<mark>red</mark>')
      expect(result).to include('<mark>shoe</mark>')
    end

    it 'escapes regex metacharacters in user input' do
      parser = described_class.new

      # Input with regex metacharacters should not break
      expect {
        parser.highlight_matches('Hello world', '(a+)+')
      }.not_to raise_error
    end

    it 'handles large number of terms without ReDoS' do
      parser = described_class.new

      terms = ('a'..'z').to_a.join(' ')
      text = 'The quick brown fox jumps over the lazy dog'

      start = Process.clock_gettime(Process::CLOCK_MONOTONIC)
      parser.highlight_matches(text, terms)
      elapsed = Process.clock_gettime(Process::CLOCK_MONOTONIC) - start

      expect(elapsed).to be < 1.0
    end
  end

  describe '#tokenize' do
    it 'limits number of tokens to prevent resource exhaustion' do
      parser = described_class.new

      # Very long query with many tokens
      long_query = (1..1000).map { |i| "term#{i}" }.join(' ')

      tokens = parser.tokenize(long_query)

      # Should limit token count
      expect(tokens.size).to be <= 100
    end
  end
end
