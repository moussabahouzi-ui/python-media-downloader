package com.mediahub.app.services

import android.content.Context
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.mediahub.app.bridge.MethodChannelContract
import io.flutter.plugin.common.MethodChannel
import java.util.concurrent.TimeUnit

/**
 * Schedules periodic checks for due download schedules via WorkManager.
 *
 * The [ScheduleCheckWorker] runs every ~5 minutes (the minimum WorkManager
 * periodic interval), calls `scheduler.due` on the Python engine via the
 * method channel, and enqueues each due URL as a download task via
 * `download.enqueue`.
 *
 * This is the Android-side counterpart of the Python `SchedulerRepository`.
 */
object DownloadScheduler {

    private const val WORK_NAME = "mediahub.schedule-check"

    /** Starts the periodic schedule-check worker. Idempotent. */
    fun start(context: Context) {
        val constraints = Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build()

        val request = PeriodicWorkRequestBuilder<ScheduleCheckWorker>(
            15, TimeUnit.MINUTES, // WorkManager minimum periodic interval
        )
            .setConstraints(constraints)
            .build()

        WorkManager.getInstance(context).enqueueUniquePeriodicWork(
            WORK_NAME,
            ExistingPeriodicWorkPolicy.KEEP,
            request,
        )
    }

    /** Cancels the periodic schedule-check worker. */
    fun stop(context: Context) {
        WorkManager.getInstance(context).cancelUniqueWork(WORK_NAME)
    }
}

/**
 * The WorkManager worker that polls the Python engine for due schedules and
 * enqueues them as downloads.
 *
 * Communication with the engine goes through the foreground service's
 * [MethodChannel], which the [DownloadForegroundService] exposes as a
 * singleton.
 */
class ScheduleCheckWorker(
    appContext: Context,
    params: WorkerParameters,
) : CoroutineWorker(appContext, params) {

    override suspend fun doWork(): Result {
        val runtime = DownloadForegroundService.runtime() ?: return Result.retry()

        // Ask the engine for due schedules.
        val dueResponse = runtime.call("scheduler.due", emptyMap<String, Any?>())
        if (dueResponse == null || dueResponse.has("error")) {
            return Result.retry()
        }

        val result = dueResponse.optJSONObject("result") ?: return Result.success()
        val schedules = result.optJSONArray("schedules") ?: return Result.success()

        for (i in 0 until schedules.length()) {
            val schedule = schedules.optJSONObject(i) ?: continue
            val url = schedule.optString("url")
            val scheduleId = schedule.optString("scheduleId")
            val priority = schedule.optInt("priority", 5)

            if (url.isBlank()) continue

            // Enqueue the download.
            runtime.call(
                "download.enqueue",
                mapOf(
                    "url" to url,
                    "priority" to priority,
                ),
            )

            // Mark the schedule as run so it advances to the next run time.
            runtime.call(
                "scheduler.mark_run",
                mapOf("scheduleId" to scheduleId),
            )
        }

        return Result.success()
    }
}
