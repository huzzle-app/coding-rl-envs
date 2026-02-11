# frozen_string_literal: true

class ApplicationMailer < ActionMailer::Base
  default from: 'noreply@taskforge.example.com'
  layout 'mailer'
end
