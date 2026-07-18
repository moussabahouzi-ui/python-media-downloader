package com.mediahub.app.notifications

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.os.Build
import androidx.core.app.NotificationManagerCompat

/**
 * Centralized notification channel registration. Called once from
 * [com.mediahub.app.MediaHubApplication.onCreate].
 */
object NotificationChannels {

    const val CHANNEL_DOWNLOADS = "mediahub.downloads"
    const val CHANNEL_ENGINE = "mediahub.engine"

    fun register(context: Context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val manager = context.getSystemService(NotificationManager::class.java) ?: return

        manager.createNotificationChannel(
            NotificationChannel(
                CHANNEL_DOWNLOADS,
                context.getString(com.mediahub.app.R.string.notification_channel_downloads),
                NotificationManager.IMPORTANCE_LOW,
            ).apply {
                description = context.getString(
                    com.mediahub.app.R.string.notification_channel_downloads_desc,
                )
                setShowBadge(false)
            },
        )

        manager.createNotificationChannel(
            NotificationChannel(
                CHANNEL_ENGINE,
                context.getString(com.mediahub.app.R.string.notification_channel_engine),
                NotificationManager.IMPORTANCE_MIN,
            ).apply {
                description = context.getString(
                    com.mediahub.app.R.string.notification_channel_engine_desc,
                )
                setShowBadge(false)
            },
        )
    }

    fun isAvailable(context: Context): Boolean =
        NotificationManagerCompat.from(context).areNotificationsEnabled()
}
