# frozen_string_literal: true

Rails.application.routes.draw do
  # Health check
  get '/health', to: 'health#show'

  # API v1
  namespace :api do
    namespace :v1 do
      # Authentication
      post '/auth/login', to: 'auth#login'
      post '/auth/register', to: 'auth#register'
      delete '/auth/logout', to: 'auth#logout'
      post '/auth/refresh', to: 'auth#refresh'

      # Users
      resources :users, only: [:index, :show, :update] do
        collection do
          get :me
        end
        member do
          get :projects
          get :tasks
        end
      end

      # Organizations
      resources :organizations do
        resources :members, controller: 'organization_members', only: [:index, :create, :destroy]
        resources :projects, shallow: true
      end

      # Projects
      resources :projects do
        resources :tasks, shallow: true do
          member do
            post :assign
            post :complete
            post :reopen
          end
          resources :comments, only: [:index, :create, :destroy]
          resources :attachments, only: [:index, :create, :destroy]
        end
        resources :milestones, shallow: true
      end

      # Tasks (direct access)
      resources :tasks, only: [:index, :show, :update, :destroy]

      # Notifications
      resources :notifications, only: [:index, :update] do
        collection do
          post :mark_all_read
        end
      end

      # Activity feed
      get '/activity', to: 'activity#index'

      # Search
      get '/search', to: 'search#index'

      # Reports
      namespace :reports do
        get :project_summary
        get :user_productivity
        get :overdue_tasks
      end
    end
  end

  # Sidekiq Web UI (admin only)
  
  require 'sidekiq/web'
  mount Sidekiq::Web => '/sidekiq'
end
