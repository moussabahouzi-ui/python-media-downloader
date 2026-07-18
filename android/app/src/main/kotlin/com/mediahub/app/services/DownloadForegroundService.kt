package com.mediahub.app.services

import android.app.Notification
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.mediahub.app.MainActivity
import com.mediahub.app.R
import com.mediahub.app.notifications.NotificationChannels
import com.mediahub.app.runtime.PythonRuntime
import com.mediahub.app.runtime.PythonRuntimeConfig
import com.mediahub.app.storage.StoragePaths

/**
 * The long-lived foreground service that hosts the embedded Python runtime.
 *
 * Why a foreground service?
 *  - Android 14+ requires a foreground service for long-running work that
 *    survives Activity recreation.
 *  - It gives the OS a clear signal that the media engine is active, so it
 *    won't be killed during background execution.
 *  - It owns the single [PythonRuntime] instance shared with the method
 *    channel handler.
 *
 * The service is started on demand by the bridge when Flutter first pings the
 * engine, and remains alive until the user explicitly stops it (or the system
 * reclaims it under memory pressure).
 */
class DownloadForegroundService : Service() {

    @Volatile private var runtime: PythonRuntime? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        startForegroundTyped(buildNotification("Media engine ready"))
    }

    /**
     * Calls the typed [startForeground] overload on Android 10+ so the system
     * knows this is a `dataSync` service (required on Android 14+).
     */
    private fun startForegroundTyped(notification: Notification) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(
                NOTIFICATION_ID,
                notification,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC,
            )
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ServiceActions.ACTION_START_ENGINE -> ensureRuntime()
            ServiceActions.ACTION_STOP_ENGINE -> {
                stopEngine()
                stopForeground(STOP_FOREGROUND_REMOVE)
                stopSelf()
            }
            ServiceActions.ACTION_PING -> ensureRuntime()
        }
        // START_STICKY: recreate if killed, so downloads can resume.
        return START_STICKY
    }

    /** Lazily creates and starts the [PythonRuntime]. Thread-safe. */
    @Synchronized
    private fun ensureRuntime(): PythonRuntime {
        runtime?.let { return it }
        val config = PythonRuntimeConfig.forApp(this)
        val rt = PythonRuntime(this, config)
        runtime = rt
        return rt
    }

    private fun stopEngine() {
        runtime?.dispose()
        runtime = null
    }

    override fun onDestroy() {
        stopEngine()
        unbind()
        super.onDestroy()
    }

    /** Exposed for the bridge to obtain the singleton runtime. */
    companion object {
        const val NOTIFICATION_ID = 1001

        @Volatile private var instance: DownloadForegroundService? = null
        internal fun bind(service: DownloadForegroundService) { instance = service }
        internal fun unbind() { instance = null }

        /** Returns the currently-running runtime, if any. */
        fun runtime(): PythonRuntime? = instance?.runtime

        fun start(context: android.content.Context) {
            // startForegroundService requires API 26+; fall back to startService.
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(ServiceActions.startEngine(context))
            } else {
                context.startService(ServiceActions.startEngine(context))
            }
        }

        fun stop(context: android.content.Context) {
            context.startService(ServiceActions.stopEngine(context))
        }
    }

    init {
        // Make the singleton instance available to the bridge via [runtime()].
        bind(this)
    }

    private fun buildNotification(text: String): Notification {
        val launchIntent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP
        }
        val contentIntent = PendingIntent.getActivity(
            this,
            0,
            launchIntent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )

        return NotificationCompat.Builder(this, NotificationChannels.CHANNEL_DOWNLOADS)
            .setContentTitle(getString(R.string.download_notification_title))
            .setContentText(text)
            .setSmallIcon(R.drawable.ic_notification)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setContentIntent(contentIntent)
            .setForegroundServiceBehavior(NotificationCompat.FOREGROUND_SERVICE_IMMEDIATE)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
    }
}
