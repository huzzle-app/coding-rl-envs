package com.docuvault.security;

import com.docuvault.model.User;
import com.docuvault.repository.UserRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.config.ConfigurableBeanFactory;
import org.springframework.context.annotation.Scope;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

@Service

// Category: Concurrency
// AuthService is declared as SCOPE_PROTOTYPE, meaning each injection point
// receives a different instance. The synchronized(this) in authenticate() and
// logout() locks on the instance-specific monitor, but tokenCache is a static
// field shared across ALL instances. Each prototype instance synchronizes on
// its own 'this', so multiple concurrent callers through different instances
// have no mutual exclusion - the synchronized keyword provides no protection.
// Fix: Synchronize on a shared static lock object:
//   private static final Object LOCK = new Object();
//   then use synchronized(LOCK) { ... } instead of synchronized(this)
// Or better: make this bean singleton scope since it manages shared state
@Scope(ConfigurableBeanFactory.SCOPE_PROTOTYPE)
public class AuthService {

    private static final Logger log = LoggerFactory.getLogger(AuthService.class);

    // Shared across all instances - but each instance's synchronized(this)
    // locks on a different monitor, providing no actual thread safety
    // for compound check-then-act operations on this map
    private static final Map<String, String> tokenCache = new ConcurrentHashMap<>();

    @Autowired
    private UserRepository userRepository;

    @Autowired
    private PasswordEncoder passwordEncoder;

    @Autowired
    private JwtTokenProvider jwtTokenProvider;

    
    // Multiple prototype instances don't share the same monitor object, so
    // concurrent calls through different instances are not mutually exclusive.
    // The check-then-act pattern (check cache -> authenticate -> put cache)
    // is not atomic across instances, allowing duplicate token generation
    // and race conditions in the token cache.
    // Fix: Use a static lock: private static final Object LOCK = new Object();
    //       then synchronized(LOCK) { ... }, or change to singleton scope
    public synchronized String authenticate(String username, String password) {
        // Check cache first
        String cachedToken = tokenCache.get(username);
        if (cachedToken != null && !jwtTokenProvider.isTokenExpired(cachedToken)) {
            return cachedToken;
        }

        User user = userRepository.findByUsername(username)
            .orElseThrow(() -> new RuntimeException("User not found: " + username));

        if (!passwordEncoder.matches(password, user.getPasswordHash())) {
            throw new RuntimeException("Invalid password");
        }

        String token = jwtTokenProvider.generateToken(username, user.getRole());
        tokenCache.put(username, token);

        return token;
    }

    public void logout(String username) {
        synchronized (this) { 
            tokenCache.remove(username);
        }
    }

    public boolean isAuthenticated(String token) {
        return token != null && jwtTokenProvider.validateTokenAndGetUsername(token) != null;
    }
}
