buildscript {
    repositories {
        google()
        mavenCentral()
    }
    dependencies {
        // المحافظة على إصدار كوتلن المتوافق الذي أصلحناه سابقاً
        classpath("org.jetbrains.kotlin:kotlin-gradle-plugin:2.0.0")
    }
}

plugins {
    // فرض استخدام إصدار مستقر وآمن من أدوات أندرويد لتجنب أزمة AGP 9+
    id("com.android.application") version "8.5.0" apply false
}
