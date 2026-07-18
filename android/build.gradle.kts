buildscript {
    repositories {
        google()
        mavenCentral()
    }
    dependencies {
        classpath("org.jetbrains.kotlin:kotlin-gradle-plugin:2.0.0")
    }
}

plugins {
    // 💎 التطابق التام: تحديث الإصدار إلى 8.7.0 ليتزامن مع ملف الـ settings وينتهي التعارض
    id("com.android.application") version "8.7.0" apply false
}
