var builder = WebApplication.CreateBuilder(args);
builder.Services.AddControllers();
builder.Services.AddScoped<EventHorizon.Auth.Services.IAuthService, EventHorizon.Auth.Services.AuthService>();
var app = builder.Build();
app.MapControllers();
app.Run();
