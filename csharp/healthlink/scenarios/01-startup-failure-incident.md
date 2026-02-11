# Incident Report: Application Fails to Start in Production

## PagerDuty Alert

**Severity**: Critical (P1)
**Triggered**: 2024-02-19 06:15 UTC
**Acknowledged**: 2024-02-19 06:18 UTC
**Team**: Platform Engineering

---

## Alert Details

```
CRITICAL: healthlink-api-prod pods failing health checks
Cluster: healthlink-prod-eus
Namespace: healthlink
Deployment: healthlink-api
Ready: 0/3 pods
```

## Timeline

**06:15 UTC** - Initial alert: Pod health checks failing

**06:18 UTC** - SRE on-call acknowledges, begins investigation

**06:22 UTC** - All 3 pods in CrashLoopBackOff state
```
NAME                            READY   STATUS             RESTARTS   AGE
healthlink-api-7d9f8c6b5-abc12   0/1     CrashLoopBackOff   4          8m
healthlink-api-7d9f8c6b5-def34   0/1     CrashLoopBackOff   4          8m
healthlink-api-7d9f8c6b5-ghi56   0/1     CrashLoopBackOff   4          8m
```

**06:30 UTC** - Attempted rollback to previous image - same failure

**06:45 UTC** - Escalated to engineering team

## Container Logs

```
info: Microsoft.Hosting.Lifetime[14]
      Now listening on: http://[::]:80
fail: Microsoft.Extensions.DependencyInjection.ServiceProvider[0]
      Exception occurred while creating the service 'INotificationService'.
System.InvalidOperationException: A circular dependency was detected for the service of type 'ISchedulingService'.
   'ISchedulingService' -> 'INotificationService' -> 'ISchedulingService'
   at Microsoft.Extensions.DependencyInjection.ServiceLookup.CallSiteFactory.GetCallSite(ServiceDescriptor, CallSiteChain)
   at Microsoft.Extensions.DependencyInjection.ServiceLookup.ServiceProviderEngine.GetService(Type)
```

## Additional Errors in Logs

After fixing a local test deployment's DI issue (manually), additional startup problems appear:

```
fail: Microsoft.AspNetCore.Diagnostics.DeveloperExceptionPageMiddleware[1]
      An unhandled exception has occurred while executing the request.
Microsoft.Extensions.Options.OptionsValidationException: SmtpSettings.Host is required.
   at Microsoft.Extensions.Options.OptionsFactory`1.Create(String name)
```

And when testing endpoints:

```
warn: Microsoft.AspNetCore.Authorization.DefaultAuthorizationService[2]
      Authorization failed. These requirements were not met:
      DenyAnonymousAuthorizationRequirement: Requires an authenticated user.
# Note: Token IS being passed in Authorization header but still fails
```

## Customer Impact

- **Total outage** - all HealthLink API endpoints returning 503
- Emergency room intake systems unable to retrieve patient records
- Appointment scheduling completely unavailable
- ~150 clinics affected across Eastern region

## Attempted Mitigations

1. **Rollback to v2.3.1** - Same crash loop (no recent changes to DI)
2. **Increased pod resources** - No effect
3. **Manual pod restart** - Pods continue crash looping
4. **Checked PostgreSQL/Redis** - Both healthy, connections succeed from debug pod

## Environment Details

```
Runtime: .NET 8.0.1
Image: healthlink-api:v2.4.0
Last successful deployment: 2024-02-18 22:00 UTC
Recent infrastructure changes: None
```

## Configuration Files

`appsettings.json` excerpt:
```json
{
  "ConnectionStrings": {
    "DefaultConnection": "Host=postgres-prod;Database=healthlink;..."
  },
  "Smtp": {
    "Host": "smtp.sendgrid.net",
    "Port": 587,
    "Username": "apikey",
    "Password": "SG.***"
  },
  "Jwt": {
    "Key": "short-key!"
  }
}
```

## Questions for Investigation

1. Why is there a circular dependency between NotificationService and SchedulingService?
2. Why is SMTP configuration not being loaded despite being present in appsettings.json?
3. Why does authentication fail even when valid tokens are provided?
4. Are there middleware ordering issues preventing auth from running?

## Files to Investigate

Based on the stack traces:
- `src/HealthLink.Api/Program.cs` - DI registration and middleware setup
- `src/HealthLink.Api/Services/NotificationService.cs` - Circular dependency participant
- `src/HealthLink.Api/Services/SchedulingService.cs` - Circular dependency participant
- `src/HealthLink.Api/appsettings.json` - Configuration section names

---

**Status**: INVESTIGATING
**Assigned**: @backend-team
**Customer Comms**: Status page updated, incident call scheduled for 07:00 UTC
