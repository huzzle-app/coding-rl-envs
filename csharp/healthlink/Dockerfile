# Stage 1: Build
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS builder

WORKDIR /app

# Copy solution and project files first (cached layer)
COPY HealthLink.sln .
COPY src/HealthLink.Api/HealthLink.Api.csproj src/HealthLink.Api/
COPY tests/HealthLink.Tests/HealthLink.Tests.csproj tests/HealthLink.Tests/
RUN dotnet restore

# Copy source code and build
COPY src/ ./src/
RUN dotnet publish src/HealthLink.Api/HealthLink.Api.csproj -c Release -o /publish --no-restore

# Stage 2: Runtime
FROM mcr.microsoft.com/dotnet/aspnet:8.0

WORKDIR /app

# Create non-root user for security
RUN groupadd --system appgroup && useradd --system --gid appgroup appuser

COPY --from=builder /publish .

RUN chown -R appuser:appgroup /app

USER appuser

EXPOSE 5000

ENTRYPOINT ["dotnet", "HealthLink.Api.dll"]
