package com.mediahub.app

import android.app.Application
import android.util.Log
import com.mediahub.app.notifications.NotificationChannels
import com.mediahub.app.services.DownloadScheduler
import com.mediahub.app.storage.SecurePreferences

/**
 * Application entry point. Performs one-time, process-wide setup:
 *  - registers notification channels
 *  - initializes secure (encrypted) preferences
 *  - starts the WorkManager schedule-check worker
 *
 * The Flutter engine is configured by the embedding; this class only owns
 * native-side concerns. The method-channel bridge is attached from
 * [MainActivity].
 */
class MediaHubApplication : Application() {

    override fun onCreate() {
        super.onCreate()
        instance = this
        NotificationChannels.register(this)
        SecurePreferences.init(this)
        DownloadScheduler.start(this)
        Log.i(TAG, "MediaHub application initialized (secure prefs + scheduler)")
    }

    companion object {
        private const val TAG = "MediaHubApp"

        @Volatile private var instance: MediaHubApplication? = null
        fun get(): MediaHubApplication =
            instance ?: error("MediaHubApplication not yet created")
    }
}
