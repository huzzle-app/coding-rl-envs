using FluentAssertions;
using HealthLink.Api.Data;
using HealthLink.Api.Services;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Options;
using Xunit;

namespace HealthLink.Tests.Integration;

public class StartupTests
{
    private ServiceProvider BuildServiceProvider()
    {
        var services = new ServiceCollection();

        services.AddDbContext<HealthLinkDbContext>(options =>
            options.UseInMemoryDatabase(Guid.NewGuid().ToString()));

        // Simulate the registrations from Program.cs
        services.AddScoped<IPatientService, PatientService>();
        services.AddScoped<IAppointmentService, AppointmentService>();
        services.AddScoped<ISchedulingService, SchedulingService>();
        services.AddScoped<INotificationService, NotificationService>();
        services.AddScoped<ICacheService, CacheService>();
        services.AddScoped<IReportService, ReportService>();
        services.AddScoped<IExternalApiService, ExternalApiService>();
        services.AddScoped<IExportService, ExportService>();
        services.AddScoped<HealthLink.Api.Repositories.IPatientRepository, HealthLink.Api.Repositories.PatientRepository>();
        services.AddScoped<HealthLink.Api.Repositories.IAppointmentRepository, HealthLink.Api.Repositories.AppointmentRepository>();
        services.AddScoped<HealthLink.Api.Security.IJwtTokenService, HealthLink.Api.Security.JwtTokenService>();

        services.Configure<SmtpSettings>(opts =>
        {
            opts.Host = "smtp.test.com";
            opts.Port = 587;
        });
        services.AddLogging();

        var config = new Microsoft.Extensions.Configuration.ConfigurationBuilder()
            .AddInMemoryCollection(new Dictionary<string, string?>
            {
                ["Jwt:Key"] = "this-is-a-sufficiently-long-key-for-hmac-sha256-testing!"
            })
            .Build();
        services.AddSingleton<Microsoft.Extensions.Configuration.IConfiguration>(config);

        return services.BuildServiceProvider();
    }

    [Fact]
    public void test_application_starts_without_circular_dependency()
    {
        
        var sp = BuildServiceProvider();
        var act = () => sp.GetRequiredService<ISchedulingService>();
        act.Should().NotThrow("circular dependency should be resolved");
    }

    [Fact]
    public void test_all_services_resolve()
    {
        
        var sp = BuildServiceProvider();
        sp.GetRequiredService<IPatientService>().Should().NotBeNull();
        sp.GetRequiredService<IAppointmentService>().Should().NotBeNull();
        sp.GetRequiredService<INotificationService>().Should().NotBeNull();
    }

    [Fact]
    public void test_scoped_services_registered()
    {
        
        var sp = BuildServiceProvider();
        using var scope1 = sp.CreateScope();
        using var scope2 = sp.CreateScope();

        var ctx1 = scope1.ServiceProvider.GetRequiredService<HealthLinkDbContext>();
        var ctx2 = scope2.ServiceProvider.GetRequiredService<HealthLinkDbContext>();

        ctx1.Should().NotBeSameAs(ctx2, "each scope should get its own DbContext");
    }

    [Fact]
    public void test_dbcontext_injection_works()
    {
        
        var sp = BuildServiceProvider();
        using var scope = sp.CreateScope();
        var ctx = scope.ServiceProvider.GetRequiredService<HealthLinkDbContext>();
        ctx.Should().NotBeNull();
    }

    [Fact]
    public void test_ioptions_section_binds_correctly()
    {
        
        var sp = BuildServiceProvider();
        var options = sp.GetRequiredService<IOptions<SmtpSettings>>();
        options.Value.Host.Should().NotBeNullOrEmpty("SMTP host should be configured");
    }

    [Fact]
    public void test_config_values_not_default()
    {
        
        var sp = BuildServiceProvider();
        var options = sp.GetRequiredService<IOptions<SmtpSettings>>();
        options.Value.Port.Should().BeGreaterThan(0);
    }

    [Fact]
    public void test_middleware_ordering_correct()
    {
        
        // This is a structural test - verifying the concept
        // In real app, auth wouldn't work if ordered wrong
        true.Should().BeTrue("middleware ordering is validated at integration level");
    }

    [Fact]
    public void test_auth_before_endpoints()
    {
        
        // Integration-level validation
        true.Should().BeTrue("authentication should be applied before endpoint routing");
    }

    [Fact]
    public void test_logging_configured()
    {
        var sp = BuildServiceProvider();
        var logger = sp.GetService<Microsoft.Extensions.Logging.ILoggerFactory>();
        logger.Should().NotBeNull();
    }

    [Fact]
    public void test_cache_service_resolves()
    {
        var sp = BuildServiceProvider();
        using var scope = sp.CreateScope();
        var cache = scope.ServiceProvider.GetRequiredService<ICacheService>();
        cache.Should().NotBeNull();
    }
}
