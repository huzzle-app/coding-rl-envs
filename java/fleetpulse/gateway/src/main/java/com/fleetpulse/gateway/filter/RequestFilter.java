package com.fleetpulse.gateway.filter;

import com.fleetpulse.gateway.service.RequestService;
import jakarta.servlet.*;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.util.UUID;

/**
 * Request filter that sets up request context for downstream processing.
 *
 * Bugs: C2
 * Categories: Concurrency
 */
@Component
public class RequestFilter implements Filter {

    @Autowired
    private RequestService requestService;

    @Override
    public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain)
            throws IOException, ServletException {
        HttpServletRequest httpRequest = (HttpServletRequest) request;
        String requestId = UUID.randomUUID().toString();
        String userId = httpRequest.getHeader("X-User-Id");

        // Bug C2: RequestContext is set on ThreadLocal but never cleared
        requestService.setRequestContext(
            new RequestService.RequestContext(requestId, userId));

        try {
            chain.doFilter(request, response);
        } finally {
            // ThreadLocal leaks to next request on same thread
        }
    }
}
