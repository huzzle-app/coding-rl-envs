FROM mcr.microsoft.com/dotnet/sdk:8.0
WORKDIR /app
COPY . .
RUN dotnet restore
EXPOSE 5000-5010
ENTRYPOINT ["dotnet", "test", "--verbosity", "normal"]
