using System.Text.Json;

namespace EventHorizon.Auth.Services;

public interface IAuthService
{
    Task<AuthResult> AuthenticateAsync(string email, string password);
    string SerializeUser(UserInfo user);
    UserInfo? DeserializeUser(string json);
}

public class AuthResult
{
    public bool Success { get; set; }
    public string? Token { get; set; }
    public string? Error { get; set; }
}

public class UserInfo
{
    public int Id { get; set; }
    public string Email { get; set; } = "";
    public string Role { get; set; } = "User";
    public string DisplayName { get; set; } = "";
}

public class AuthService : IAuthService
{
    // === BUG A2: Missing ConfigureAwait(false) in library code ===
    public async Task<AuthResult> AuthenticateAsync(string email, string password)
    {
        
        var user = await LookupUserAsync(email);
        if (user == null)
            return new AuthResult { Success = false, Error = "User not found" };

        var valid = await ValidatePasswordAsync(user, password);
        return new AuthResult { Success = valid, Token = valid ? "token" : null };
    }

    private async Task<UserInfo?> LookupUserAsync(string email)
    {
        await Task.Delay(10); // Simulate DB lookup
        return new UserInfo { Id = 1, Email = email, Role = "User", DisplayName = "Test" };
    }

    private async Task<bool> ValidatePasswordAsync(UserInfo user, string password)
    {
        await Task.Delay(5);
        return password.Length >= 8;
    }

    // === BUG J1: STJ vs Newtonsoft case mismatch ===
    // System.Text.Json uses camelCase by default, but we're setting PascalCase
    // which creates inconsistency with other services using default camelCase
    public string SerializeUser(UserInfo user)
    {
        var options = new JsonSerializerOptions
        {
            PropertyNamingPolicy = null, // PascalCase (not camelCase!)
        };
        return JsonSerializer.Serialize(user, options);
    }

    public UserInfo? DeserializeUser(string json)
    {
        // Default STJ uses camelCase, so PascalCase JSON won't match
        return JsonSerializer.Deserialize<UserInfo>(json);
    }
}
