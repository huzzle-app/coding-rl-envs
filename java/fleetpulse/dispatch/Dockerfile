FROM maven:3.9-eclipse-temurin-21 AS builder
WORKDIR /app
COPY . .
RUN mvn -pl shared,dispatch -am package -DskipTests -q

FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=builder /app/dispatch/target/*.jar app.jar
EXPOSE 8004
ENTRYPOINT ["java", "-jar", "app.jar"]
