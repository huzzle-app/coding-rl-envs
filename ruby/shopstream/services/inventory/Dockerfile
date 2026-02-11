FROM ruby:3.2.2-alpine

RUN apk add --no-cache \
    build-base \
    postgresql-dev \
    nodejs \
    tzdata \
    git

WORKDIR /app

COPY shared /app/shared

COPY services/inventory/Gemfile ./
RUN bundle install --jobs 4 --retry 3

COPY services/inventory/ .

EXPOSE 3000

CMD ["bundle", "exec", "rails", "server", "-b", "0.0.0.0"]
