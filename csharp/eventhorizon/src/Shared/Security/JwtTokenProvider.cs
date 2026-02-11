using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Text;
using Microsoft.Extensions.Configuration;
using Microsoft.IdentityModel.Tokens;

namespace EventHorizon.Shared.Security;

public interface IJwtTokenProvider
{
    string GenerateToken(int userId, string email, string role);
    ClaimsPrincipal? ValidateToken(string token);
}

public class JwtTokenProvider : IJwtTokenProvider
{
    // === BUG I3: JWT signing key too short (< 256 bits) ===
    private readonly string _secretKey;
    private readonly string _issuer = "EventHorizon";

    public JwtTokenProvider(IConfiguration configuration)
    {
        _secretKey = configuration["Jwt:Key"] ?? "weak-key"; // Only 8 bytes!
    }

    public string GenerateToken(int userId, string email, string role)
    {
        var key = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(_secretKey));
        var credentials = new SigningCredentials(key, SecurityAlgorithms.HmacSha256);

        var claims = new[]
        {
            new Claim(ClaimTypes.NameIdentifier, userId.ToString()),
            new Claim(ClaimTypes.Email, email),
            new Claim(ClaimTypes.Role, role),
        };

        var token = new JwtSecurityToken(
            issuer: _issuer, audience: _issuer, claims: claims,
            expires: DateTime.UtcNow.AddHours(2), signingCredentials: credentials);

        return new JwtSecurityTokenHandler().WriteToken(token);
    }

    public ClaimsPrincipal? ValidateToken(string token)
    {
        var key = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(_secretKey));
        try
        {
            return new JwtSecurityTokenHandler().ValidateToken(token, new TokenValidationParameters
            {
                ValidateIssuerSigningKey = true, IssuerSigningKey = key,
                ValidateIssuer = true, ValidIssuer = _issuer,
                ValidateAudience = false, ValidateLifetime = true,
            }, out _);
        }
        catch { return null; }
    }
}
