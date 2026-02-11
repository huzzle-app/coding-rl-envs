var builder = WebApplication.CreateBuilder(args);
builder.Services.AddControllers();
builder.Services.AddScoped<EventHorizon.Orders.Services.IOrderService, EventHorizon.Orders.Services.OrderService>();
builder.Services.AddScoped<EventHorizon.Orders.Services.IOrderSagaService, EventHorizon.Orders.Services.OrderSagaService>();
var app = builder.Build();
app.MapControllers();
app.Run();
