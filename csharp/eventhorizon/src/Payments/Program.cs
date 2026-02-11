var builder = WebApplication.CreateBuilder(args);
builder.Services.AddControllers();
builder.Services.AddScoped<EventHorizon.Payments.Services.IPaymentService, EventHorizon.Payments.Services.PaymentService>();
builder.Services.AddScoped<EventHorizon.Payments.Services.IRefundService, EventHorizon.Payments.Services.RefundService>();
var app = builder.Build();
app.MapControllers();
app.Run();
