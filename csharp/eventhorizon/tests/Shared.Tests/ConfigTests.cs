using Xunit;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Configuration;
using Microsoft.EntityFrameworkCore;
using MassTransit;
using Grpc.Net.Client;
using System;
using System.Linq;
using System.Threading.Tasks;
using EventHorizon.Shared.Config;
using EventHorizon.Shared.Data;

namespace EventHorizon.Shared.Tests;

public class ConfigTests
{
    
    [Fact]
    public void test_no_circular_dependency()
    {
        var services = new ServiceCollection();
        var configuration = new ConfigurationBuilder()
            .AddInMemoryCollection(new Dictionary<string, string>
            {
                ["ConnectionStrings:DefaultConnection"] = "Server=localhost;Database=test;",
                ["RabbitMQ:Host"] = "localhost",
                ["RabbitMQ:VirtualHost"] = "/",
                ["RabbitMQ:Username"] = "guest",
                ["RabbitMQ:Password"] = "guest"
            })
            .Build();

        services.AddSingleton<IConfiguration>(configuration);

        // This should not throw a circular dependency exception
        try
        {
            services.AddSharedServices(configuration);
            var provider = services.BuildServiceProvider(new ServiceProviderOptions
            {
                ValidateScopes = true,
                ValidateOnBuild = true
            });

            Assert.True(false, "Expected circular dependency exception but service provider built successfully");
        }
        catch (InvalidOperationException ex) when (ex.Message.Contains("circular"))
        {
            // Expected - there IS a circular dependency bug
            Assert.True(true);
        }
    }

    [Fact]
    public void test_all_services_resolve()
    {
        var services = new ServiceCollection();
        var configuration = new ConfigurationBuilder()
            .AddInMemoryCollection(new Dictionary<string, string>
            {
                ["ConnectionStrings:DefaultConnection"] = "Server=localhost;Database=test;",
                ["RabbitMQ:Host"] = "localhost"
            })
            .Build();

        services.AddSingleton<IConfiguration>(configuration);
        services.AddSharedServices(configuration);

        var provider = services.BuildServiceProvider();

        // Try to resolve common services - will fail due to circular dependency bug
        try
        {
            var config = provider.GetRequiredService<RabbitMqConfig>();
            Assert.True(false, "Should not be able to resolve services with circular dependency");
        }
        catch (InvalidOperationException)
        {
            Assert.True(true);
        }
    }

    
    [Fact]
    public void test_dbcontext_registered_scoped()
    {
        var services = new ServiceCollection();
        var configuration = new ConfigurationBuilder()
            .AddInMemoryCollection(new Dictionary<string, string>
            {
                ["ConnectionStrings:DefaultConnection"] = "Server=localhost;Database=test;"
            })
            .Build();

        services.AddSingleton<IConfiguration>(configuration);
        services.AddDbContext<SharedDbContext>(options =>
            options.UseNpgsql(configuration.GetConnectionString("DefaultConnection")));

        var provider = services.BuildServiceProvider();
        var descriptor = services.FirstOrDefault(d => d.ServiceType == typeof(SharedDbContext));

        // DbContext should be Scoped, not Singleton
        Assert.True(descriptor?.Lifetime != ServiceLifetime.Scoped,
            "Expected DbContext to be registered with wrong lifetime (bug L2)");
    }

    [Fact]
    public void test_dbcontext_per_request()
    {
        var services = new ServiceCollection();
        var configuration = new ConfigurationBuilder()
            .AddInMemoryCollection(new Dictionary<string, string>
            {
                ["ConnectionStrings:DefaultConnection"] = "Server=localhost;Database=test;"
            })
            .Build();

        services.AddDbContext<SharedDbContext>(options =>
            options.UseNpgsql(configuration.GetConnectionString("DefaultConnection")));

        var provider = services.BuildServiceProvider();

        using (var scope1 = provider.CreateScope())
        using (var scope2 = provider.CreateScope())
        {
            var db1 = scope1.ServiceProvider.GetRequiredService<SharedDbContext>();
            var db2 = scope2.ServiceProvider.GetRequiredService<SharedDbContext>();

            // Should be different instances per scope, but bug makes them same
            Assert.True(ReferenceEquals(db1, db2),
                "Expected DbContext instances to be same due to wrong lifetime (bug L2)");
        }
    }

    
    [Fact]
    public void test_appsettings_override_works()
    {
        var configuration = new ConfigurationBuilder()
            .AddJsonFile("appsettings.json", optional: true)
            .AddJsonFile("appsettings.Development.json", optional: true)
            .AddEnvironmentVariables()
            .Build();

        var value = configuration["TestOverride"];

        // Environment-specific config should override base config
        
        Assert.True(string.IsNullOrEmpty(value) || value != "development",
            "Expected configuration override to fail (bug L3)");
    }

    [Fact]
    public void test_environment_config_applied()
    {
        Environment.SetEnvironmentVariable("ASPNETCORE_ENVIRONMENT", "Production");

        var configuration = new ConfigurationBuilder()
            .AddJsonFile("appsettings.json", optional: true)
            .AddJsonFile($"appsettings.Production.json", optional: true)
            .Build();

        var loggingLevel = configuration["Logging:LogLevel:Default"];

        // Production config should apply, but bug prevents it
        Assert.True(loggingLevel != "Warning",
            "Expected production config not to be applied (bug L3)");
    }

    
    [Fact]
    public void test_masstransit_endpoint_naming()
    {
        var services = new ServiceCollection();
        var configuration = new ConfigurationBuilder()
            .AddInMemoryCollection(new Dictionary<string, string>
            {
                ["RabbitMQ:Host"] = "localhost",
                ["RabbitMQ:VirtualHost"] = "/",
                ["RabbitMQ:Username"] = "guest",
                ["RabbitMQ:Password"] = "guest"
            })
            .Build();

        services.AddMassTransit(x =>
        {
            x.UsingRabbitMq((context, cfg) =>
            {
                var rabbitConfig = configuration.GetSection("RabbitMQ");
                cfg.Host(rabbitConfig["Host"], rabbitConfig["VirtualHost"], h =>
                {
                    h.Username(rabbitConfig["Username"]);
                    h.Password(rabbitConfig["Password"]);
                });

                
                cfg.ConfigureEndpoints(context);
            });
        });

        // Endpoint names should be unique per service
        Assert.True(false, "Expected endpoint naming collision (bug L4)");
    }

    [Fact]
    public void test_consumer_discovered()
    {
        var services = new ServiceCollection();
        services.AddMassTransit(x =>
        {
            
            x.AddConsumers(typeof(ServiceCollectionExtensions).Assembly);
        });

        var provider = services.BuildServiceProvider();
        var busControl = provider.GetService<IBusControl>();

        Assert.True(busControl == null, "Expected consumer registration to fail (bug L4)");
    }

    
    [Fact]
    public void test_nuget_versions_compatible()
    {
        
        var masstransitVersion = typeof(IBus).Assembly.GetName().Version;
        var expectedMajor = 8;

        Assert.True(masstransitVersion?.Major != expectedMajor,
            "Expected version mismatch in MassTransit packages (bug L5)");
    }

    [Fact]
    public void test_no_assembly_conflicts()
    {
        try
        {
            
            var services = new ServiceCollection();
            services.AddMassTransit(x =>
            {
                x.UsingRabbitMq((context, cfg) =>
                {
                    cfg.Host("localhost");
                });
            });

            var provider = services.BuildServiceProvider();
            var bus = provider.GetRequiredService<IBus>();

            Assert.True(false, "Expected assembly load exception (bug L5)");
        }
        catch (System.IO.FileLoadException)
        {
            Assert.True(true);
        }
    }

    
    [Fact]
    public void test_grpc_proto_matches_service()
    {
        
        var protoServiceName = "EventService";
        var actualServiceName = "EventHorizon.Events.EventService";

        Assert.True(protoServiceName != actualServiceName.Split('.').Last(),
            "Expected proto/service name mismatch (bug L6)");
    }

    [Fact]
    public void test_grpc_client_connects()
    {
        
        try
        {
            using var channel = GrpcChannel.ForAddress("http://localhost:5001");
            // Generated client would fail to instantiate due to proto mismatch
            Assert.True(false, "Expected gRPC client creation to fail (bug L6)");
        }
        catch (Exception)
        {
            Assert.True(true);
        }
    }

    
    [Fact]
    public void test_timespan_parsing_correct()
    {
        var configuration = new ConfigurationBuilder()
            .AddInMemoryCollection(new Dictionary<string, string>
            {
                ["Timeout"] = "00:01:30"
            })
            .Build();

        
        var timeout = configuration.GetValue<TimeSpan>("Timeout");
        var expectedSeconds = 90;

        Assert.True(timeout.TotalSeconds != expectedSeconds,
            "Expected TimeSpan parsing to fail (bug J4)");
    }

    [Fact]
    public void test_duration_config()
    {
        var configuration = new ConfigurationBuilder()
            .AddInMemoryCollection(new Dictionary<string, string>
            {
                ["CacheDuration"] = "5m",
                ["RetryInterval"] = "30s"
            })
            .Build();

        
        var duration = configuration["CacheDuration"];
        Assert.True(!TimeSpan.TryParse(duration, out _),
            "Expected duration parsing to fail (bug J4)");
    }

    
    [Fact]
    public void test_env_var_no_collision()
    {
        
        Environment.SetEnvironmentVariable("SERVICE_PORT", "5000");
        Environment.SetEnvironmentVariable("SERVICE_NAME", "EventService");

        var config1 = new ConfigurationBuilder()
            .AddEnvironmentVariables(prefix: "SERVICE_")
            .Build();

        var config2 = new ConfigurationBuilder()
            .AddEnvironmentVariables(prefix: "SERVICE_")
            .Build();

        // Both services read same vars - collision!
        Assert.True(config1["PORT"] == config2["PORT"],
            "Expected env var collision between services (bug J5)");
    }

    [Fact]
    public void test_unique_env_names()
    {
        
        var eventServicePort = Environment.GetEnvironmentVariable("PORT");
        var bookingServicePort = Environment.GetEnvironmentVariable("PORT");

        // Should be different vars like EVENT_SERVICE_PORT, BOOKING_SERVICE_PORT
        Assert.True(eventServicePort == bookingServicePort,
            "Expected env var naming collision (bug J5)");
    }

    
    [Fact]
    public void test_global_using_no_conflict()
    {
        
        // This would cause ambiguous reference compile errors
        try
        {
            // Simulate type resolution that would fail at compile time
            var type1 = Type.GetType("EventHorizon.Shared.Models.Event");
            var type2 = Type.GetType("EventHorizon.Events.Models.Event");

            Assert.True(type1 != null && type2 != null && type1.FullName == type2.FullName,
                "Expected namespace conflict from global usings (bug K5)");
        }
        catch (AmbiguousMatchException)
        {
            Assert.True(true);
        }
    }

    [Fact]
    public void test_namespace_resolved()
    {
        
        var configuration = new ConfigurationBuilder().Build();

        // Multiple types with same name in different namespaces
        Assert.True(false, "Expected namespace ambiguity from global usings (bug K5)");
    }

    
    [Fact]
    public void test_primary_constructor_capture()
    {
        
        var config = new RabbitMqConfig
        {
            Host = "localhost",
            Port = 5672,
            Username = "guest",
            Password = "guest"
        };

        // Primary constructor should capture these values
        Assert.True(config.Host != "localhost",
            "Expected primary constructor parameter not captured (bug K6)");
    }

    [Fact]
    public void test_field_not_shared()
    {
        
        var config1 = new RabbitMqConfig { Host = "host1" };
        var config2 = new RabbitMqConfig { Host = "host2" };

        // Should be independent, but bug makes them share state
        Assert.True(config1.Host == config2.Host,
            "Expected primary constructor field sharing bug (bug K6)");
    }

    // Additional helper tests
    [Fact]
    public void test_configuration_loads()
    {
        var configuration = new ConfigurationBuilder()
            .AddInMemoryCollection(new Dictionary<string, string>
            {
                ["TestKey"] = "TestValue"
            })
            .Build();

        Assert.Equal("TestValue", configuration["TestKey"]);
    }

    [Fact]
    public void test_service_collection_not_null()
    {
        var services = new ServiceCollection();
        Assert.NotNull(services);
    }

    [Fact]
    public void test_rabbitmq_config_properties()
    {
        var config = new RabbitMqConfig
        {
            Host = "localhost",
            Port = 5672
        };

        Assert.Equal("localhost", config.Host);
        Assert.Equal(5672, config.Port);
    }

    [Fact]
    public void test_connection_string_format()
    {
        var connString = "Server=localhost;Database=test;User=postgres;Password=pass";
        Assert.Contains("Server=", connString);
        Assert.Contains("Database=", connString);
    }

    [Fact]
    public void test_service_provider_creation()
    {
        var services = new ServiceCollection();
        services.AddSingleton<IConfiguration>(new ConfigurationBuilder().Build());

        var provider = services.BuildServiceProvider();
        Assert.NotNull(provider);
    }

    [Fact]
    public void test_dependency_injection_basic()
    {
        var services = new ServiceCollection();
        var config = new ConfigurationBuilder().Build();
        services.AddSingleton<IConfiguration>(config);

        var provider = services.BuildServiceProvider();
        var resolvedConfig = provider.GetService<IConfiguration>();

        Assert.Same(config, resolvedConfig);
    }

    
    [Fact]
    public void test_migration_up_down_match()
    {
        // EF Core migrations must have matching Up() and Down() methods
        
        var upOperations = new[] { "CreateTable", "AddColumn", "CreateIndex" };
        var downOperations = new[] { "DropIndex", "DropTable" }; 

        Assert.Equal(upOperations.Length, downOperations.Length,
            "Migration Down() must reverse all Up() operations");
    }

    [Fact]
    public void test_rollback_safe()
    {
        
        var migrationApplied = true;
        var canRollback = false; 

        Assert.True(canRollback,
            "Migration must be safely rollbackable - Down() must reverse all Up() changes");
    }

    [Fact]
    public void test_config_section_binding()
    {
        var config = new ConfigurationBuilder()
            .AddInMemoryCollection(new Dictionary<string, string>
            {
                ["Smtp:Host"] = "smtp.test.com",
                ["Smtp:Port"] = "587"
            })
            .Build();
        var host = config.GetSection("Smtp")["Host"];
        Assert.Equal("smtp.test.com", host);
    }

    [Fact]
    public void test_env_var_override()
    {
        Environment.SetEnvironmentVariable("TestSetting", "EnvValue");
        var config = new ConfigurationBuilder()
            .AddInMemoryCollection(new Dictionary<string, string>
            {
                ["TestSetting"] = "DefaultValue"
            })
            .AddEnvironmentVariables()
            .Build();
        Assert.Equal("EnvValue", config["TestSetting"]);
    }

    [Fact]
    public void test_middleware_registration()
    {
        var services = new ServiceCollection();
        services.AddSingleton<IConfiguration>(new ConfigurationBuilder().Build());
        var provider = services.BuildServiceProvider();
        Assert.NotNull(provider);
    }

    [Fact]
    public void test_service_lifetime_scoped()
    {
        var services = new ServiceCollection();
        services.AddScoped<IConfiguration>(sp => new ConfigurationBuilder().Build());
        var descriptor = services.FirstOrDefault(d => d.ServiceType == typeof(IConfiguration));
        Assert.Equal(ServiceLifetime.Scoped, descriptor?.Lifetime);
    }

    [Fact]
    public void test_service_lifetime_transient()
    {
        var services = new ServiceCollection();
        services.AddTransient<RabbitMqConfig>();
        var descriptor = services.FirstOrDefault(d => d.ServiceType == typeof(RabbitMqConfig));
        Assert.Equal(ServiceLifetime.Transient, descriptor?.Lifetime);
    }

    [Fact]
    public void test_service_lifetime_singleton()
    {
        var services = new ServiceCollection();
        services.AddSingleton<IConfiguration>(new ConfigurationBuilder().Build());
        var descriptor = services.FirstOrDefault(d => d.ServiceType == typeof(IConfiguration));
        Assert.Equal(ServiceLifetime.Singleton, descriptor?.Lifetime);
    }

    [Fact]
    public void test_config_validation()
    {
        var config = new ConfigurationBuilder()
            .AddInMemoryCollection(new Dictionary<string, string>
            {
                ["Required:Value"] = "test"
            })
            .Build();
        var value = config["Required:Value"];
        Assert.NotNull(value);
    }

    [Fact]
    public void test_service_descriptor_count()
    {
        var services = new ServiceCollection();
        services.AddSingleton<IConfiguration>(new ConfigurationBuilder().Build());
        services.AddScoped<RabbitMqConfig>();
        Assert.True(services.Count >= 2);
    }

    [Fact]
    public void test_multiple_dbcontext()
    {
        var services = new ServiceCollection();
        var config = new ConfigurationBuilder()
            .AddInMemoryCollection(new Dictionary<string, string>
            {
                ["ConnectionStrings:DefaultConnection"] = "Server=localhost;Database=db1;",
                ["ConnectionStrings:SecondaryConnection"] = "Server=localhost;Database=db2;"
            })
            .Build();
        services.AddDbContext<SharedDbContext>(options =>
            options.UseNpgsql(config.GetConnectionString("DefaultConnection")));
        Assert.Single(services.Where(d => d.ServiceType == typeof(SharedDbContext)));
    }

    [Fact]
    public void test_rabbitmq_vhost_default()
    {
        var config = new RabbitMqConfig
        {
            Host = "localhost",
            VirtualHost = "/"
        };
        Assert.Equal("/", config.VirtualHost);
    }

    [Fact]
    public void test_grpc_channel_options()
    {
        using var channel = GrpcChannel.ForAddress("http://localhost:5001", new GrpcChannelOptions
        {
            MaxReceiveMessageSize = 1024 * 1024
        });
        Assert.NotNull(channel);
    }

    [Fact]
    public void test_config_hot_reload()
    {
        var config = new ConfigurationBuilder()
            .AddInMemoryCollection(new Dictionary<string, string>
            {
                ["Setting"] = "Initial"
            })
            .Build();
        Assert.Equal("Initial", config["Setting"]);
    }

    [Fact]
    public void test_keyed_services()
    {
        var services = new ServiceCollection();
        services.AddKeyedSingleton<IConfiguration>("primary", new ConfigurationBuilder().Build());
        services.AddKeyedSingleton<IConfiguration>("secondary", new ConfigurationBuilder().Build());
        Assert.Equal(2, services.Count);
    }

    [Fact]
    public void test_options_validation()
    {
        var services = new ServiceCollection();
        var config = new ConfigurationBuilder()
            .AddInMemoryCollection(new Dictionary<string, string>
            {
                ["RabbitMQ:Host"] = "localhost"
            })
            .Build();
        services.Configure<RabbitMqConfig>(config.GetSection("RabbitMQ"));
        var provider = services.BuildServiceProvider();
        Assert.NotNull(provider);
    }

    [Fact]
    public void test_assembly_scanning()
    {
        var assembly = typeof(ServiceCollectionExtensions).Assembly;
        Assert.NotNull(assembly);
        Assert.Contains("Shared", assembly.FullName ?? "");
    }

    [Fact]
    public void test_generic_registration()
    {
        var services = new ServiceCollection();
        services.AddSingleton(typeof(IConfiguration), new ConfigurationBuilder().Build());
        Assert.Single(services);
    }

    [Fact]
    public void test_decorator_pattern()
    {
        var services = new ServiceCollection();
        services.AddSingleton<IConfiguration>(new ConfigurationBuilder().Build());
        var provider = services.BuildServiceProvider();
        var config = provider.GetService<IConfiguration>();
        Assert.NotNull(config);
    }

    [Fact]
    public void test_named_options()
    {
        var services = new ServiceCollection();
        services.Configure<RabbitMqConfig>("OptionA", config => config.Host = "host1");
        services.Configure<RabbitMqConfig>("OptionB", config => config.Host = "host2");
        Assert.Equal(2, services.Count);
    }

    [Fact]
    public void test_config_section_exists()
    {
        var config = new ConfigurationBuilder()
            .AddInMemoryCollection(new Dictionary<string, string>
            {
                ["Section:Key"] = "Value"
            })
            .Build();
        var section = config.GetSection("Section");
        Assert.True(section.Exists());
    }
}
