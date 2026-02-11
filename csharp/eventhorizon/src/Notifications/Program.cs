var builder = WebApplication.CreateBuilder(args);
builder.Services.AddControllers();
builder.Services.AddScoped<EventHorizon.Notifications.Services.INotificationService, EventHorizon.Notifications.Services.NotificationService>();
builder.Services.AddSingleton<EventHorizon.Notifications.Hubs.NotificationHub>();
builder.Services.AddSingleton<EventHorizon.Notifications.Hubs.HubNotificationSender>();
var app = builder.Build();
app.MapControllers();
app.Run();
