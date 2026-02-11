# frozen_string_literal: true

require 'rails_helper'

RSpec.describe Organization, type: :model do
  describe 'associations' do
    it { should have_many(:organization_memberships).dependent(:destroy) }
    it { should have_many(:members).through(:organization_memberships) }
    it { should have_many(:projects).dependent(:destroy) }
  end

  describe 'validations' do
    it { should validate_presence_of(:name) }
    it { should validate_presence_of(:slug) }
    it { should validate_length_of(:name).is_at_most(100) }
  end

  describe 'state machine' do
    let(:org) { create(:organization) }

    it 'starts in active state' do
      expect(org).to be_active
    end

    it 'can be suspended' do
      org.suspend!
      expect(org).to be_suspended
    end

    it 'can be reactivated' do
      org.suspend!
      org.reactivate!
      expect(org).to be_active
    end
  end

  describe '#increment_project_count!' do
    let(:org) { create(:organization, projects_count: 5) }

    
    it 'increments the count atomically' do
      org.increment_project_count!
      expect(org.reload.projects_count).to eq(6)
    end

    it 'produces correct count under concurrent increments' do
      org = create(:organization, projects_count: 0)

      threads = 10.times.map do
        Thread.new do
          Organization.find(org.id).increment_project_count!
        end
      end
      threads.each(&:join)

      org.reload
      # Fixed behavior: atomic increment should give exactly 10
      expect(org.projects_count).to eq(10)
    end
  end

  describe '#member_details' do
    let(:org) { create(:organization) }
    let!(:members) { create_list(:user, 3) }
    let!(:project) { create(:project, organization: org) }

    before do
      members.each do |member|
        create(:organization_membership, organization: org, user: member, role: 'member')
        create_list(:task, 2, project: project, assignee: member)
      end
    end

    
    it 'returns member details with task counts' do
      details = org.member_details

      expect(details.size).to eq(3)
      expect(details.first).to have_key(:task_count)
      expect(details.first).to have_key(:name)
      expect(details.first).to have_key(:role)
      expect(details.first[:task_count]).to eq(2)
    end

    it 'loads member details without N+1 queries' do
      # Fixed behavior: should use at most 3-4 queries, not 7-15
      expect {
        org.member_details
      }.to make_database_queries(count: 1..4)
    end
  end

  describe '#search_projects' do
    let(:org) { create(:organization) }
    let!(:project1) { create(:project, organization: org, name: 'Alpha Project') }
    let!(:project2) { create(:project, organization: org, name: 'Beta Project') }

    it 'searches projects by name' do
      results = org.search_projects('Alpha')
      expect(results).to include(project1)
      expect(results).not_to include(project2)
    end

    
    it 'safely handles SQL injection attempts via parameterized queries' do
      malicious_query = "'; DROP TABLE projects;--"

      # Fixed behavior: parameterized query prevents injection and returns empty results
      results = org.search_projects(malicious_query)
      expect(results).to be_empty

      # Verify projects table still exists
      expect(Project.count).to be >= 2
    end

    it 'handles special characters in search without errors' do
      expect {
        org.search_projects("test%_'\"\\")
      }.not_to raise_error
    end
  end

  
  # trigger itself recursively via touch
  describe 'sync callback' do
    let(:org) { create(:organization) }

    it 'triggers sync on name change' do
      expect(ExternalSyncJob).to receive(:perform_later).with(org.id)

      org.update!(name: 'New Name')
    end

    it 'does not cause infinite loop when syncing' do
      allow(ExternalSyncJob).to receive(:perform_later)

      # Fixed behavior: after_save should not re-trigger itself
      # The callback should either skip touch or use update_column
      expect {
        Timeout.timeout(5) { org.update!(name: 'Another Name') }
      }.not_to raise_error
    end
  end
end
