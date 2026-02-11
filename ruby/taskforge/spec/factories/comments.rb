# frozen_string_literal: true

FactoryBot.define do
  factory :comment do
    body { Faker::Lorem.paragraph }
    user
    task
  end

  factory :notification do
    notification_type { 'task_assigned' }
    message { 'You have been assigned a task' }
    user
    notifiable { association :task }
  end

  factory :milestone do
    name { Faker::Lorem.words(number: 3).join(' ') }
    description { Faker::Lorem.paragraph }
    due_date { 1.month.from_now }
    status { 'open' }
    project
  end
end
