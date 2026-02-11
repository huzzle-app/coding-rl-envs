FROM mcr.microsoft.com/dotnet/sdk:8.0 AS builder
WORKDIR /app
COPY EventHorizon.sln .
COPY src/Shared/Shared.csproj src/Shared/
COPY src/Gateway/Gateway.csproj src/Gateway/
COPY src/Auth/Auth.csproj src/Auth/
COPY src/Events/Events.csproj src/Events/
COPY src/Tickets/Tickets.csproj src/Tickets/
COPY src/Orders/Orders.csproj src/Orders/
COPY src/Payments/Payments.csproj src/Payments/
COPY src/Venues/Venues.csproj src/Venues/
COPY src/Notifications/Notifications.csproj src/Notifications/
COPY src/Analytics/Analytics.csproj src/Analytics/
COPY src/Search/Search.csproj src/Search/
RUN dotnet restore

COPY src/ ./src/
RUN dotnet publish -c Release -o /publish --no-restore

FROM mcr.microsoft.com/dotnet/aspnet:8.0
WORKDIR /app
COPY --from=builder /publish .
EXPOSE 5000-5010
