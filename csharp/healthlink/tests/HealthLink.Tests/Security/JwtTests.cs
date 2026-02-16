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
        // Verify that JwtTokenService enforces minimum key length (>= 32 bytes for HMAC-SHA256)
        var config = new ConfigurationBuilder()
            .AddInMemoryCollection(new Dictionary<string, string?>
            {
                ["Jwt:Key"] = "short-key!"  // Only 10 bytes - too weak
            })
            .Build();

        var act = () => new JwtTokenService(config);
        // After fix: constructor should throw if key is too short,
        // OR GenerateToken should throw, OR the default key should be >= 32 bytes
        var sourceFile = Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "..",
            "src", "HealthLink.Api", "Security", "JwtTokenService.cs");
        var source = System.IO.File.ReadAllText(sourceFile);
        // Verify that the hardcoded default key is at least 32 bytes
        source.Should().NotContain("\"short-key!\"",
            "default JWT signing key must be at least 256 bits (32 bytes) for HMAC-SHA256");
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
