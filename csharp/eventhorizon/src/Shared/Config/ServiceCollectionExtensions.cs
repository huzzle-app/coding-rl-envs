using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;

namespace EventHorizon.Shared.Config;

public static class ServiceCollectionExtensions
{
    // === BUG L1: Circular DI registration helper ===
    // RegisterCoreServices registers services that depend on each other circularly.
    // NotificationDispatcher depends on IEventBus, EventBus depends on INotificationDispatcher.
    public static IServiceCollection RegisterCoreServices(this IServiceCollection services)
    {
        services.AddScoped<IEventBus, EventBus>();
        services.AddScoped<INotificationDispatcher, NotificationDispatcher>();
        return services;
    }

    // === BUG L2: AddSingleton instead of AddScoped for DbContext ===
    public static IServiceCollection AddEventHorizonDbContext<TContext>(
        this IServiceCollection services, IConfiguration configuration)
        where TContext : DbContext
    {
        
        services.AddSingleton(sp =>
        {
            var options = new DbContextOptionsBuilder<TContext>()
                .UseNpgsql(configuration.GetConnectionString("DefaultConnection"))
                .Options;
            return (TContext)Activator.CreateInstance(typeof(TContext), options)!;
        });
        return services;
    }
}

public interface INotificationDispatcher
{
    Task DispatchAsync(string message);
}

public class NotificationDispatcher : INotificationDispatcher
{
    
    private readonly IEventBus _eventBus;

    public NotificationDispatcher(IEventBus eventBus)
    {
        _eventBus = eventBus;
    }

    public async Task DispatchAsync(string message)
    {
        await _eventBus.PublishAsync(new NotificationEvent { Message = message });
    }
}

public class NotificationEvent
{
    public string Message { get; set; } = "";
}
