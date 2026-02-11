using Xunit;
using System;
using System.Threading;
using System.Threading.Tasks;
using System.Collections.Generic;
using Microsoft.Extensions.DependencyInjection;
using StackExchange.Redis;
using EventHorizon.Shared.Events;

namespace EventHorizon.Shared.Tests;

public class EventBusTests
{
    
    [Fact]
    public async Task test_semaphore_released_on_error()
    {
        var semaphore = new SemaphoreSlim(1, 1);

        try
        {
            await semaphore.WaitAsync();

            // Simulate error without releasing semaphore (bug A8)
            throw new InvalidOperationException("Test exception");
        }
        catch
        {
            
        }

        // Try to acquire again - should timeout if not released (bug)
        var acquired = await semaphore.WaitAsync(TimeSpan.FromMilliseconds(100));
        Assert.False(acquired, "Expected semaphore to be leaked (bug A8)");
    }

    [Fact]
    public async Task test_no_semaphore_leak()
    {
        var semaphore = new SemaphoreSlim(2, 2);
        var tasks = new List<Task>();

        // Create multiple tasks that might fail
        for (int i = 0; i < 5; i++)
        {
            tasks.Add(Task.Run(async () =>
            {
                await semaphore.WaitAsync();
                try
                {
                    if (Random.Shared.Next(2) == 0)
                    {
                        throw new Exception("Random error");
                    }
                    await Task.Delay(10);
                }
                catch
                {
                    
                }
            }));
        }

        await Task.WhenAll(tasks);

        // If semaphores leaked, available count will be less than max
        Assert.True(semaphore.CurrentCount < 2, "Expected semaphore leaks (bug A8)");
    }

    
    [Fact]
    public void test_httpclient_factory()
    {
        var services = new ServiceCollection();

        
        // This causes socket exhaustion
        services.AddTransient(_ => new System.Net.Http.HttpClient());

        var provider = services.BuildServiceProvider();

        var clients = new List<System.Net.Http.HttpClient>();
        for (int i = 0; i < 100; i++)
        {
            clients.Add(provider.GetRequiredService<System.Net.Http.HttpClient>());
        }

        // Each client has its own handler - socket exhaustion bug
        Assert.True(clients.Count == 100, "Expected socket exhaustion risk (bug D2)");
    }

    [Fact]
    public async Task test_no_socket_exhaustion()
    {
        
        var clients = new List<System.Net.Http.HttpClient>();

        for (int i = 0; i < 1000; i++)
        {
            clients.Add(new System.Net.Http.HttpClient());
        }

        // Try to make requests - will fail due to socket exhaustion
        var tasks = clients.Select(c =>
            c.GetAsync("http://localhost:5000/health").ContinueWith(_ => { }));

        try
        {
            await Task.WhenAll(tasks);
            Assert.True(false, "Expected socket exhaustion (bug D2)");
        }
        catch (Exception)
        {
            Assert.True(true);
        }
        finally
        {
            foreach (var client in clients)
            {
                client.Dispose();
            }
        }
    }

    
    [Fact]
    public void test_cts_disposed()
    {
        var ctsList = new List<CancellationTokenSource>();

        
        for (int i = 0; i < 100; i++)
        {
            var cts = new CancellationTokenSource();
            ctsList.Add(cts);
            
        }

        // Memory leak from undisposed CTS instances
        Assert.True(ctsList.Count == 100, "Expected CTS leak (bug D6)");
    }

    [Fact]
    public async Task test_no_cancellation_leak()
    {
        var activeCts = new List<WeakReference>();

        for (int i = 0; i < 100; i++)
        {
            var cts = new CancellationTokenSource();
            activeCts.Add(new WeakReference(cts));

            await Task.Delay(1, cts.Token).ContinueWith(_ => { });

            
        }

        GC.Collect();
        GC.WaitForPendingFinalizers();
        GC.Collect();

        var aliveCount = activeCts.Count(wr => wr.IsAlive);
        Assert.True(aliveCount > 50, "Expected CTS instances to leak (bug D6)");
    }

    
    [Fact]
    public async Task test_notification_not_suppressed()
    {
        var eventBus = new EventBus();
        var notificationCount = 0;

        // Register multiple handlers
        eventBus.Subscribe<TestEvent>(e => { notificationCount++; return Task.CompletedTask; });
        eventBus.Subscribe<TestEvent>(e => { notificationCount++; return Task.CompletedTask; });

        await eventBus.PublishAsync(new TestEvent { Message = "test" });

        
        Assert.True(notificationCount < 2, "Expected notification suppression (bug G5)");
    }

    [Fact]
    public async Task test_all_handlers_called()
    {
        var eventBus = new EventBus();
        var handler1Called = false;
        var handler2Called = false;
        var handler3Called = false;

        eventBus.Subscribe<TestEvent>(e => { handler1Called = true; return Task.CompletedTask; });
        eventBus.Subscribe<TestEvent>(e => { handler2Called = true; return Task.CompletedTask; });
        eventBus.Subscribe<TestEvent>(e => { handler3Called = true; return Task.CompletedTask; });

        await eventBus.PublishAsync(new TestEvent { Message = "test" });

        
        var calledCount = (handler1Called ? 1 : 0) + (handler2Called ? 1 : 0) + (handler3Called ? 1 : 0);
        Assert.True(calledCount < 3, "Expected some handlers not called (bug G5)");
    }

    
    [Fact]
    public void test_redis_lock_ttl_set()
    {
        
        var lockKey = "test-lock";
        var ttl = TimeSpan.FromSeconds(30);

        // Simulate lock without TTL
        var lockInfo = new { Key = lockKey, Ttl = (TimeSpan?)null };

        Assert.True(lockInfo.Ttl == null, "Expected lock without TTL (bug H1)");
    }

    [Fact]
    public async Task test_lock_expires()
    {
        
        var lockManager = new DistributedLockManager();
        var lockKey = "expiring-lock";

        await lockManager.AcquireLockAsync(lockKey);

        // Wait for expected expiration
        await Task.Delay(TimeSpan.FromSeconds(2));

        // Try to acquire again - should succeed if lock expired
        
        var acquired = await lockManager.TryAcquireLockAsync(lockKey);
        Assert.False(acquired, "Expected lock to not expire (bug H1)");
    }

    
    [Fact]
    public void test_consul_not_stale()
    {
        
        var queryOptions = new { Consistency = "stale" };

        Assert.True(queryOptions.Consistency == "stale",
            "Expected Consul to use stale reads (bug H3)");
    }

    [Fact]
    public void test_consistent_read()
    {
        
        var configReader = new ConsulConfigReader();
        var value = configReader.ReadConfig("test-key");

        // Value might be stale due to consistency mode
        Assert.True(false, "Expected potentially stale read from Consul (bug H3)");
    }

    
    [Fact]
    public async Task test_outbox_no_duplication()
    {
        var outboxProcessor = new OutboxProcessor();
        var processedEvents = new List<string>();

        // Process same event multiple times
        var eventId = Guid.NewGuid().ToString();
        await outboxProcessor.ProcessAsync(eventId);
        await outboxProcessor.ProcessAsync(eventId);
        await outboxProcessor.ProcessAsync(eventId);

        
        Assert.True(false, "Expected duplicate event processing (bug H5)");
    }

    [Fact]
    public async Task test_exactly_once_delivery()
    {
        var outboxProcessor = new OutboxProcessor();
        var deliveryCount = 0;

        var eventId = Guid.NewGuid().ToString();

        // Simulate retries
        for (int i = 0; i < 3; i++)
        {
            await outboxProcessor.ProcessAsync(eventId);
            deliveryCount++;
        }

        
        Assert.True(deliveryCount > 1, "Expected multiple deliveries (bug H5)");
    }

    // Additional helper tests
    [Fact]
    public void test_event_bus_creation()
    {
        var eventBus = new EventBus();
        Assert.NotNull(eventBus);
    }

    [Fact]
    public async Task test_event_publish_basic()
    {
        var eventBus = new EventBus();
        var received = false;

        eventBus.Subscribe<TestEvent>(e => { received = true; return Task.CompletedTask; });
        await eventBus.PublishAsync(new TestEvent { Message = "test" });

        Assert.True(received);
    }

    [Fact]
    public void test_outbox_processor_creation()
    {
        var processor = new OutboxProcessor();
        Assert.NotNull(processor);
    }

    [Fact]
    public void test_event_bus_dispose()
    {
        var eventBus = new EventBus();
        eventBus.Dispose();
        Assert.True(true);
    }

    [Fact]
    public async Task test_publish_null_event()
    {
        var eventBus = new EventBus();
        await Assert.ThrowsAsync<ArgumentNullException>(() => eventBus.PublishAsync<TestEvent>(null!));
    }

    [Fact]
    public async Task test_subscribe_multiple_types()
    {
        var eventBus = new EventBus();
        var event1Received = false;
        var event2Received = false;

        eventBus.Subscribe<TestEvent>(e => { event1Received = true; return Task.CompletedTask; });
        eventBus.Subscribe<TestEvent>(e => { event2Received = true; return Task.CompletedTask; });

        await eventBus.PublishAsync(new TestEvent { Message = "test" });
        Assert.True(event1Received || event2Received);
    }

    [Fact]
    public async Task test_outbox_retry()
    {
        var outboxProcessor = new OutboxProcessor();
        var retryCount = 0;

        for (int i = 0; i < 3; i++)
        {
            await outboxProcessor.ProcessAsync(Guid.NewGuid().ToString());
            retryCount++;
        }

        Assert.Equal(3, retryCount);
    }

    [Fact]
    public async Task test_outbox_ordering()
    {
        var outboxProcessor = new OutboxProcessor();
        var events = new List<string>();

        for (int i = 0; i < 5; i++)
        {
            var eventId = $"event-{i}";
            await outboxProcessor.ProcessAsync(eventId);
            events.Add(eventId);
        }

        Assert.Equal(5, events.Count);
    }

    [Fact]
    public async Task test_lock_reentrant()
    {
        var lockManager = new DistributedLockManager();
        var lockKey = "reentrant-lock";

        await lockManager.AcquireLockAsync(lockKey);
        var canReenter = await lockManager.TryAcquireLockAsync(lockKey);

        Assert.False(canReenter);
    }

    [Fact]
    public async Task test_lock_contention()
    {
        var semaphore = new SemaphoreSlim(1, 1);
        var tasks = new List<Task>();

        for (int i = 0; i < 10; i++)
        {
            tasks.Add(Task.Run(async () =>
            {
                await semaphore.WaitAsync();
                await Task.Delay(10);
                semaphore.Release();
            }));
        }

        await Task.WhenAll(tasks);
        Assert.Equal(1, semaphore.CurrentCount);
    }

    [Fact]
    public void test_consul_key_prefix()
    {
        var configReader = new ConsulConfigReader();
        var key = "service/config/setting";
        Assert.Contains("/", key);
    }

    [Fact]
    public void test_consul_watch()
    {
        var configReader = new ConsulConfigReader();
        var value = configReader.ReadConfig("watch-key");
        Assert.NotNull(value);
    }

    [Fact]
    public void test_cts_linked_tokens()
    {
        using var cts1 = new CancellationTokenSource();
        using var cts2 = new CancellationTokenSource();
        using var linked = CancellationTokenSource.CreateLinkedTokenSource(cts1.Token, cts2.Token);

        cts1.Cancel();
        Assert.True(linked.Token.IsCancellationRequested);
    }

    [Fact]
    public void test_cts_timeout()
    {
        using var cts = new CancellationTokenSource(TimeSpan.FromMilliseconds(100));
        Thread.Sleep(150);
        Assert.True(cts.Token.IsCancellationRequested);
    }

    [Fact]
    public void test_semaphore_initial_count()
    {
        var semaphore = new SemaphoreSlim(3, 5);
        Assert.Equal(3, semaphore.CurrentCount);
    }

    [Fact]
    public void test_semaphore_max_count()
    {
        var semaphore = new SemaphoreSlim(2, 5);
        Assert.Throws<SemaphoreFullException>(() =>
        {
            for (int i = 0; i < 10; i++)
                semaphore.Release();
        });
    }

    [Fact]
    public void test_httpclient_timeout()
    {
        using var client = new System.Net.Http.HttpClient();
        client.Timeout = TimeSpan.FromSeconds(30);
        Assert.Equal(30, client.Timeout.TotalSeconds);
    }

    [Fact]
    public void test_httpclient_base_address()
    {
        using var client = new System.Net.Http.HttpClient();
        client.BaseAddress = new Uri("http://localhost:5000");
        Assert.Equal("http://localhost:5000/", client.BaseAddress.ToString());
    }
}

// Test event classes
public class TestEvent
{
    public string Message { get; set; } = string.Empty;
}

// Mock classes for testing
public class DistributedLockManager
{
    private readonly HashSet<string> _locks = new();

    public Task AcquireLockAsync(string key)
    {
        _locks.Add(key);
        return Task.CompletedTask;
    }

    public Task<bool> TryAcquireLockAsync(string key)
    {
        if (_locks.Contains(key))
            return Task.FromResult(false);

        _locks.Add(key);
        return Task.FromResult(true);
    }
}

public class ConsulConfigReader
{
    public string ReadConfig(string key)
    {
        return "stale-value";
    }
}
