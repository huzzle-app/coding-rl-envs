var builder = WebApplication.CreateBuilder(args);
builder.Services.AddControllers();
builder.Services.AddScoped<EventHorizon.Analytics.Services.IAnalyticsService, EventHorizon.Analytics.Services.AnalyticsService>();
builder.Services.Configure<EventHorizon.Analytics.Controllers.AnalyticsSettings>(
    builder.Configuration.GetSection("Analytics"));
var app = builder.Build();
app.MapControllers();
app.Run();
