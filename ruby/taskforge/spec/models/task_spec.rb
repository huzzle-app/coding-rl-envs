# frozen_string_literal: true

require 'rails_helper'

RSpec.describe Task, type: :model do
  describe 'associations' do
    it { should belong_to(:project) }
    it { should belong_to(:creator).class_name('User') }
    it { should belong_to(:assignee).class_name('User').optional }
    it { should belong_to(:milestone).optional }
    it { should belong_to(:parent).class_name('Task').optional }
    it { should have_many(:subtasks).class_name('Task').dependent(:destroy) }
    it { should have_many(:comments).dependent(:destroy) }
    it { should have_many(:dependencies) }
  end

  describe 'validations' do
    it { should validate_presence_of(:title) }
    it { should validate_length_of(:title).is_at_most(200) }
    it { should validate_inclusion_of(:priority).in_array(%w[low medium high critical]) }
  end

  describe 'state machine' do
    let(:task) { create(:task, status: 'todo') }

    it 'starts in todo state' do
      expect(task).to be_todo
    end

    it 'can transition to in_progress' do
      task.start!
      expect(task).to be_in_progress
    end

    it 'can complete from in_progress' do
      task.start!
      task.complete!
      expect(task).to be_completed
      expect(task.completed_at).to be_present
    end

    
    # nesting should not cause stack overflow
    context 'with subtasks' do
      let(:parent) { create(:task, status: 'in_progress') }
      let!(:subtask1) { create(:task, parent: parent, status: 'completed') }
      let!(:subtask2) { create(:task, parent: parent, status: 'completed') }

      it 'completes parent when all subtasks done without stack overflow' do
        expect { parent.complete! }.not_to raise_error
        expect(parent.reload).to be_completed
      end

      it 'does not recurse infinitely with nested parents' do
        grandparent = create(:task, status: 'in_progress')
        parent.update!(parent: grandparent)

        # Fixed behavior: should complete without SystemStackError
        expect { parent.complete! }.not_to raise_error
        expect(parent.reload).to be_completed
      end
    end
  end

  describe '#calculate_position' do
    let(:project) { create(:project) }

    
    # unique positions via atomic operations
    it 'calculates position on create' do
      task1 = create(:task, project: project)
      task2 = create(:task, project: project)

      expect(task1.position).to eq(1)
      expect(task2.position).to eq(2)
    end

    it 'assigns unique positions under concurrent creates' do
      tasks = []
      threads = 5.times.map do
        Thread.new do
          tasks << create(:task, project: project)
        end
      end
      threads.each(&:join)

      positions = tasks.map(&:position)
      # Fixed behavior: all positions should be unique (no duplicates from race)
      expect(positions.uniq.size).to eq(5)
      expect(positions.sort).to eq((1..5).to_a)
    end
  end

  describe '#all_dependencies' do
    let(:task) { create(:task) }
    let!(:deps) { create_list(:task, 3) }

    before do
      deps.each { |d| task.dependencies << d }
    end

    
    it 'returns dependency data with assignee info' do
      result = task.all_dependencies

      expect(result.size).to eq(3)
      expect(result.first).to have_key(:assignee)
      expect(result.first).to have_key(:title)
      expect(result.first).to have_key(:status)
    end

    it 'loads dependencies without N+1 queries' do
      # Fixed behavior: 1 query for deps + 1 for assignees = 2, not 1+N
      expect {
        task.all_dependencies
      }.to make_database_queries(count: 1..2)
    end
  end

  describe '#add_tag' do
    let(:task) { create(:task, tags: ['existing']) }

    
    # should not be shared/mutated across calls
    it 'adds a tag successfully' do
      task.add_tag('new_tag')

      expect(task.tags).to include('new_tag')
      expect(task.tags).to include('existing')
    end

    it 'does not accumulate state in default argument across calls' do
      task.add_tag('tag1')
      other_task = create(:task, tags: ['other'])
      other_task.add_tag('tag2')

      # Fixed behavior: default options should be independent per call
      # tag1 should only be on first task, tag2 only on second
      expect(task.reload.tags).to include('tag1')
      expect(task.reload.tags).not_to include('tag2')
      expect(other_task.reload.tags).to include('tag2')
      expect(other_task.reload.tags).not_to include('tag1')
    end
  end

  describe '#assign_to' do
    let(:task) { create(:task) }
    let(:user) { create(:user) }

    
    # be sent AFTER save succeeds
    it 'assigns user and notifies only after successful save' do
      expect(NotificationService).to receive(:notify).with(user, :task_assigned, task)

      task.assign_to(user)

      expect(task.assignee).to eq(user)
    end

    it 'does not send notification if save fails' do
      allow(task).to receive(:save!).and_raise(ActiveRecord::RecordInvalid)

      # Fixed behavior: notification should NOT be sent if save fails
      expect(NotificationService).not_to receive(:notify)

      expect {
        task.assign_to(user)
      }.to raise_error(ActiveRecord::RecordInvalid)
    end
  end

  describe '#blocked?' do
    let(:task) { create(:task) }

    context 'with pending dependencies' do
      before do
        dep = create(:task, status: 'todo')
        task.dependencies << dep
      end

      it 'returns true' do
        expect(task).to be_blocked
      end
    end

    context 'with completed dependencies' do
      before do
        dep = create(:task, status: 'completed')
        task.dependencies << dep
      end

      it 'returns false' do
        expect(task).not_to be_blocked
      end
    end
  end

  describe 'scopes' do
    let!(:overdue_task) { create(:task, due_date: 1.day.ago, status: 'todo') }
    let!(:due_soon_task) { create(:task, due_date: 2.days.from_now, status: 'todo') }
    let!(:completed_task) { create(:task, status: 'completed') }

    describe '.overdue' do
      it 'returns overdue pending tasks' do
        expect(Task.overdue).to include(overdue_task)
        expect(Task.overdue).not_to include(completed_task)
      end
    end

    describe '.due_soon' do
      it 'returns tasks due within 3 days' do
        expect(Task.due_soon).to include(due_soon_task)
        expect(Task.due_soon).not_to include(overdue_task)
      end
    end
  end

  
  # stats job so it fires at most once per save batch
  describe 'callbacks' do
    let(:task) { create(:task) }

    it 'debounces stats job instead of firing on every save' do
      # Fixed behavior: should batch/debounce rather than fire individually
      expect(ProjectStatsJob).to receive(:perform_later).at_most(:once)

      task.update!(title: 'Updated 1')
      task.update!(title: 'Updated 2')
    end
  end
end
