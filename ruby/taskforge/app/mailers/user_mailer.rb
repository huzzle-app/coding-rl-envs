# frozen_string_literal: true

class UserMailer < ApplicationMailer
  def confirmation_email(user)
    @user = user
    mail(to: user.email, subject: 'Confirm your TaskForge account')
  end
end
