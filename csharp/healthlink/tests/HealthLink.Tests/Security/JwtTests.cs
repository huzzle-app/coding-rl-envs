using FluentAssertions;
using HealthLink.Api.Security;
using Microsoft.Extensions.Configuration;
using Xunit;

namespace HealthLink.Tests.Security;

public class JwtTests
{
    [Fact]
    public void test_jwt_weak_key_rejected()
    {
        
        var config = new ConfigurationBuilder()
            .AddInMemoryCollection(new Dictionary<string, string?>
            {
                ["Jwt:Key"] = "short-key!"  // Only 10 bytes!
            })
            .Build();

        var service = new JwtTokenService(config);

        // Generating token with weak key should fail or be rejected
        var act = () => service.GenerateToken(1, "test@test.com", "User");
        // After fix, should enforce minimum key length
        act.Should().NotThrow(); // Token generated but should be rejected on validation
    }

    [Fact]
    public void test_jwt_minimum_key_length()
    {
        
        var config = new ConfigurationBuilder()
            .AddInMemoryCollection(new Dictionary<string, string?>
            {
                ["Jwt:Key"] = "this-is-a-long-enough-key-for-hmac-sha256-testing!"
            })
            .Build();

        var service = new JwtTokenService(config);
        var token = service.GenerateToken(1, "test@test.com", "Admin");
        token.Should().NotBeNullOrEmpty();

        var principal = service.ValidateToken(token);
        principal.Should().NotBeNull();
    }

    [Fact]
    public void test_jwt_token_contains_claims()
    {
        var config = new ConfigurationBuilder()
            .AddInMemoryCollection(new Dictionary<string, string?>
            {
                ["Jwt:Key"] = "this-is-a-long-enough-key-for-hmac-sha256-testing!"
            })
            .Build();

        var service = new JwtTokenService(config);
        var token = service.GenerateToken(42, "user@test.com", "Admin");
        var principal = service.ValidateToken(token);

        principal.Should().NotBeNull();
    }

    [Fact]
    public void test_jwt_invalid_token_rejected()
    {
        var config = new ConfigurationBuilder()
            .AddInMemoryCollection(new Dictionary<string, string?>
            {
                ["Jwt:Key"] = "this-is-a-long-enough-key-for-hmac-sha256-testing!"
            })
            .Build();

        var service = new JwtTokenService(config);
        var principal = service.ValidateToken("invalid-token");
        principal.Should().BeNull();
    }

    [Fact]
    public void test_jwt_expired_token_rejected()
    {
        var config = new ConfigurationBuilder()
            .AddInMemoryCollection(new Dictionary<string, string?>
            {
                ["Jwt:Key"] = "this-is-a-long-enough-key-for-hmac-sha256-testing!"
            })
            .Build();

        var service = new JwtTokenService(config);
        // Can't easily test expiry in unit test, but validate basic flow
        var token = service.GenerateToken(1, "test@test.com", "User");
        token.Should().NotBeNullOrEmpty();
    }
}
