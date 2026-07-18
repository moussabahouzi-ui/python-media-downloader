buildscript {
    dependencies {
        classpath("org.jetbrains.kotlin:kotlin-gradle-plugin:2.0.0")
    }
}

plugins {
    alias(libs.plugins.android.application) apply false
}
