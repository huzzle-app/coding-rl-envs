# frozen_string_literal: true

class UserSerializer
  def initialize(user)
    @user = user
  end

  def as_json(_options = {})
    {
      id: @user.id,
      email: @user.email,
      name: @user.name,
      username: @user.username,
      avatar_url: @user.avatar_url,
      timezone: @user.timezone,
      admin: @user.admin
    }
  end
end
