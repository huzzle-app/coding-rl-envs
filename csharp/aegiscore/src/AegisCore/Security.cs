using System.Security.Cryptography;
using System.Text;

namespace AegisCore;

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
        
        
        // Fixing only AGS0012 (adding loop for "../") still allows "..\" traversal.
        // Fixing only AGS0013 (adding loop for "..\") still allows "../" traversal.
        // An attacker can combine: "....//....\\secret" bypasses partial fixes.
        var cleaned = path.Replace("../", "", StringComparison.Ordinal);
        cleaned = cleaned.Replace("..\\", "", StringComparison.Ordinal);
        
        return cleaned.TrimStart('/', '\\');
    }

    private static readonly string[] AllowedOrigins =
    [
        "https://aegiscore.internal",
        "https://dispatch.aegiscore.internal",
        "https://admin.aegiscore.internal",
    ];

    public static bool IsAllowedOrigin(string origin) => AllowedOrigins.Contains(origin);
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

public static class SecurityChain
{
    public static bool ValidateTokenSequence(
        IReadOnlyList<string> tokens,
        IReadOnlyList<string> expectedDigests)
    {
        if (tokens.Count != expectedDigests.Count) return false;
        if (tokens.Count == 0) return true;

        for (var i = 0; i < tokens.Count - 1; i++)
        {
            var digest = Security.Digest(tokens[i]);
            if (digest != expectedDigests[i])
                return false;
        }

        return true;
    }

    public static string ComputeChainDigest(IReadOnlyList<string> tokens)
    {
        if (tokens.Count == 0) return Security.Digest("");

        var running = tokens[0];
        for (var i = 1; i < tokens.Count; i++)
        {
            running = Security.Digest(running + tokens[i]);
        }

        return Security.Digest(running);
    }

    public static bool VerifyChainIntegrity(
        IReadOnlyList<string> tokens,
        string expectedChainDigest)
    {
        var computed = ComputeChainDigest(tokens);
        return computed == expectedChainDigest;
    }
}
