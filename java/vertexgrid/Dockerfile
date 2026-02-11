FROM maven:3.9-eclipse-temurin-21 AS builder
WORKDIR /app
COPY pom.xml .
COPY shared ./shared
COPY gateway ./gateway
COPY auth ./auth
COPY vehicles ./vehicles
COPY routes ./routes
COPY dispatch ./dispatch
COPY tracking ./tracking
COPY billing ./billing
COPY analytics ./analytics
COPY notifications ./notifications
COPY compliance ./compliance
RUN mvn package -DskipTests -q

FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=builder /app/*/target/*.jar ./
EXPOSE 8000-8009
