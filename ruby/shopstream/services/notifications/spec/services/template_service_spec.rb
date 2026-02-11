# frozen_string_literal: true

require 'rails_helper'

RSpec.describe TemplateService do
  

  describe '#render' do
    it 'renders template with variables' do
      service = described_class.new
      result = service.render(:order_confirmation, {
        customer_name: 'Alice',
        order_id: '12345',
        order_details: '2x Widget',
        total: '99.99'
      })

      expect(result[:subject]).to include('12345')
      expect(result[:body]).to include('Alice')
      expect(result[:body]).to include('99.99')
    end

    it 'does not modify the template constant' do
      service = described_class.new

      original_subject = TemplateService::TEMPLATES[:order_confirmation][:subject].dup
      original_body = TemplateService::TEMPLATES[:order_confirmation][:body].dup

      service.render(:order_confirmation, {
        customer_name: 'Bob',
        order_id: '999',
        order_details: 'stuff',
        total: '50.00'
      })

      # Template constants should be unmodified after render
      expect(TemplateService::TEMPLATES[:order_confirmation][:subject]).to eq(original_subject)
      expect(TemplateService::TEMPLATES[:order_confirmation][:body]).to eq(original_body)
    end

    it 'raises for unknown template' do
      service = described_class.new
      expect { service.render(:nonexistent, {}) }.to raise_error(/Template not found/)
    end
  end

  describe '#render_string' do
    it 'does not raise FrozenError when template is frozen' do
      service = described_class.new
      frozen_template = 'Hello {{name}}'.freeze

      expect {
        result = service.render_string(frozen_template, { name: 'World' })
        expect(result).to eq('Hello World')
      }.not_to raise_error
    end

    it 'handles multiple variable substitutions' do
      service = described_class.new
      template = '{{a}} and {{b}} and {{c}}'

      result = service.render_string(template, { a: '1', b: '2', c: '3' })
      expect(result).to eq('1 and 2 and 3')
    end
  end

  describe '#customize_template' do
    it 'does not modify the frozen TEMPLATES constant' do
      service = described_class.new

      expect {
        service.customize_template(:order_confirmation, { footer: 'Custom footer' })
      }.not_to raise_error

      # TEMPLATES should still be frozen and unmodified
      expect(TemplateService::TEMPLATES).to be_frozen
    end
  end

  describe '#build_greeting' do
    it 'does not modify the DEFAULT_GREETING constant' do
      service = described_class.new

      original = TemplateService::DEFAULT_GREETING.dup

      expect {
        service.build_greeting('Alice', :morning)
      }.not_to raise_error

      expect(TemplateService::DEFAULT_GREETING).to eq(original)
    end

    it 'returns proper greeting based on time of day' do
      service = described_class.new

      morning = service.build_greeting('Alice', :morning)
      expect(morning).to include('Alice')

      afternoon = service.build_greeting('Bob', :afternoon)
      expect(afternoon).to include('Bob')
    end

    it 'does not raise FrozenError on string concatenation' do
      service = described_class.new

      # Call multiple times to ensure constant is not mutated
      3.times do
        expect {
          service.build_greeting('Test', :evening)
        }.not_to raise_error
      end
    end
  end

  describe 'apply_defaults' do
    it 'does not mutate frozen input variables' do
      service = described_class.new
      variables = { customer_name: 'Alice' }.freeze

      expect {
        service.render(:order_confirmation, variables)
      }.not_to raise_error
    end
  end
end
