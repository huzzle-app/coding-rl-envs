using HealthLink.Api.Data;
using HealthLink.Api.Models;
using HealthLink.Api.Repositories;
using HealthLink.Api.Security;
using HealthLink.Api.Services;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.EntityFrameworkCore;
using Microsoft.IdentityModel.Tokens;
using System.Text;

var builder = WebApplication.CreateBuilder(args);

// === BUG L2: AddSingleton instead of AddScoped for DbContext ===
// DbContext is NOT thread-safe and should be scoped per-request
builder.Services.AddSingleton<HealthLinkDbContext>(sp =>
{
    var options = new DbContextOptionsBuilder<HealthLinkDbContext>()
        .UseNpgsql(builder.Configuration.GetConnectionString("DefaultConnection"))
        .Options;
    return new HealthLinkDbContext(options);
});

// === BUG L3: IOptions section mismatch ===
// appsettings.json has "Smtp" section, but we bind to "Email"
builder.Services.Configure<SmtpSettings>(builder.Configuration.GetSection("Email"));

// Service registrations
builder.Services.AddScoped<IPatientService, PatientService>();
builder.Services.AddScoped<IAppointmentService, AppointmentService>();
builder.Services.AddScoped<ISchedulingService, SchedulingService>();
builder.Services.AddScoped<INotificationService, NotificationService>();
builder.Services.AddScoped<ICacheService, CacheService>();
builder.Services.AddScoped<IReportService, ReportService>();
builder.Services.AddScoped<IExternalApiService, ExternalApiService>();
builder.Services.AddScoped<IExportService, ExportService>();
builder.Services.AddScoped<IPatientRepository, PatientRepository>();
builder.Services.AddScoped<IAppointmentRepository, AppointmentRepository>();
builder.Services.AddScoped<IJwtTokenService, JwtTokenService>();

// Authentication
var jwtKey = builder.Configuration["Jwt:Key"] ?? "short";
builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(options =>
    {
        options.TokenValidationParameters = new TokenValidationParameters
        {
            ValidateIssuerSigningKey = true,
            IssuerSigningKey = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(jwtKey)),
            ValidateIssuer = false,
            ValidateAudience = false,
        };
    });

builder.Services.AddAuthorization();
builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();
builder.Services.AddHttpClient();
builder.Services.AddMediatR(cfg => cfg.RegisterServicesFromAssembly(typeof(Program).Assembly));

var app = builder.Build();

if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

app.UseHttpsRedirection();

// === BUG L4: Middleware ordering wrong ===
// MapControllers() BEFORE UseAuthentication/UseAuthorization
// Authentication middleware won't run for controller endpoints
app.MapControllers();
app.UseAuthentication();
app.UseAuthorization();

app.Run();
