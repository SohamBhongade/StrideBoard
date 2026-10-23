package com.strideboard.app

import android.content.Context
import androidx.health.connect.client.HealthConnectClient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.text.NumberFormat
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Locale

enum class SyncOutcome {
    SUCCESS,
    NOTHING_TO_SEND,
    /** Network or temporary problem: the background job should try again. */
    RETRY,
    /** Something the user must fix (token, permission, address). Don't retry. */
    NEEDS_ATTENTION,
    /** Background run on a phone that doesn't allow background reads: quietly do nothing. */
    SKIPPED,
}

/**
 * One sync: read yesterday + today from Health Connect, skip zero totals, POST each day.
 * Used by the background job, the "Sync now" button and the sync-on-open.
 */
object SyncRunner {
    private val lock = Mutex()

    /**
     * Today's total is re-sent at least this often even if it hasn't changed: the website
     * uses those check-ins to tell when someone has been sitting still (stand-up reminder).
     */
    private const val RESEND_UNCHANGED_MS = 5 * 60 * 1000L

    /** force = send both days even if unchanged (the "Sync now" button). */
    suspend fun run(context: Context, inBackground: Boolean, force: Boolean = false): SyncOutcome =
        lock.withLock {
            withContext(Dispatchers.IO) { runLocked(context.applicationContext, inBackground, force) }
        }

    private suspend fun runLocked(c: Context, inBackground: Boolean, force: Boolean): SyncOutcome {
        val now = System.currentTimeMillis()
        Prefs.recordAttempt(c, now)

        if (!Prefs.isConfigured(c)) {
            Prefs.recordResult(c, false, "Log in on the StrideBoard screen to link this phone.")
            return SyncOutcome.NEEDS_ATTENTION
        }

        val status = StepReader.status(c)
        if (!status.available) {
            Prefs.recordResult(c, false, healthConnectProblem(status.sdkStatus))
            return SyncOutcome.NEEDS_ATTENTION
        }
        if (!status.stepsGranted) {
            Prefs.recordResult(c, false, "Step access is off. Tap \"Allow step access\".")
            return SyncOutcome.NEEDS_ATTENTION
        }
        if (inBackground && !status.backgroundGranted) {
            // This phone only lets us read while the app is open; sync-on-open covers it.
            return SyncOutcome.SKIPPED
        }

        val days = try {
            StepReader.readRecentDays(c)
        } catch (e: SecurityException) {
            Prefs.recordResult(c, false, "Health Connect blocked the step read. Open the app and tap Sync now.")
            return SyncOutcome.NEEDS_ATTENTION
        } catch (e: Exception) {
            Prefs.recordResult(c, false, "Couldn't read steps from Health Connect. Will try again.")
            return SyncOutcome.RETRY
        }

        val todayDate = LocalDate.now(StepReader.DUBAI)
        days.firstOrNull { it.date == todayDate }?.let { Prefs.setTodayRead(c, it.date.toString(), it.steps) }

        // Never send 0. Skip a day whose total the server already has, except that today
        // is re-sent every few minutes (see RESEND_UNCHANGED_MS).
        val toSend = days.filter { day ->
            val d = day.date.toString()
            val unchanged = Prefs.lastSentSteps(c, d) == day.steps
            val recentlySent = now - Prefs.lastSentAt(c, d) < RESEND_UNCHANGED_MS
            day.steps > 0 && (force || !unchanged || (day.date == todayDate && !recentlySent))
        }
        if (toSend.isEmpty()) {
            val anySteps = days.any { it.steps > 0 }
            Prefs.recordResult(c, true, if (anySteps) "Up to date." else
                "No steps recorded in the last week yet, so nothing was sent.")
            return SyncOutcome.NOTHING_TO_SEND
        }
        val keepDates = days.map { it.date.toString() }.toSet()

        Prefs.ensureServer(c)   // moves an old website address to the new one
        val server = Prefs.serverUrl(c)
        val token = Prefs.token(c)
        val sent = mutableListOf<String>()
        val problems = mutableListOf<String>()
        var weekly: Long? = null
        var tier: String? = null
        var tryLater: String? = null

        for (day in toSend) {
            val label = "${dayLabel(day.date)} ${fmt(day.steps)}"
            when (val r = ApiClient.postSteps(server, token, day.date.toString(), day.steps)) {
                is ApiResult.Ok -> {
                    Prefs.markSent(c, day.date.toString(), day.steps, now, keepDates)
                    sent += label
                    r.weeklyTotal?.let { weekly = it }
                    r.tier?.let { tier = it }
                }
                is ApiResult.Rejected -> problems += "${dayLabel(day.date)}: ${r.message}"
                ApiResult.BadToken -> {
                    Prefs.recordResult(c, false,
                        "Your token was not accepted. Copy it again from Settings on the website and paste it here.")
                    return SyncOutcome.NEEDS_ATTENTION
                }
                is ApiResult.TryLater -> {
                    tryLater = r.message
                    break
                }
            }
        }

        val sentText = if (sent.isEmpty()) "" else "Sent: ${sent.joinToString(" · ")}. "
        return when {
            tryLater != null -> {
                Prefs.recordResult(c, false, "${sentText}Couldn't reach StrideBoard ($tryLater). Will try again.")
                SyncOutcome.RETRY
            }
            problems.isNotEmpty() -> {
                Prefs.recordResult(c, false, sentText + problems.joinToString(" "))
                SyncOutcome.NEEDS_ATTENTION
            }
            else -> {
                val week = weekly?.let { " This week: ${fmt(it)}" + (tier?.let { t -> " ($t)" } ?: "") + "." } ?: ""
                Prefs.recordResult(c, true, "Sent: ${sent.joinToString(" · ")}.$week")
                SyncOutcome.SUCCESS
            }
        }
    }

    private fun dayLabel(date: LocalDate): String {
        val today = LocalDate.now(StepReader.DUBAI)
        return when (date) {
            today -> "Today"
            today.minusDays(1) -> "Yesterday"
            else -> date.format(DateTimeFormatter.ofPattern("EEE d MMM", Locale.US))   // e.g. "Mon 19 Oct"
        }
    }

    private fun fmt(n: Long): String = NumberFormat.getIntegerInstance(Locale.US).format(n)

    fun healthConnectProblem(sdkStatus: Int): String = when (sdkStatus) {
        HealthConnectClient.SDK_UNAVAILABLE_PROVIDER_UPDATE_REQUIRED ->
            "Health Connect needs to be installed or updated. Tap \"Allow step access\" to open the Play Store."
        else ->
            "Health Connect is not available on this phone (it needs Android 9 or newer). " +
                "You can still type your steps on the website's Log page."
    }
}
