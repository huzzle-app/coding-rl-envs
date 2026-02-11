var builder = WebApplication.CreateBuilder(args);
builder.Services.AddControllers();
builder.Services.AddScoped<EventHorizon.Search.Services.ISearchService, EventHorizon.Search.Services.SearchService>();
var app = builder.Build();
app.MapControllers();
app.Run();
