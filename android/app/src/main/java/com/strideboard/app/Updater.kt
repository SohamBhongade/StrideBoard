package com.strideboard.app

import android.app.Activity
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInstaller
import android.net.Uri
import android.os.Build
import android.provider.Settings
import android.widget.Toast
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.net.HttpURLConnection
import java.net.URL

/**
 * Updates the app from inside the app. The website's Home page shows a small "Update" notice
 * when a newer version is out; tapping it downloads the newest StrideBoard.apk from the
 * GitHub Releases page and hands it to Android, which asks "Update StrideBoard?" (one tap).
 * Android never lets an app from outside the Play Store update with no tap at all.
 */
object Updater {
    const val APK_URL =
        "https://github.com/SohamBhongade/StrideBoard/releases/download/android-latest/StrideBoard.apk"
    private const val ACTION_STATUS = "com.strideboard.app.UPDATE_STATUS"

    fun versionCode(c: Context): Long {
        val info = c.packageManager.getPackageInfo(c.packageName, 0)
        return if (Build.VERSION.SDK_INT >= 28) info.longVersionCode
        else @Suppress("DEPRECATION") info.versionCode.toLong()
    }

    /** Returns null when Android's "Update StrideBoard?" box is on its way, or a message to show. */
    suspend fun downloadAndInstall(activity: Activity): String? = withContext(Dispatchers.IO) {
        // The first time, Android asks the person to allow StrideBoard to install updates.
        if (!activity.packageManager.canRequestPackageInstalls()) {
            withContext(Dispatchers.Main) {
                activity.startActivity(
                    Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:${activity.packageName}"))
                )
            }
            return@withContext "Turn on \"Allow from this source\", come back, and tap Update again."
        }
        val installer = activity.packageManager.packageInstaller
        val params = PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL)
        params.setAppPackageName(activity.packageName)
        val sessionId = installer.createSession(params)
        val session = installer.openSession(sessionId)
        try {
            // GitHub sends the file from another address (a redirect), so follow up to 5 hops.
            var url = URL(APK_URL)
            var conn: HttpURLConnection
            var hops = 0
            while (true) {
                conn = url.openConnection() as HttpURLConnection
                conn.instanceFollowRedirects = false
                conn.connectTimeout = 15_000
                conn.readTimeout = 60_000
                val code = conn.responseCode
                if (code in 300..399 && hops++ < 5) {
                    url = URL(url, conn.getHeaderField("Location"))
                    conn.disconnect()
                    continue
                }
                if (code != 200) {
                    conn.disconnect()
                    session.abandon()
                    return@withContext "Couldn't download the update (error $code). Try again later."
                }
                break
            }
            conn.inputStream.use { input ->
                session.openWrite("StrideBoard.apk", 0, conn.contentLengthLong.takeIf { it > 0 } ?: -1).use { out ->
                    input.copyTo(out)
                    session.fsync(out)
                }
            }
            val intent = Intent(activity, UpdateResultReceiver::class.java).setAction(ACTION_STATUS)
            val flags = PendingIntent.FLAG_UPDATE_CURRENT or
                (if (Build.VERSION.SDK_INT >= 31) PendingIntent.FLAG_MUTABLE else 0)
            session.commit(PendingIntent.getBroadcast(activity, sessionId, intent, flags).intentSender)
            null
        } catch (e: Exception) {
            session.abandon()
            "Couldn't download the update. Check your internet and try again."
        } finally {
            session.close()
        }
    }
}

/** Android reports back here: show its "Update StrideBoard?" box, or say what went wrong. */
class UpdateResultReceiver : BroadcastReceiver() {
    override fun onReceive(c: Context, intent: Intent) {
        when (intent.getIntExtra(PackageInstaller.EXTRA_STATUS, PackageInstaller.STATUS_FAILURE)) {
            PackageInstaller.STATUS_PENDING_USER_ACTION -> {
                val confirm: Intent? = if (Build.VERSION.SDK_INT >= 33)
                    intent.getParcelableExtra(Intent.EXTRA_INTENT, Intent::class.java)
                else @Suppress("DEPRECATION") intent.getParcelableExtra(Intent.EXTRA_INTENT)
                confirm?.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                confirm?.let { c.startActivity(it) }
            }
            PackageInstaller.STATUS_SUCCESS -> Unit   // Android restarts the app on the new version
            PackageInstaller.STATUS_FAILURE_ABORTED -> Unit   // they tapped Cancel
            else -> Toast.makeText(
                c, "The update didn't install: " +
                    (intent.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE) ?: "unknown reason"),
                Toast.LENGTH_LONG
            ).show()
        }
    }
}
