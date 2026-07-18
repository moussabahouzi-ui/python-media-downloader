package com.mediahub.app.storage

import android.content.Context
import android.content.SharedPreferences
import android.os.Build
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

/**
 * Secure preferences backed by [EncryptedSharedPreferences] (Android Keystore).
 *
 * Stores sensitive data that must survive process restarts but must not be
 * readable without the device unlock key: provider session tokens, the engine
 * encryption key, etc.
 *
 * On Android < 6.0 (API 23) where EncryptedSharedPreferences is unavailable,
 * falls back to standard SharedPreferences (with a logged warning). The
 * `standard` flavor targets API 24+ so this is a safety net only.
 */
object SecurePreferences {

    private const val PREFS_NAME = "mediahub_secure"
    private const val KEY_ENGINE_ENCRYPTION_KEY = "engine.encryption_key"

    @Volatile private var prefs: SharedPreferences? = null

    /** Initializes the secure preferences. Call from [MediaHubApplication.onCreate]. */
    fun init(context: Context) {
        prefs = try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                val masterKey = MasterKey.Builder(context)
                    .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
                    .build()
                EncryptedSharedPreferences.create(
                    context,
                    PREFS_NAME,
                    masterKey,
                    EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                    EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
                )
            } else {
                context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            }
        } catch (e: Exception) {
            // Fallback: standard prefs (not encrypted, but functional).
            android.util.Log.w("SecurePreferences", "Falling back to plain prefs", e)
            context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        }
    }

    /** Returns the engine encryption key, generating one if absent. */
    fun getEngineEncryptionKey(): ByteArray {
        val p = prefs ?: error("SecurePreferences not initialized")
        val existing = p.getString(KEY_ENGINE_ENCRYPTION_KEY, null)
        if (existing != null) {
            return android.util.Base64.decode(existing, android.util.Base64.DEFAULT)
        }
        // Generate a 256-bit key.
        val key = ByteArray(32).also { java.security.SecureRandom().nextBytes(it) }
        p.edit()
            .putString(KEY_ENGINE_ENCRYPTION_KEY, android.util.Base64.encodeToString(key, android.util.Base64.DEFAULT))
            .apply()
        return key
    }

    fun setString(key: String, value: String) {
        prefs?.edit()?.putString(key, value)?.apply()
    }

    fun getString(key: String, default: String? = null): String? {
        return prefs?.getString(key, default)
    }

    fun remove(key: String) {
        prefs?.edit()?.remove(key)?.apply()
    }

    fun clear() {
        prefs?.edit()?.clear()?.apply()
    }
}
