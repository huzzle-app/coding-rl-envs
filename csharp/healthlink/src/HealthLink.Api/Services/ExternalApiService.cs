namespace HealthLink.Api.Services;

public interface IExternalApiService
{
    Task<string?> GetInsuranceVerificationAsync(string patientId);
    Task<string?> GetLabResultsAsync(string orderId);
}

public class ExternalApiService : IExternalApiService
{
    private readonly ILogger<ExternalApiService> _logger;

    public ExternalApiService(ILogger<ExternalApiService> logger)
    {
        _logger = logger;
    }

    public async Task<string?> GetInsuranceVerificationAsync(string patientId)
    {
        // === BUG D3: new HttpClient() per request causes socket exhaustion ===
        // Each HttpClient instance holds sockets that won't be released immediately
        // due to TIME_WAIT state. Should use IHttpClientFactory instead.
        using var client = new HttpClient();
        client.BaseAddress = new Uri("https://insurance-api.example.com");

        try
        {
            var response = await client.GetStringAsync($"/verify/{patientId}");
            return response;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Insurance verification failed for {PatientId}", patientId);
            return null;
        }
    }

    public async Task<string?> GetLabResultsAsync(string orderId)
    {
        // Same bug - new HttpClient per request
        using var client = new HttpClient();
        client.BaseAddress = new Uri("https://lab-api.example.com");

        try
        {
            var response = await client.GetStringAsync($"/results/{orderId}");
            return response;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Lab results fetch failed for {OrderId}", orderId);
            return null;
        }
    }
}
