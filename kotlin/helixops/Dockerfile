# Stage 1: Build all modules
FROM gradle:8.5-jdk21 AS builder

WORKDIR /app

# Copy Gradle build files first and download dependencies (cached layer)
COPY build.gradle.kts settings.gradle.kts gradle.properties* ./
COPY gradle ./gradle
COPY shared/build.gradle.kts shared/build.gradle.kts
COPY gateway/build.gradle.kts gateway/build.gradle.kts
COPY auth/build.gradle.kts auth/build.gradle.kts
COPY documents/build.gradle.kts documents/build.gradle.kts
COPY search/build.gradle.kts search/build.gradle.kts
COPY graph/build.gradle.kts graph/build.gradle.kts
COPY embeddings/build.gradle.kts embeddings/build.gradle.kts
COPY collab/build.gradle.kts collab/build.gradle.kts
COPY billing/build.gradle.kts billing/build.gradle.kts
COPY notifications/build.gradle.kts notifications/build.gradle.kts
COPY analytics/build.gradle.kts analytics/build.gradle.kts
RUN gradle build -x test --no-daemon || true

# Copy source code for all modules
COPY shared ./shared
COPY gateway ./gateway
COPY auth ./auth
COPY documents ./documents
COPY search ./search
COPY graph ./graph
COPY embeddings ./embeddings
COPY collab ./collab
COPY billing ./billing
COPY notifications ./notifications
COPY analytics ./analytics

RUN gradle build -x test --no-daemon

# Stage 2: Runtime
FROM eclipse-temurin:21-jre

WORKDIR /app

# Create non-root user for security
RUN groupadd --system appgroup && useradd --system --gid appgroup appuser

# Create data directories
RUN mkdir -p /tmp/helixops/data && chown -R appuser:appgroup /tmp/helixops

# Copy the built jars from builder stage
COPY --from=builder /app/*/build/libs/*.jar ./

# Set ownership
RUN chown -R appuser:appgroup /app

USER appuser

EXPOSE 8080-8089

ENTRYPOINT ["java", "-jar", "gateway.jar"]
