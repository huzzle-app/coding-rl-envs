FROM maven:3.9-eclipse-temurin-21 AS builder
WORKDIR /app
COPY . .
RUN mvn -pl shared,compliance -am package -DskipTests -q

FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=builder /app/compliance/target/*.jar app.jar
EXPOSE 8009
ENTRYPOINT ["java", "-jar", "app.jar"]
