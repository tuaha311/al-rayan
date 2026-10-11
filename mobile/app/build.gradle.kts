import java.util.Properties

plugins {
    id("com.android.application")
}

// Release signing lives outside the repo (see mobile/README.md). Without it the
// release build is simply unsigned rather than failing, so CI and fresh clones
// can still compile.
val keystoreProps = Properties().apply {
    val f = rootProject.file("keystore.properties")
    if (f.exists()) f.inputStream().use { load(it) }
}

android {
    namespace = "pk.alrayan.app"
    compileSdk = 35

    defaultConfig {
        applicationId = "pk.floralfinesse.app"
        minSdk = 24
        targetSdk = 35
        versionCode = 1
        versionName = "1.0.0"

        val baseUrl = (project.findProperty("alrayan.baseUrl") as String?)
            ?.trimEnd('/')
            ?: error("alrayan.baseUrl is missing from gradle.properties")
        buildConfigField("String", "BASE_URL", "\"$baseUrl\"")
        // Cleartext stays off unless the storefront itself is plain http
        // (e.g. a staging IP); an https base URL keeps it blocked.
        manifestPlaceholders["usesCleartextTraffic"] = baseUrl.startsWith("http://").toString()
    }

    signingConfigs {
        if (keystoreProps.getProperty("storeFile") != null) {
            create("release") {
                storeFile = rootProject.file(keystoreProps.getProperty("storeFile"))
                storePassword = keystoreProps.getProperty("storePassword")
                keyAlias = keystoreProps.getProperty("keyAlias")
                keyPassword = keystoreProps.getProperty("keyPassword")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            isShrinkResources = false
            signingConfig = signingConfigs.findByName("release")
        }
        debug {
            applicationIdSuffix = ".debug"
        }
    }

    buildFeatures {
        buildConfig = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

// No dependencies on purpose: the app is a WebView shell built entirely against
// the platform SDK, which keeps the APK a few hundred KB.
dependencies { }
