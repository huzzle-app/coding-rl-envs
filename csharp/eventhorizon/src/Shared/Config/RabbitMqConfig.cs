using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;

namespace EventHorizon.Shared.Config;

public class RabbitMqSettings
{
    public string Host { get; set; } = "localhost";
    public string Username { get; set; } = "guest";
    public string Password { get; set; } = "guest";
    public int Port { get; set; } = 5672;
}

public static class RabbitMqConfig
{
    // === BUG L4: MassTransit endpoint naming convention wrong ===
    // MassTransit uses kebab-case by default for endpoint names,
    // but we're configuring PascalCase which causes consumers to not be discovered
    public static IServiceCollection AddRabbitMqMessaging(
        this IServiceCollection services, IConfiguration configuration)
    {
        services.Configure<RabbitMqSettings>(configuration.GetSection("RabbitMq"));
        // In real code, MassTransit.AddMassTransit would be here
        
        return services;
    }
}
