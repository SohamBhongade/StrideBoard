plugins {
    id("com.android.application")
}

android {
    namespace = "com.strideboard.app"
    compileSdk = 37

    defaultConfig {
        applicationId = "com.strideboard.app"
        minSdk = 26          // Health Connect library minimum
        targetSdk = 36
        versionCode = 2
        versionName = "1.1"
    }

    buildTypes {
        debug {
            // Debug builds may talk to a laptop over plain http:// for testing.
            manifestPlaceholders["usesCleartextTraffic"] = "true"
        }
        release {
            // Release builds: https:// only.
            manifestPlaceholders["usesCleartextTraffic"] = "false"
            isMinifyEnabled = false
            // Sideloaded hackathon APK: sign with the built-in debug key so no keystore is needed.
            // Phones can only install updates signed with the same key, so build every APK on
            // the same computer (see README).
            signingConfig = signingConfigs.getByName("debug")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.19.1")
    implementation("androidx.activity:activity-ktx:1.13.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.11.0")
    implementation("androidx.work:work-runtime-ktx:2.11.2")
    implementation("androidx.health.connect:connect-client:1.1.0")
}
