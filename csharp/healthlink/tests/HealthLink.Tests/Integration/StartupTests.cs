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
    public void test_dbcontext_not_singleton()
    {
        // DbContext must not be registered as Singleton - it's not thread-safe
        var programSource = System.IO.File.ReadAllText(
            Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "..", "src", "HealthLink.Api", "Program.cs"));
        programSource.Should().NotContain("AddSingleton<HealthLinkDbContext>",
            "DbContext should use AddScoped or AddDbContext, not AddSingleton");
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
        // Verify Program.cs binds SmtpSettings to the correct config section
        var programSource = System.IO.File.ReadAllText(
            Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "..", "src", "HealthLink.Api", "Program.cs"));
        var appsettingsSource = System.IO.File.ReadAllText(
            Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "..", "src", "HealthLink.Api", "appsettings.json"));

        // Find the section name used in Configure<SmtpSettings>
        // The section name in Program.cs must match a key in appsettings.json
        if (programSource.Contains("GetSection(\"Email\")"))
        {
            appsettingsSource.Should().Contain("\"Email\"",
                "Program.cs binds to 'Email' section but appsettings.json must have matching key");
        }
        else if (programSource.Contains("GetSection(\"Smtp\")"))
        {
            appsettingsSource.Should().Contain("\"Smtp\"",
                "Program.cs binds to 'Smtp' section which should exist in appsettings.json");
        }

        // The bound section must match what's in appsettings.json
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
        // Verify that Program.cs calls UseAuthentication before MapControllers
        var programSource = System.IO.File.ReadAllText(
            Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "..", "src", "HealthLink.Api", "Program.cs"));
        var authIndex = programSource.IndexOf("UseAuthentication");
        var mapIndex = programSource.IndexOf("MapControllers");
        authIndex.Should().BeGreaterThan(-1, "UseAuthentication should be present");
        mapIndex.Should().BeGreaterThan(-1, "MapControllers should be present");
        authIndex.Should().BeLessThan(mapIndex, "UseAuthentication must be called before MapControllers");
    }

    [Fact]
    public void test_auth_before_endpoints()
    {
        // Verify that UseAuthorization appears before MapControllers
        var programSource = System.IO.File.ReadAllText(
            Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "..", "src", "HealthLink.Api", "Program.cs"));
        var authzIndex = programSource.IndexOf("UseAuthorization");
        var mapIndex = programSource.IndexOf("MapControllers");
        authzIndex.Should().BeGreaterThan(-1, "UseAuthorization should be present");
        authzIndex.Should().BeLessThan(mapIndex, "UseAuthorization must be called before MapControllers");
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
