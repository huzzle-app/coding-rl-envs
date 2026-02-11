# frozen_string_literal: true

require 'rails_helper'

RSpec.describe User, type: :model do
  describe 'associations' do
    it { should have_many(:organization_memberships).dependent(:destroy) }
    it { should have_many(:organizations).through(:organization_memberships) }
    it { should have_many(:assigned_tasks).class_name('Task') }
    it { should have_many(:created_tasks).class_name('Task') }
    it { should have_many(:comments).dependent(:destroy) }
    it { should have_many(:notifications).dependent(:destroy) }
  end

  describe 'validations' do
    it { should validate_presence_of(:name) }
    it { should validate_presence_of(:email) }
    it { should validate_length_of(:name).is_at_most(100) }
  end

  describe '#full_profile' do
    let(:user) { create(:user) }
    let!(:organization) { create(:organization, members: [user]) }

    it 'returns user profile data' do
      profile = user.full_profile

      expect(profile[:id]).to eq(user.id)
      expect(profile[:name]).to eq(user.name)
      expect(profile[:organizations]).to include(organization.name)
    end

    
    # return consistent results without data corruption
    it 'returns thread-safe profile under concurrent access' do
      profiles = []
      threads = 5.times.map do
        Thread.new { profiles << user.full_profile }
      end
      threads.each(&:join)

      # All concurrent reads should return identical, non-nil profiles
      expect(profiles).to all(be_a(Hash))
      expect(profiles.map { |p| p[:id] }).to all(eq(user.id))
      expect(profiles.uniq.size).to eq(1)
    end
  end

  describe '#preferences' do
    let(:user) { create(:user, settings: { 'theme' => 'dark' }) }

    
    # correctly return the theme from string-keyed settings hash
    it 'returns theme preference using consistent key access' do
      # Fixed behavior: should return 'dark' from the settings hash
      expect(user.preferences).to eq('dark')
    end

    it 'returns default when settings is nil' do
      user_no_settings = create(:user, settings: nil)
      expect(user_no_settings.preferences).to eq('light')
    end

    it 'returns theme with string key directly' do
      expect(user.settings['theme']).to eq('dark')
    end
  end

  describe '#as_json' do
    let(:user) { create(:user) }
    let(:project) { create(:project) }
    let!(:tasks) { create_list(:task, 3, assignee: user, project: project) }

    
    # use eager loading instead of individual queries
    it 'includes task counts' do
      json = user.as_json

      expect(json['task_count']).to eq(3)
    end

    it 'serializes multiple users without N+1 queries' do
      users = create_list(:user, 5)
      users.each { |u| create_list(:task, 2, assignee: u, project: project) }

      # Fixed behavior: should use at most 5 queries (not 15-20)
      expect {
        users.map(&:as_json)
      }.to make_database_queries(count: 1..5)
    end
  end

  describe '#deactivate!' do
    let(:user) { create(:user) }

    it 'sets deactivated_at' do
      user.deactivate!

      expect(user.deactivated_at).to be_present
    end

    
    # should be rescued and not prevent deactivation
    it 'handles notification service failure gracefully' do
      allow(NotificationService).to receive(:notify_admins).and_raise(StandardError, 'Service unavailable')

      # Fixed behavior: should rescue the error and still complete deactivation
      expect { user.deactivate! }.not_to raise_error
      expect(user.reload.deactivated_at).to be_present
    end
  end

  describe '#update_preferences' do
    let(:user) { create(:user, settings: { 'theme' => 'light' }) }

    
    # consistently string-typed after update
    it 'maintains consistent string keys after update' do
      user.update_preferences(notifications: false)

      # Fixed behavior: all keys should be strings (not a mix of symbols and strings)
      expect(user.settings.keys).to all(be_a(String))
      expect(user.settings.keys.map(&:class).uniq.size).to eq(1)
    end
  end
end
