class ApplicationController < ActionController::API
  before_action :authenticate!

  private

  def authenticate!
    # Authentication logic would go here
    # For now, no-op to allow tests to run
  end

  def current_user
    @current_user
  end
end
