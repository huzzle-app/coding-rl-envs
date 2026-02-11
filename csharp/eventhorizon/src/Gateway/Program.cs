var builder = WebApplication.CreateBuilder(args);

// === BUG I5: CORS wildcard allows any origin ===
builder.Services.AddCors(options =>
{
    options.AddDefaultPolicy(policy =>
    {
        policy.AllowAnyOrigin()  
              .AllowAnyMethod()
              .AllowAnyHeader();
    });
});

builder.Services.AddControllers();
builder.Services.AddSingleton<EventHorizon.Gateway.Services.IRateLimiterService, EventHorizon.Gateway.Services.RateLimiterService>();

var app = builder.Build();
app.UseCors();
app.MapControllers();
app.Run();
