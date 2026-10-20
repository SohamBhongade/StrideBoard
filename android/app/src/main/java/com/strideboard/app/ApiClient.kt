package com.strideboard.app

import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL

/** What the server said about one upload. */
sealed class ApiResult {
    data class Ok(val weeklyTotal: Long?, val tier: String?) : ApiResult()
    /** 400 and other "don't retry" answers, with a readable reason. */
    data class Rejected(val message: String) : ApiResult()
    /** 401: the token is wrong. */
    data object BadToken : ApiResult()
    /** No connection, timeout or a server error: worth trying again later. */
    data class TryLater(val message: String) : ApiResult()
}

/**
 * Sends one day's total to POST {server}/api/steps, exactly as the shared brief describes:
 * {"token": "...", "date": "YYYY-MM-DD", "steps": 8423, "source": "android_app"}
 * Blocking: call it from a background thread (SyncRunner does).
 */
object ApiClient {
    const val SOURCE = "android_app"

    fun postSteps(server: String, token: String, date: String, steps: Long): ApiResult {
        val body = JSONObject()
            .put("token", token)
            .put("date", date)
            .put("steps", steps)
            .put("source", SOURCE)
            .toString()

        var conn: HttpURLConnection? = null
        try {
            conn = (URL("$server/api/steps").openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = 15_000
                readTimeout = 20_000
                doOutput = true
                setRequestProperty("Content-Type", "application/json; charset=utf-8")
                setRequestProperty("Accept", "application/json")
            }
            conn.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }

            val code = conn.responseCode
            val stream = if (code >= 400) conn.errorStream else conn.inputStream
            val text = stream?.bufferedReader()?.use { it.readText() } ?: ""
            val json = try { JSONObject(text) } catch (e: Exception) { null }
            val error = json?.optString("error")?.takeIf { it.isNotBlank() }

            return when {
                code == 200 && json != null && json.optBoolean("ok") -> ApiResult.Ok(
                    weeklyTotal = if (json.has("weekly_total")) json.optLong("weekly_total") else null,
                    tier = json.optString("tier").takeIf { it.isNotBlank() },
                )
                code == 200 -> ApiResult.Rejected("Unexpected answer from the website. Is the address right?")
                code == 401 -> ApiResult.BadToken
                code == 400 -> ApiResult.Rejected(error ?: "The website refused this entry.")
                code == 413 -> ApiResult.Rejected(error ?: "request is too large")
                code == 404 -> ApiResult.Rejected("Website address not found (404). Check it on this screen.")
                code == 429 || code >= 500 -> ApiResult.TryLater("website error $code")
                else -> ApiResult.Rejected(error ?: "Website answered with code $code.")
            }
        } catch (e: IOException) {
            conn?.disconnect()   // a broken connection must not be reused
            val msg = e.message ?: ""
            if (msg.contains("Cleartext", ignoreCase = true)) {
                return ApiResult.Rejected("This app only talks to https:// addresses.")
            }
            return ApiResult.TryLater("no connection")
        }
        // No disconnect() after a good answer: the response was read to the end, so Android
        // keeps the connection open and the next upload skips the slow HTTPS handshake.
    }
}
