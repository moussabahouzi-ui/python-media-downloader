plugins {
    id("com.android.application")
    id("kotlin-android")
    // The Flutter Gradle Plugin must be applied after Android and Kotlin.
    id("dev.flutter.flutter-gradle-plugin")
}

val mediahubVersionName: String = providers.gradleProperty("mediahub.versionName")
    .getOrElse("0.1.0")
val mediahubVersionCode: String = providers.gradleProperty("mediahub.versionCode")
    .getOrElse("1").trim()

android {
    namespace = "com.mediahub.app"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.mediahub.app"
        minSdk = 24
        targetSdk = 34
        versionCode = mediahubVersionCode.toInt()
        versionName = mediahubVersionName

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        vectorDrawables { useSupportLibrary = true }
    }

    // Product flavors — see docs/ARCHITECTURE.md §9.
    flavorDimensions += "distribution"
    productFlavors {
        create("standard") {
            dimension = "distribution"
            // Public build: scoped storage only.
            buildConfigField("boolean", "FULL_STORAGE", "false")
        }
        create("full") {
            dimension = "distribution"
            // Power-user build: advanced storage modes (opt-in at runtime).
            buildConfigField("boolean", "FULL_STORAGE", "true")
        }
    }

    buildTypes {
        debug {
            isMinifyEnabled = false
            applicationIdSuffix = ".debug"
            versionNameSuffix = "-debug"
        }
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
            // R8 full mode for stricter optimization.
            signingConfig = signingConfigs.findByName("release")
        }
    }

    signingConfigs {
        create("release") {
            val keyProps = file("key.properties")
            if (keyProps.exists()) {
                val props = java.util.Properties()
                keyProps.inputStream().use { props.load(it) }
                storeFile = file(props.getProperty("storeFile"))
                storePassword = props.getProperty("storePassword")
                keyAlias = props.getProperty("keyAlias")
                keyPassword = props.getProperty("keyPassword")
            }
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
        freeCompilerArgs = freeCompilerArgs + listOf(
            "-opt-in=kotlin.RequiresOptIn",
            "-opt-in=kotlinx.coroutines.ExperimentalCoroutinesApi",
        )
    }

    buildFeatures {
        buildConfig = true
    }

    packaging {
        resources {
            excludes += setOf(
                "/META-INF/{AL2.0,LGPL2.1}",
                "META-INF/DEPENDENCIES",
                "META-INF/LICENSE*",
                "META-INF/NOTICE*",
            )
        }
    }

    testOptions {
        unitTests.isReturnDefaultValues = true
        unitTests.isIncludeAndroidResources = true
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.appcompat)
    implementation(libs.androidx.lifecycle.runtime)
    implementation(libs.androidx.lifecycle.service)
    implementation(libs.androidx.work.runtime)
    implementation(libs.androidx.security.crypto)
    implementation(libs.kotlinx.coroutines.android)

    testImplementation(libs.junit)
    androidTestImplementation(libs.androidx.junit)
    androidTestImplementation(libs.androidx.espresso.core)
}
