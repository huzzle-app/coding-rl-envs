# frozen_string_literal: true

module ShopStream
  # Generic API client with method_missing for dynamic endpoints
  
  class ApiClient
    def initialize(service_name, base_url: nil)
      @service_name = service_name
      @base_url = base_url || discover_service(service_name)
      @http_client = HttpClient.new(@base_url)
    end

    
    # When a method doesn't exist and we try to call another missing method,
    # it recurses infinitely
    def method_missing(method_name, *args, **kwargs, &block)
      if method_name.to_s.start_with?('get_', 'find_', 'fetch_')
        resource = method_name.to_s.sub(/^(get_|find_|fetch_)/, '')
        get_resource(resource, *args, **kwargs)
      elsif method_name.to_s.start_with?('create_')
        resource = method_name.to_s.sub(/^create_/, '')
        create_resource(resource, *args, **kwargs)
      elsif method_name.to_s.start_with?('update_')
        resource = method_name.to_s.sub(/^update_/, '')
        update_resource(resource, *args, **kwargs)
      elsif method_name.to_s.start_with?('delete_')
        resource = method_name.to_s.sub(/^delete_/, '')
        delete_resource(resource, *args, **kwargs)
      else
        
        # triggering another method_missing call
        unknown_method(method_name, *args)
        # Should be: super
      end
    end

    def respond_to_missing?(method_name, include_private = false)
      method_name.to_s.match?(/^(get_|find_|fetch_|create_|update_|delete_)/) || super
    end

    private

    def get_resource(resource, id = nil, **params)
      path = id ? "/api/v1/#{resource}/#{id}" : "/api/v1/#{resource}"
      @http_client.get(path, params: params)
    end

    def create_resource(resource, **attributes)
      @http_client.post("/api/v1/#{resource}", body: attributes)
    end

    def update_resource(resource, id, **attributes)
      @http_client.put("/api/v1/#{resource}/#{id}", body: attributes)
    end

    def delete_resource(resource, id)
      @http_client.delete("/api/v1/#{resource}/#{id}")
    end

    def discover_service(service_name)
      # Would use service registry in production
      ENV["#{service_name.upcase}_SERVICE_URL"] || "http://#{service_name}:3000"
    end

    # Correct implementation:
    # def method_missing(method_name, *args, **kwargs, &block)
    #   if method_name.to_s.start_with?('get_', ...)
    #     # ... handle known patterns
    #   else
    #     super  # Properly delegate to parent
    #   end
    # end
  end
end
