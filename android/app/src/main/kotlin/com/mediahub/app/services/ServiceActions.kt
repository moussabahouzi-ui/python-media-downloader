package com.mediahub.app.services

import android.content.Context
import android.content.Intent

/**
 * Strongly-typed action constants and intent builder for
 * [DownloadForegroundService]. Using explicit builder functions keeps the
 * Intent contract in one place and avoids stringly-typed callers.
 */
object ServiceActions {
    const val ACTION_START_ENGINE = "com.mediahub.app.action.START_ENGINE"
    const val ACTION_STOP_ENGINE = "com.mediahub.app.action.STOP_ENGINE"
    const val ACTION_PING = "com.mediahub.app.action.PING"

    fun startEngine(context: Context): Intent =
        Intent(context, DownloadForegroundService::class.java).apply {
            action = ACTION_START_ENGINE
        }

    fun stopEngine(context: Context): Intent =
        Intent(context, DownloadForegroundService::class.java).apply {
            action = ACTION_STOP_ENGINE
        }
}
