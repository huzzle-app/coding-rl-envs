var builder = WebApplication.CreateBuilder(args);
builder.Services.AddControllers();
builder.Services.AddScoped<EventHorizon.Venues.Services.IVenueService, EventHorizon.Venues.Services.VenueService>();
var app = builder.Build();
app.MapControllers();
app.Run();
