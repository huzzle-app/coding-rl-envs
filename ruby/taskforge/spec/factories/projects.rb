# frozen_string_literal: true

FactoryBot.define do
  factory :project do
    name { Faker::App.name }
    description { Faker::Lorem.paragraph }
    status { 'planning' }
    organization
    creator { association :user }

    trait :active do
      status { 'active' }
    end

    trait :completed do
      status { 'completed' }
    end

    trait :with_tasks do
      transient do
        task_count { 5 }
      end

      after(:create) do |project, evaluator|
        create_list(:task, evaluator.task_count, project: project)
      end
    end

    trait :with_members do
      transient do
        member_count { 3 }
      end

      after(:create) do |project, evaluator|
        create_list(:project_membership, evaluator.member_count, project: project)
      end
    end
  end

  factory :project_membership do
    project
    user
    role { 'member' }

    trait :admin do
      role { 'admin' }
    end
  end
end
