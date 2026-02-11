namespace HealthLink.Api.Services;

public interface IExportService
{
    Task<byte[]> ExportToCsvAsync(IEnumerable<object> data);
}

public class CsvWriter : IAsyncDisposable, IDisposable
{
    private readonly StreamWriter _writer;
    private bool _disposed;

    public CsvWriter(Stream stream)
    {
        _writer = new StreamWriter(stream);
    }

    public async Task WriteLineAsync(string line)
    {
        await _writer.WriteLineAsync(line);
    }

    public async Task FlushAsync()
    {
        await _writer.FlushAsync();
    }

    public async ValueTask DisposeAsync()
    {
        if (!_disposed)
        {
            await _writer.FlushAsync();
            await _writer.DisposeAsync();
            _disposed = true;
        }
    }

    
    // When 'using' is used instead of 'await using', this is called
    // and async resources may not be properly flushed
    public void Dispose()
    {
        if (!_disposed)
        {
            _writer.Flush();
            _writer.Dispose();
            _disposed = true;
        }
    }
}

public class ExportService : IExportService
{
    public async Task<byte[]> ExportToCsvAsync(IEnumerable<object> data)
    {
        var stream = new MemoryStream();

        // === BUG D4: IAsyncDisposable not awaited ===
        // CsvWriter implements IAsyncDisposable but we're using regular 'using'
        // instead of 'await using'. The async disposal won't be awaited,
        // potentially leaving the stream unflushed.
        using (var writer = new CsvWriter(stream))
        {
            await writer.WriteLineAsync("Id,Name,Value");

            foreach (var item in data)
            {
                await writer.WriteLineAsync(item.ToString() ?? "");
            }

            await writer.FlushAsync();
        } 

        return stream.ToArray();
    }
}
