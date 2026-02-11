FROM maven:3.9-eclipse-temurin-21 AS builder
WORKDIR /app
COPY . .
RUN mvn -pl shared,notifications -am package -DskipTests -q

FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=builder /app/notifications/target/*.jar app.jar
EXPOSE 8008
ENTRYPOINT ["java", "-jar", "app.jar"]
