plugins {
    
    kotlin("jvm") version "1.9.22"
    kotlin("plugin.serialization") version "1.9.22"
}

allprojects {
    group = "com.helixops"
    version = "1.0.0"

    repositories {
        mavenCentral()
    }
}

subprojects {
    apply(plugin = "org.jetbrains.kotlin.jvm")
    apply(plugin = "org.jetbrains.kotlin.plugin.serialization")

    dependencies {
        implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.7.3")
        implementation("org.jetbrains.kotlinx:kotlinx-coroutines-slf4j:1.7.3")
        implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.2")
        implementation("io.ktor:ktor-server-websockets:2.3.7")
        implementation("org.jetbrains.exposed:exposed-core:0.44.1")
        implementation("org.jetbrains.exposed:exposed-dao:0.44.1")
        implementation("org.jetbrains.exposed:exposed-jdbc:0.44.1")
        implementation("org.jetbrains.exposed:exposed-java-time:0.44.1")
        implementation("org.postgresql:postgresql:42.7.1")
        implementation("org.slf4j:slf4j-api:2.0.9")
        implementation("ch.qos.logback:logback-classic:1.4.14")

        testImplementation("org.jetbrains.kotlin:kotlin-test-junit5:1.9.22")
        testImplementation("org.junit.jupiter:junit-jupiter:5.10.1")
        testImplementation("io.mockk:mockk:1.13.8")
        testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.7.3")
    }

    tasks.test {
        useJUnitPlatform()
    }

    kotlin {
        jvmToolchain(21)
    }
}
