package com.strideboard.app

import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import java.time.Duration
import java.time.ZonedDateTime
import java.util.concurrent.TimeUnit

/** The background job. Retries network problems (up to 3 times), never 400/401 problems. */
class SyncWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result =
        when (SyncRunner.run(applicationContext, inBackground = true)) {
            SyncOutcome.RETRY -> if (runAttemptCount < 3) Result.retry() else Result.success()
            else -> Result.success()
        }
}

/** Schedules the background job: every 3 hours, plus a nightly run around 23:30 Dubai time. */
object SyncScheduler {
    private const val EVERY_3_HOURS = "strideboard-sync-3h"
    private const val NIGHTLY = "strideboard-sync-nightly"

    /**
     * Call whenever settings or permissions might have changed.
     * Background jobs only exist if the phone allows background reads; otherwise the app
     * syncs when it is opened.
     */
    fun update(c: Context, backgroundAllowed: Boolean) {
        val wm = WorkManager.getInstance(c)
        if (!backgroundAllowed || !Prefs.isConfigured(c)) {
            wm.cancelUniqueWork(EVERY_3_HOURS)
            wm.cancelUniqueWork(NIGHTLY)
            return
        }
        val needsNetwork = Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build()

        val every3h = PeriodicWorkRequestBuilder<SyncWorker>(3, TimeUnit.HOURS)
            .setConstraints(needsNetwork)
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 5, TimeUnit.MINUTES)
            .build()
        wm.enqueueUniquePeriodicWork(EVERY_3_HOURS, ExistingPeriodicWorkPolicy.KEEP, every3h)

        val nightly = PeriodicWorkRequestBuilder<SyncWorker>(24, TimeUnit.HOURS)
            .setInitialDelay(millisUntil(23, 30), TimeUnit.MILLISECONDS)
            .setConstraints(needsNetwork)
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 5, TimeUnit.MINUTES)
            .build()
        wm.enqueueUniquePeriodicWork(NIGHTLY, ExistingPeriodicWorkPolicy.KEEP, nightly)
    }

    private fun millisUntil(hour: Int, minute: Int): Long {
        val now = ZonedDateTime.now(StepReader.DUBAI)
        var next = now.toLocalDate().atTime(hour, minute).atZone(StepReader.DUBAI)
        if (!next.isAfter(now)) next = next.plusDays(1)
        return Duration.between(now, next).toMillis()
    }
}
