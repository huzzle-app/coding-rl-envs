Rails.application.routes.draw do
  namespace :api do
    namespace :v1 do
      # Add routes here
    end
  end

  get '/health', to: 'health#show'
end
