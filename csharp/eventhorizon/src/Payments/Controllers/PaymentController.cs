using EventHorizon.Shared.Models;
using Microsoft.AspNetCore.Mvc;

namespace EventHorizon.Payments.Controllers;

[ApiController]
[Route("api/[controller]")]
public class PaymentController : ControllerBase
{
    private readonly Services.IPaymentService _paymentService;

    public PaymentController(Services.IPaymentService paymentService)
    {
        _paymentService = paymentService;
    }

    [HttpPost]
    public async Task<IActionResult> ProcessPayment([FromBody] PaymentRequest request)
    {
        var result = await _paymentService.ProcessPaymentAsync(request.OrderId, new Money(request.Amount, "USD"));
        return result.Success ? Ok(result) : BadRequest(result);
    }
}

public record PaymentRequest(string OrderId, float Amount);
