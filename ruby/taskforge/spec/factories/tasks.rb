# frozen_string_literal: true

FactoryBot.define do
  factory :task do
    title { Faker::Lorem.sentence(word_count: 4) }
    description { Faker::Lorem.paragraph }
    status { 'todo' }
    priority { 'medium' }
    project
    creator { association :user }

    trait :in_progress do
      status { 'in_progress' }
    end

    trait :completed do
      status { 'completed' }
      completed_at { Time.current }
    end

    trait :high_priority do
      priority { 'high' }
    end

    trait :critical do
      priority { 'critical' }
    end

    trait :overdue do
      due_date { 2.days.ago }
      status { 'todo' }
    end

    trait :due_soon do
      due_date { 2.days.from_now }
    end

    trait :with_assignee do
      assignee { association :user }
    end

    trait :with_subtasks do
      transient do
        subtask_count { 3 }
      end

      after(:create) do |task, evaluator|
        create_list(:task, evaluator.subtask_count, parent: task, project: task.project)
      end
    end
  end
end
