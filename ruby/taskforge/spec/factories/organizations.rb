# frozen_string_literal: true

FactoryBot.define do
  factory :organization do
    name { Faker::Company.name }
    slug { name.parameterize }
    description { Faker::Company.catch_phrase }
    status { 'active' }

    trait :suspended do
      status { 'suspended' }
    end

    trait :with_members do
      transient do
        member_count { 3 }
      end

      after(:create) do |org, evaluator|
        create_list(:organization_membership, evaluator.member_count, organization: org)
      end
    end

    transient do
      members { [] }
    end

    after(:create) do |org, evaluator|
      evaluator.members.each do |member|
        create(:organization_membership, organization: org, user: member)
      end
    end
  end

  factory :organization_membership do
    organization
    user
    role { 'member' }

    trait :owner do
      role { 'owner' }
    end

    trait :admin do
      role { 'admin' }
    end
  end
end
