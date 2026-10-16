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
    const val DEFAULT_SERVER = "https://sohambhongade.pythonanywhere.com"

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

    /** Time of the last sync attempt of any kind (0 = never). Used for the 15-minute limit. */
    fun lastAttemptAt(c: Context) = sp(c).getLong(KEY_LAST_ATTEMPT, 0L)
    fun lastMessage(c: Context) = sp(c).getString(KEY_LAST_MESSAGE, "") ?: ""
    fun lastOk(c: Context) = sp(c).getBoolean(KEY_LAST_OK, true)

    fun recordAttempt(c: Context, now: Long) = sp(c).edit { putLong(KEY_LAST_ATTEMPT, now) }

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
