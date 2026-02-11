# frozen_string_literal: true

require 'rails_helper'

RSpec.describe Project, type: :model do
  describe 'associations' do
    it { should belong_to(:organization) }
    it { should belong_to(:creator).class_name('User') }
    it { should have_many(:tasks).dependent(:destroy) }
    it { should have_many(:milestones).dependent(:destroy) }
    it { should have_many(:project_memberships).dependent(:destroy) }
    it { should have_many(:members).through(:project_memberships) }
  end

  describe 'validations' do
    it { should validate_presence_of(:name) }
    it { should validate_presence_of(:organization) }
    it { should validate_length_of(:name).is_at_most(100) }
  end

  describe 'state machine' do
    let(:project) { create(:project, status: 'planning') }

    it 'can start' do
      project.start!
      expect(project).to be_active
    end

    it 'can pause and resume' do
      project.start!
      project.pause!
      expect(project).to be_on_hold

      project.resume!
      expect(project).to be_active
    end

    it 'can complete' do
      project.start!
      project.complete!
      expect(project).to be_completed
    end
  end

  describe '#completion_percentage' do
    let(:project) { create(:project) }

    context 'with no tasks' do
      it 'returns 0' do
        expect(project.completion_percentage).to eq(0)
      end
    end

    context 'with tasks' do
      before do
        create_list(:task, 3, project: project, status: 'completed')
        create_list(:task, 2, project: project, status: 'todo')
      end

      
      # query with conditional counting
      it 'calculates percentage correctly' do
        expect(project.completion_percentage).to eq(60.0)
      end

      it 'computes percentage in a single query' do
        # Fixed behavior: should use one query, not two separate counts
        expect {
          project.completion_percentage
        }.to make_database_queries(count: 1)
      end
    end
  end

  describe '#stats' do
    let(:project) { create(:project) }

    before do
      create_list(:task, 5, project: project, status: 'todo')
      create_list(:task, 3, project: project, status: 'completed')
      create(:task, project: project, status: 'todo', due_date: 1.day.ago)
    end

    
    # should return consistent stats without data corruption
    it 'returns correct stats' do
      stats = project.stats

      expect(stats[:total_tasks]).to eq(9)
      expect(stats[:completed_tasks]).to eq(3)
      expect(stats[:overdue_tasks]).to eq(1)
    end

    it 'returns consistent stats under concurrent access' do
      results = []
      threads = 5.times.map do
        Thread.new { results << project.stats }
      end
      threads.each(&:join)

      # Fixed behavior: all threads should see identical stats
      expect(results).to all(be_a(Hash))
      expect(results.map { |r| r[:total_tasks] }).to all(eq(9))
      expect(results.uniq.size).to eq(1)
    end
  end

  describe '#cleanup_old_tasks!' do
    let(:project) { create(:project) }

    
    # first then destroy, or use delete_all
    context 'with old completed tasks' do
      before do
        Timecop.freeze(2.years.ago) do
          create_list(:task, 5, project: project, status: 'completed')
        end
        create_list(:task, 3, project: project, status: 'completed')
      end

      it 'removes all old completed tasks without skipping any' do
        project.cleanup_old_tasks!

        # Fixed behavior: should delete all 5 old tasks (not skip some)
        old_tasks = project.tasks.where('created_at < ?', 1.year.ago)
        expect(old_tasks.count).to eq(0)
      end

      it 'preserves recent completed tasks' do
        project.cleanup_old_tasks!

        recent_tasks = project.tasks.where('created_at >= ?', 1.year.ago)
        expect(recent_tasks.count).to eq(3)
      end
    end
  end

  describe '#tasks_by_status' do
    let(:project) { create(:project) }

    before do
      create_list(:task, 3, project: project, status: 'todo')
      create_list(:task, 2, project: project, status: 'in_progress')
      create_list(:task, 5, project: project, status: 'completed')
    end

    
    it 'groups tasks by status correctly' do
      result = project.tasks_by_status

      expect(result['todo']).to eq(3)
      expect(result['in_progress']).to eq(2)
      expect(result['completed']).to eq(5)
    end

    it 'returns all status categories' do
      result = project.tasks_by_status

      expect(result.keys).to include('todo', 'in_progress', 'completed')
    end
  end
end
