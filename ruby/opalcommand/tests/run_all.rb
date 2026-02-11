# frozen_string_literal: true

base = File.expand_path(__dir__)
patterns = ARGV.empty? ? ['tests/unit/**/*_test.rb', 'tests/integration/**/*_test.rb', 'tests/services/**/*_test.rb', 'tests/stress/**/*_test.rb'] : ARGV
patterns.each do |pattern|
  Dir.glob(File.expand_path(pattern, File.expand_path('..', base))).sort.each { |file| require file }
end
