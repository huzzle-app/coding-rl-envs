# frozen_string_literal: true

root = File.expand_path('..', __dir__)
Dir.chdir(root)

targets = ARGV.empty? ? ['tests'] : ARGV
files = targets.flat_map do |target|
  if File.directory?(target)
    Dir[File.join(target, '**/*_test.rb')]
  elsif File.file?(target)
    [target]
  else
    []
  end
end.uniq.sort

if files.empty?
  warn 'No tests selected'
  exit 1
end

files.each do |file|
  require File.expand_path(file, root)
end
