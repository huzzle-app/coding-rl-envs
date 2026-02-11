var builder = WebApplication.CreateBuilder(args);
builder.Services.AddControllers();
builder.Services.AddScoped<EventHorizon.Tickets.Services.ITicketInventoryService, EventHorizon.Tickets.Services.TicketInventoryService>();
builder.Services.AddScoped<EventHorizon.Tickets.Services.ISeatMapService, EventHorizon.Tickets.Services.SeatMapService>();
var app = builder.Build();
app.MapControllers();
app.Run();
