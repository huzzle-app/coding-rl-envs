# frozen_string_literal: true

require 'rails_helper'

RSpec.describe SearchService do
  let(:user) { create(:user) }
  let(:organization) { create(:organization, members: [user]) }
  let(:project) { create(:project, organization: organization) }

  describe '#search' do
    context 'with blank query' do
      it 'returns empty results' do
        service = described_class.new(user, '')
        result = service.search

        expect(result[:results]).to be_empty
        expect(result[:total]).to eq(0)
      end
    end

    context 'with valid query' do
      let!(:matching_task) { create(:task, project: project, title: 'Ruby development task') }
      let!(:non_matching_task) { create(:task, project: project, title: 'Python task') }

      it 'returns matching tasks' do
        service = described_class.new(user, 'Ruby')
        result = service.search

        expect(result[:results].map { |r| r[:id] }).to include(matching_task.id)
        expect(result[:results].map { |r| r[:id] }).not_to include(non_matching_task.id)
      end
    end

    
    describe 'status filter' do
      let!(:task) { create(:task, project: project, title: 'Test task', status: 'todo') }
      let!(:completed_task) { create(:task, project: project, title: 'Test done', status: 'completed') }

      it 'filters by status safely using parameterized queries' do
        service = described_class.new(user, 'Test')

        # Fixed behavior: injection string should be treated as literal value
        result = service.search(status: "todo' OR '1'='1")

        # Should NOT return all tasks - injection should fail
        task_ids = result[:results].select { |r| r[:type] == 'task' }.map { |r| r[:id] }
        expect(task_ids).not_to include(completed_task.id)
      end

      it 'returns correct results with valid status filter' do
        service = described_class.new(user, 'Test')
        result = service.search(status: 'todo')

        task_ids = result[:results].select { |r| r[:type] == 'task' }.map { |r| r[:id] }
        expect(task_ids).to include(task.id)
        expect(task_ids).not_to include(completed_task.id)
      end
    end

    
    # who are members of the same organization
    describe 'user search' do
      let!(:org_member) { create(:user, name: 'John Doe') }
      let!(:external_user) { create(:user, name: 'John Smith') }

      before do
        organization.members << org_member
      end

      it 'only returns users within the organization' do
        service = described_class.new(user, 'John')
        result = service.search(include_users: true)

        user_ids = result[:results].select { |r| r[:type] == 'user' }.map { |r| r[:id] }

        # Fixed behavior: should NOT expose external users
        expect(user_ids).to include(org_member.id)
        expect(user_ids).not_to include(external_user.id)
      end
    end

    
    describe 'query efficiency' do
      it 'minimizes database queries for full search' do
        service = described_class.new(user, 'test')

        # Fixed behavior: should use fewer queries (batched or parallel)
        expect {
          service.search(
            include_tasks: true,
            include_projects: true,
            include_comments: true,
            include_users: true
          )
        }.to make_database_queries(count: 1..4)
      end
    end
  end
end
