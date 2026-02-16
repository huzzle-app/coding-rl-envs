# frozen_string_literal: true

require 'rails_helper'

RSpec.describe TaskService do
  let(:user) { create(:user) }
  let(:project) { create(:project) }
  let(:service) { described_class.new(user) }

  describe '#create' do
    let(:valid_params) do
      {
        title: 'New Task',
        description: 'Task description',
        priority: 'high'
      }
    end

    it 'creates a task' do
      task = service.create(project, valid_params)

      expect(task).to be_persisted
      expect(task.title).to eq('New Task')
      expect(task.creator).to eq(user)
    end

    
    # so callers can handle validation failures properly
    it 'raises error on validation failure instead of returning nil' do
      expect {
        service.create(project, { title: '' })
      }.to raise_error(ActiveRecord::RecordInvalid)
    end

    context 'with assignee' do
      let(:assignee) { create(:user) }
      let(:params_with_assignee) { valid_params.merge(assignee_id: assignee.id) }

      it 'notifies assignee' do
        expect(NotificationService).to receive(:notify)
          .with(assignee, :task_assigned, anything)

        service.create(project, params_with_assignee)
      end
    end


    # should happen after the transaction commits, not inside it
    it 'does not send notification when transaction rolls back' do
      assignee = create(:user)

      # Simulate failure in log_creation (after save! but before transaction commits)
      allow_any_instance_of(TaskService).to receive(:log_creation)
        .and_raise(ActiveRecord::RecordInvalid.new(Task.new))

      # Fixed: notification should NOT fire if transaction rolls back
      # Buggy: notification fires inside transaction before the rollback
      expect(NotificationService).not_to receive(:notify)

      service.create(project, valid_params.merge(assignee_id: assignee.id)) rescue nil
    end
  end

  describe '#bulk_assign' do
    let(:assignee) { create(:user) }
    let!(:tasks) { create_list(:task, 5, project: project) }

    
    it 'assigns multiple tasks' do
      service.bulk_assign(tasks.map(&:id), assignee.id)

      tasks.each do |task|
        expect(task.reload.assignee).to eq(assignee)
      end
    end

    it 'uses bulk update instead of individual saves' do
      # Fixed behavior: should use 1-2 queries, not 10-15
      expect {
        service.bulk_assign(tasks.map(&:id), assignee.id)
      }.to make_database_queries(count: 1..4)
    end
  end

  describe '#move_to_project' do
    let(:task) { create(:task, project: project) }
    let!(:subtask) { create(:task, parent: task, project: project) }
    let!(:comment) { create(:comment, task: task) }
    let(:new_project) { create(:project, organization: project.organization) }

    
    it 'moves task and related records atomically' do
      service.move_to_project(task, new_project)

      expect(task.reload.project).to eq(new_project)
      expect(subtask.reload.project).to eq(new_project)
    end

    it 'rolls back all changes on partial failure' do
      allow(Comment).to receive(:update_all).and_raise(ActiveRecord::StatementInvalid)

      expect {
        service.move_to_project(task, new_project)
      }.to raise_error(ActiveRecord::StatementInvalid)

      # Fixed behavior: task should not have moved if comments failed
      expect(task.reload.project).to eq(project)
      expect(subtask.reload.project).to eq(project)
    end
  end

  describe '#duplicate' do
    let(:task) { create(:task, tags: ['ruby', 'rails'], metadata: { key: 'value' }) }

    it 'creates a duplicate with correct attributes' do
      new_task = service.duplicate(task)

      expect(new_task).to be_persisted
      expect(new_task.title).to eq(task.title)
      expect(new_task.status).to eq('todo')
    end

    
    it 'creates independent copy of tags array' do
      new_task = service.duplicate(task)

      # Fixed behavior: modifying new task's tags should not affect original
      new_task.tags << 'new_tag'

      expect(task.tags).not_to include('new_tag')
      expect(task.tags).to eq(['ruby', 'rails'])
    end

    it 'creates independent copy of metadata hash' do
      new_task = service.duplicate(task)

      # Fixed behavior: modifying new task's metadata should not affect original
      new_task.metadata[:new_key] = 'new_value'

      expect(task.metadata).not_to have_key(:new_key)
      expect(task.metadata).to eq({ key: 'value' })
    end
  end

  
  # regardless of environment
  describe 'authorization' do
    context 'in development environment' do
      before do
        allow(Rails).to receive(:env).and_return(ActiveSupport::StringInquirer.new('development'))
      end

      it 'still enforces authorization in development' do
        non_member_task = create(:task)

        # Fixed behavior: should check membership even in development
        expect(service.send(:can_assign?, non_member_task)).to be false
      end
    end

    context 'with authorized user' do
      it 'allows assignment for project members' do
        member_project = create(:project)
        create(:project_membership, project: member_project, user: user)
        member_task = create(:task, project: member_project)

        expect(service.send(:can_assign?, member_task)).to be true
      end
    end
  end

  
  # have its own independent options copy
  describe 'default options' do
    it 'does not share options across instances' do
      service1 = described_class.new(user)
      service2 = described_class.new(user)

      # Modifying options in one instance
      service1.instance_variable_get(:@options)[:notify] = false

      # Fixed behavior: service2 should NOT be affected
      expect(service2.instance_variable_get(:@options)[:notify]).to be true
    end
  end
end
