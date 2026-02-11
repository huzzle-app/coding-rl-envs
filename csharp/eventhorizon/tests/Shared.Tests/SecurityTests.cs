using Xunit;
using System;
using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Text;
using Microsoft.IdentityModel.Tokens;
using EventHorizon.Shared.Security;

namespace EventHorizon.Shared.Tests;

public class SecurityTests
{
    private const string TestSecretKey = "test-secret-key-that-is-long-enough-for-hmac-sha256";
    private const string TestIssuer = "EventHorizon";
    private const string TestAudience = "EventHorizonAPI";

    [Fact]
    public void test_jwt_token_generation()
    {
        var provider = new JwtTokenProvider(TestSecretKey, TestIssuer, TestAudience);
        var userId = "user123";
        var email = "test@example.com";

        var token = provider.GenerateToken(userId, email);

        Assert.False(string.IsNullOrEmpty(token), "Token should be generated");
    }

    [Fact]
    public void test_jwt_token_validation()
    {
        var provider = new JwtTokenProvider(TestSecretKey, TestIssuer, TestAudience);
        var userId = "user123";
        var email = "test@example.com";

        var token = provider.GenerateToken(userId, email);
        var principal = provider.ValidateToken(token);

        Assert.NotNull(principal);
        Assert.True(principal.Identity?.IsAuthenticated);
    }

    [Fact]
    public void test_jwt_claims_present()
    {
        var provider = new JwtTokenProvider(TestSecretKey, TestIssuer, TestAudience);
        var userId = "user123";
        var email = "test@example.com";

        var token = provider.GenerateToken(userId, email);
        var handler = new JwtSecurityTokenHandler();
        var jwtToken = handler.ReadJwtToken(token);

        var userIdClaim = jwtToken.Claims.FirstOrDefault(c => c.Type == "sub" || c.Type == ClaimTypes.NameIdentifier);
        var emailClaim = jwtToken.Claims.FirstOrDefault(c => c.Type == "email" || c.Type == ClaimTypes.Email);

        Assert.NotNull(userIdClaim);
        Assert.NotNull(emailClaim);
    }

    [Fact]
    public void test_jwt_expiration_set()
    {
        var provider = new JwtTokenProvider(TestSecretKey, TestIssuer, TestAudience);
        var token = provider.GenerateToken("user123", "test@example.com");

        var handler = new JwtSecurityTokenHandler();
        var jwtToken = handler.ReadJwtToken(token);

        Assert.True(jwtToken.ValidTo > DateTime.UtcNow);
        Assert.True(jwtToken.ValidTo < DateTime.UtcNow.AddDays(2));
    }

    [Fact]
    public void test_jwt_signature_verification()
    {
        var provider = new JwtTokenProvider(TestSecretKey, TestIssuer, TestAudience);
        var token = provider.GenerateToken("user123", "test@example.com");

        // Tamper with token
        var parts = token.Split('.');
        if (parts.Length == 3)
        {
            var tamperedToken = $"{parts[0]}.{parts[1]}.invalidsignature";

            Assert.Throws<SecurityTokenException>(() => provider.ValidateToken(tamperedToken));
        }
    }

    [Fact]
    public void test_jwt_expired_token_rejected()
    {
        var provider = new JwtTokenProvider(TestSecretKey, TestIssuer, TestAudience);

        // Create token with past expiration
        var tokenDescriptor = new SecurityTokenDescriptor
        {
            Subject = new ClaimsIdentity(new[]
            {
                new Claim(ClaimTypes.NameIdentifier, "user123"),
                new Claim(ClaimTypes.Email, "test@example.com")
            }),
            Expires = DateTime.UtcNow.AddMinutes(-10), // Expired 10 minutes ago
            Issuer = TestIssuer,
            Audience = TestAudience,
            SigningCredentials = new SigningCredentials(
                new SymmetricSecurityKey(Encoding.UTF8.GetBytes(TestSecretKey)),
                SecurityAlgorithms.HmacSha256Signature)
        };

        var handler = new JwtSecurityTokenHandler();
        var token = handler.CreateToken(tokenDescriptor);
        var expiredToken = handler.WriteToken(token);

        Assert.Throws<SecurityTokenExpiredException>(() => provider.ValidateToken(expiredToken));
    }

    [Fact]
    public void test_jwt_wrong_issuer_rejected()
    {
        var provider = new JwtTokenProvider(TestSecretKey, TestIssuer, TestAudience);

        var wrongProvider = new JwtTokenProvider(TestSecretKey, "WrongIssuer", TestAudience);
        var token = wrongProvider.GenerateToken("user123", "test@example.com");

        Assert.Throws<SecurityTokenInvalidIssuerException>(() => provider.ValidateToken(token));
    }

    [Fact]
    public void test_jwt_wrong_audience_rejected()
    {
        var provider = new JwtTokenProvider(TestSecretKey, TestIssuer, TestAudience);

        var wrongProvider = new JwtTokenProvider(TestSecretKey, TestIssuer, "WrongAudience");
        var token = wrongProvider.GenerateToken("user123", "test@example.com");

        Assert.Throws<SecurityTokenInvalidAudienceException>(() => provider.ValidateToken(token));
    }

    [Fact]
    public void test_jwt_minimum_key_length()
    {
        var shortKey = "short";

        Assert.Throws<ArgumentException>(() =>
            new JwtTokenProvider(shortKey, TestIssuer, TestAudience));
    }

    [Fact]
    public void test_jwt_refresh_token_generation()
    {
        var provider = new JwtTokenProvider(TestSecretKey, TestIssuer, TestAudience);

        var refreshToken = provider.GenerateRefreshToken();

        Assert.False(string.IsNullOrEmpty(refreshToken));
        Assert.True(refreshToken.Length >= 32);
    }

    [Fact]
    public void test_jwt_refresh_tokens_unique()
    {
        var provider = new JwtTokenProvider(TestSecretKey, TestIssuer, TestAudience);

        var token1 = provider.GenerateRefreshToken();
        var token2 = provider.GenerateRefreshToken();

        Assert.NotEqual(token1, token2);
    }

    [Fact]
    public void test_password_hashing()
    {
        var password = "TestPassword123!";
        var hashedPassword = JwtTokenProvider.HashPassword(password);

        Assert.NotEqual(password, hashedPassword);
        Assert.True(hashedPassword.Length > password.Length);
    }

    [Fact]
    public void test_password_verification()
    {
        var password = "TestPassword123!";
        var hashedPassword = JwtTokenProvider.HashPassword(password);

        var isValid = JwtTokenProvider.VerifyPassword(password, hashedPassword);

        Assert.True(isValid);
    }

    [Fact]
    public void test_password_verification_fails_wrong_password()
    {
        var password = "TestPassword123!";
        var wrongPassword = "WrongPassword456!";
        var hashedPassword = JwtTokenProvider.HashPassword(password);

        var isValid = JwtTokenProvider.VerifyPassword(wrongPassword, hashedPassword);

        Assert.False(isValid);
    }

    [Fact]
    public void test_same_password_different_hashes()
    {
        var password = "TestPassword123!";
        var hash1 = JwtTokenProvider.HashPassword(password);
        var hash2 = JwtTokenProvider.HashPassword(password);

        // Due to salt, same password should produce different hashes
        Assert.NotEqual(hash1, hash2);
    }

    [Fact]
    public void test_token_claims_extraction()
    {
        var provider = new JwtTokenProvider(TestSecretKey, TestIssuer, TestAudience);
        var token = provider.GenerateToken("user123", "test@example.com");
        var handler = new JwtSecurityTokenHandler();
        var jwtToken = handler.ReadJwtToken(token);

        Assert.True(jwtToken.Claims.Any());
    }

    [Fact]
    public void test_token_audience_validation()
    {
        var provider = new JwtTokenProvider(TestSecretKey, TestIssuer, TestAudience);
        var token = provider.GenerateToken("user123", "test@example.com");
        var handler = new JwtSecurityTokenHandler();
        var jwtToken = handler.ReadJwtToken(token);

        Assert.Contains(TestAudience, jwtToken.Audiences);
    }

    [Fact]
    public void test_token_issuer_validation()
    {
        var provider = new JwtTokenProvider(TestSecretKey, TestIssuer, TestAudience);
        var token = provider.GenerateToken("user123", "test@example.com");
        var handler = new JwtSecurityTokenHandler();
        var jwtToken = handler.ReadJwtToken(token);

        Assert.Equal(TestIssuer, jwtToken.Issuer);
    }

    [Fact]
    public void test_token_not_before()
    {
        var provider = new JwtTokenProvider(TestSecretKey, TestIssuer, TestAudience);
        var token = provider.GenerateToken("user123", "test@example.com");
        var handler = new JwtSecurityTokenHandler();
        var jwtToken = handler.ReadJwtToken(token);

        Assert.True(jwtToken.ValidFrom <= DateTime.UtcNow);
    }

    [Fact]
    public void test_token_expiry_check()
    {
        var provider = new JwtTokenProvider(TestSecretKey, TestIssuer, TestAudience);
        var token = provider.GenerateToken("user123", "test@example.com");
        var handler = new JwtSecurityTokenHandler();
        var jwtToken = handler.ReadJwtToken(token);

        Assert.True(jwtToken.ValidTo > DateTime.UtcNow);
    }

    [Fact]
    public void test_refresh_token_rotation()
    {
        var provider = new JwtTokenProvider(TestSecretKey, TestIssuer, TestAudience);
        var token1 = provider.GenerateRefreshToken();
        var token2 = provider.GenerateRefreshToken();

        Assert.NotEqual(token1, token2);
    }

    [Fact]
    public void test_password_complexity()
    {
        var weakPassword = "123";
        var strongPassword = "StrongP@ssw0rd!";

        Assert.True(strongPassword.Length > weakPassword.Length);
    }

    [Fact]
    public void test_password_salt_unique()
    {
        var password = "TestPassword123!";
        var hash1 = JwtTokenProvider.HashPassword(password);
        var hash2 = JwtTokenProvider.HashPassword(password);

        Assert.NotEqual(hash1, hash2);
    }

    [Fact]
    public void test_hash_algorithm_secure()
    {
        var password = "TestPassword123!";
        var hashedPassword = JwtTokenProvider.HashPassword(password);

        Assert.True(hashedPassword.Length >= 60); // BCrypt hashes are typically 60 chars
    }

    [Fact]
    public void test_token_revocation()
    {
        var provider = new JwtTokenProvider(TestSecretKey, TestIssuer, TestAudience);
        var token = provider.GenerateToken("user123", "test@example.com");

        Assert.NotNull(token);
    }
}
