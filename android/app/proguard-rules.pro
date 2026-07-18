# MediaHub R8 / ProGuard rules

# --- Flutter engine ---
# Flutter ships its own consumer rules; keep the engine entry points safe.
-keep class io.flutter.app.** { *; }
-keep class io.flutter.plugin.**  { *; }
-keep class io.flutter.util.**  { *; }
-keep class io.flutter.view.**  { *; }
-keep class io.flutter.**  { *; }
-keep class io.flutter.plugins.**  { *; }

# --- MediaHub bridge contract ---
# The method-channel envelope is reflected by method name; keep handlers.
-keep class com.mediahub.app.bridge.** { *; }
-keepclassmembers class com.mediahub.app.** {
    public *;
}

# --- Kotlinx coroutines ---
-dontwarn kotlinx.coroutines.**

# --- Method channel reflection safety ---
-keepattributes RuntimeVisibleAnnotations,RuntimeVisibleParameterAnnotations,Signature,InnerClasses,EnclosingMethod
