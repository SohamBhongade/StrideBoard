plugins {
    id("com.android.application")
}

android {
    namespace = "com.strideboard.app"
    compileSdk = 37

    defaultConfig {
        // New id from 1.4 on: the first builds (com.strideboard.app) were each signed with a
        // different throwaway key, so they can't be updated. This app installs beside the old
        // one and then offers to remove it (MainActivity.offerToRemoveOldApp).
        applicationId = "com.strideboard.android"
        minSdk = 26          // Health Connect library minimum
        targetSdk = 36
        versionCode = 6
        versionName = "1.5"
    }

    // One fixed key for every release, so each new APK installs over the last one (and the
    // in-app updater works). GitHub fills these from the repo's secrets; on a laptop without
    // them the build falls back to the debug key.
    val keystorePath = System.getenv("STRIDEBOARD_KEYSTORE")
    signingConfigs {
        if (keystorePath != null && file(keystorePath).exists()) {
            create("release") {
                storeFile = file(keystorePath)
                storePassword = System.getenv("STRIDEBOARD_KEYSTORE_PASSWORD")
                keyAlias = "strideboard"
                keyPassword = System.getenv("STRIDEBOARD_KEYSTORE_PASSWORD")
            }
        }
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
            signingConfig = signingConfigs.findByName("release") ?: signingConfigs.getByName("debug")
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
