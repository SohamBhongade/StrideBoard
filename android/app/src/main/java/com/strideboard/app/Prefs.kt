package com.strideboard.app

import android.content.Context
import android.content.pm.ApplicationInfo
import android.net.Uri
import androidx.core.content.edit

/**
 * Everything the app remembers, kept in private app storage.
 * The token is a password: it is never logged, and backups are turned off in the manifest.
 */
object Prefs {
    /** The live StrideBoard server (Agent 1). Pre-filled on the setup screen; can be changed there. */
    const val DEFAULT_SERVER = "https://strideboard.pythonanywhere.com"

    /** Where StrideBoard used to live. Phones still set to these move to DEFAULT_SERVER by themselves. */
    private val OLD_SERVERS = setOf("https://sohambhongade.pythonanywhere.com")

    private const val FILE = "strideboard"
    private const val KEY_SERVER = "server_url"
    private const val KEY_TOKEN = "token"
    private const val KEY_LAST_SUCCESS = "last_success_at"
    private const val KEY_LAST_ATTEMPT = "last_attempt_at"
    private const val KEY_LAST_MESSAGE = "last_message"
    private const val KEY_LAST_OK = "last_ok"

    private fun sp(c: Context) = c.getSharedPreferences(FILE, Context.MODE_PRIVATE)

    fun serverUrl(c: Context): String = sp(c).getString(KEY_SERVER, "") ?: ""
    fun token(c: Context): String = sp(c).getString(KEY_TOKEN, "") ?: ""
    fun isConfigured(c: Context) = serverUrl(c).isNotBlank() && token(c).isNotBlank()

    /** First run: use the school's website without asking. A phone set to an old address moves
     *  to the new one; its token still works because the accounts moved with the website. */
    fun ensureServer(c: Context) {
        val now = serverUrl(c)
        if (now.isBlank() || now.trimEnd('/').lowercase() in OLD_SERVERS) {
            sp(c).edit { putString(KEY_SERVER, DEFAULT_SERVER) }
        }
    }

    /** A token looks like letters, digits, - and _ (what the website makes). */
    private val TOKEN_SHAPE = Regex("^[A-Za-z0-9_-]{16,128}$")

    /**
     * The website hands over the logged-in person's token (see MainActivity.AppBridge), so
     * nobody has to copy or paste it. Returns true if this phone is now linked to a different
     * account than before.
     */
    fun linkToken(c: Context, token: String): Boolean {
        val t = token.trim()
        if (!TOKEN_SHAPE.matches(t) || t == token(c)) return false
        saveSetup(c, serverUrl(c).ifBlank { DEFAULT_SERVER }, t)
        return true
    }

    fun saveSetup(c: Context, server: String, token: String) {
        val changed = server != serverUrl(c) || token != token(c)
        sp(c).edit {
            putString(KEY_SERVER, server)
            putString(KEY_TOKEN, token)
            if (changed) {
                // Old sync results belonged to the old address/token.
                remove(KEY_LAST_SUCCESS)
                remove(KEY_LAST_ATTEMPT)
                remove(KEY_LAST_MESSAGE)
                remove(KEY_LAST_OK)
            }
        }
    }

    /** Time of the last sync that fully worked (0 = never). */
    fun lastSuccessAt(c: Context) = sp(c).getLong(KEY_LAST_SUCCESS, 0L)

    /** Time of the last sync attempt of any kind (0 = never). */
    fun lastAttemptAt(c: Context) = sp(c).getLong(KEY_LAST_ATTEMPT, 0L)
    fun lastMessage(c: Context) = sp(c).getString(KEY_LAST_MESSAGE, "") ?: ""
    fun lastOk(c: Context) = sp(c).getBoolean(KEY_LAST_OK, true)

    fun recordAttempt(c: Context, now: Long) = sp(c).edit { putLong(KEY_LAST_ATTEMPT, now) }

    // ---- What was last sent for each day, so unchanged totals aren't sent again.
    private const val SENT_STEPS = "sent_steps_"
    private const val SENT_AT = "sent_at_"

    fun lastSentSteps(c: Context, date: String) = sp(c).getLong(SENT_STEPS + date, -1L)
    fun lastSentAt(c: Context, date: String) = sp(c).getLong(SENT_AT + date, 0L)

    /** Remember a day's total was accepted by the server. Forgets days older than yesterday. */
    fun markSent(c: Context, date: String, steps: Long, now: Long, keepDates: Set<String>) {
        val prefs = sp(c)
        prefs.edit {
            putLong(SENT_STEPS + date, steps)
            putLong(SENT_AT + date, now)
            for (key in prefs.all.keys) {
                val d = key.removePrefix(SENT_STEPS).removePrefix(SENT_AT)
                if ((key.startsWith(SENT_STEPS) || key.startsWith(SENT_AT)) && d !in keepDates) remove(key)
            }
        }
    }

    /** Today's total as last read from Health Connect (-1 = not read yet), for the live dashboard. */
    private const val KEY_TODAY_READ = "today_read"
    private const val KEY_TODAY_READ_DATE = "today_read_date"
    fun todayRead(c: Context, date: String): Long =
        if (sp(c).getString(KEY_TODAY_READ_DATE, "") == date) sp(c).getLong(KEY_TODAY_READ, -1L) else -1L
    fun setTodayRead(c: Context, date: String, steps: Long) =
        sp(c).edit { putString(KEY_TODAY_READ_DATE, date); putLong(KEY_TODAY_READ, steps) }

    fun recordResult(c: Context, ok: Boolean, message: String, now: Long = System.currentTimeMillis()) {
        sp(c).edit {
            putBoolean(KEY_LAST_OK, ok)
            putString(KEY_LAST_MESSAGE, message)
            if (ok) putLong(KEY_LAST_SUCCESS, now)
        }
    }

    /**
     * Cleans up what the user typed: trims it, adds https:// if no scheme was given, and removes
     * trailing slashes. Returns null if it doesn't look like a web address.
     */
    fun normalizeServer(input: String): String? {
        var s = input.trim()
        if (s.isEmpty()) return null
        if (!s.startsWith("http://", ignoreCase = true) && !s.startsWith("https://", ignoreCase = true)) {
            s = "https://$s"
        }
        s = s.trimEnd('/')
        val host = Uri.parse(s).host
        if (host.isNullOrBlank() || host.contains(' ')) return null
        return s
    }
}

/** True for debug builds (which may use http:// for laptop testing). */
fun Context.isDebugBuild(): Boolean =
    (applicationInfo.flags and ApplicationInfo.FLAG_DEBUGGABLE) != 0
