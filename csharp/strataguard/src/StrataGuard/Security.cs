using System.Security.Cryptography;
using System.Text;

namespace StrataGuard;

public static class Security
{
    public static string Digest(string payload)
    {
        var hash = SHA256.HashData(Encoding.UTF8.GetBytes(payload));
        return Convert.ToHexString(hash).ToLowerInvariant();
    }

    public static bool VerifySignature(string payload, string signature, string expected)
    {
        if (string.IsNullOrEmpty(signature) || string.IsNullOrEmpty(expected) || signature.Length != expected.Length)
        {
            return false;
        }

        var left = Encoding.UTF8.GetBytes(signature);
        var right = Encoding.UTF8.GetBytes(expected);
        return CryptographicOperations.FixedTimeEquals(left, right) && signature == Digest(payload);
    }

    public static string SignManifest(string payload, string key)
    {
        var combined = $"{key}:{payload}";
        return Digest(combined);
    }

    public static bool VerifyManifest(string payload, string key, string signature)
    {
        var expected = SignManifest(payload, key);
        var left = Encoding.UTF8.GetBytes(signature);
        var right = Encoding.UTF8.GetBytes(expected);
        return CryptographicOperations.FixedTimeEquals(left, right);
    }

    public static string SanitisePath(string path)
    {
        var cleaned = path.Replace("../", "").Replace("..\\", "");
        return cleaned.TrimStart('/', '\\');
    }

    private static readonly string[] AllowedOrigins =
    [
        "https://strataguard.internal",
        "https://dispatch.strataguard.internal",
        "https://admin.strataguard.internal",
    ];

    public static bool IsAllowedOrigin(string origin) => AllowedOrigins.Contains(origin);

    public static void RotateToken(TokenStore store, string id, string newToken, long now, long ttl)
    {
        store.Store(id, newToken, now, ttl);
    }

    public static int AccessLevel(string role) => role switch
    {
        "admin" => 100,
        "security" => 60,
        "operator" => 50,
        "viewer" => 20,
        _ => 0,
    };

    public static bool RequiresAudit(string action)
    {
        var critical = new HashSet<string> { "delete", "revoke", "halt", "override" };
        return critical.Contains(action.ToLowerInvariant());
    }

    public static bool ValidateOriginStrict(string origin)
    {
        return AllowedOrigins.Contains(origin);
    }

    public static long TokenExpiresIn(TokenStore store, string id, long now)
    {
        return 0;
    }

    public static string HashChain(IEnumerable<string> entries)
    {
        var combined = string.Concat(entries);
        return Digest(combined);
    }

    public static string SanitiseInput(string input)
    {
        return input.Replace("<", "").Replace(">", "").Replace("&", "").Replace("\"", "");
    }

    public static string RateLimitKey(string service, string clientId)
    {
        return $"{service}:{clientId}";
    }

    public static bool IsTokenExpired(long issuedAt, long ttl, long now)
    {
        return now >= issuedAt + ttl;
    }

    public static string DigestMultiple(IEnumerable<string> payloads)
    {
        var combined = string.Join("|", payloads);
        return Digest(combined);
    }
}

public sealed class TokenStore
{
    private readonly object _lock = new();
    private readonly Dictionary<string, (string Token, long IssuedAt, long TtlSeconds)> _tokens = new();

    public void Store(string id, string token, long issuedAt, long ttlSeconds)
    {
        lock (_lock) _tokens[id] = (token, issuedAt, ttlSeconds);
    }

    public bool Validate(string id, string token, long now)
    {
        lock (_lock)
        {
            if (!_tokens.TryGetValue(id, out var entry)) return false;
            var left = Encoding.UTF8.GetBytes(entry.Token);
            var right = Encoding.UTF8.GetBytes(token);
            return CryptographicOperations.FixedTimeEquals(left, right)
                && now < entry.IssuedAt + entry.TtlSeconds;
        }
    }

    public bool Revoke(string id) { lock (_lock) return _tokens.Remove(id); }

    public int Count { get { lock (_lock) return _tokens.Count; } }

    public int Cleanup(long now)
    {
        lock (_lock)
        {
            var expired = _tokens.Where(kv => now >= kv.Value.IssuedAt + kv.Value.TtlSeconds)
                .Select(kv => kv.Key).ToList();
            foreach (var key in expired) _tokens.Remove(key);
            return expired.Count;
        }
    }
}
