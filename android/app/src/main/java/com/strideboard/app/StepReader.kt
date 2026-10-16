package com.strideboard.app

import android.content.Context
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.HealthConnectFeatures
import androidx.health.connect.client.permission.HealthPermission
import androidx.health.connect.client.records.StepsRecord
import androidx.health.connect.client.request.AggregateRequest
import androidx.health.connect.client.time.TimeRangeFilter
import java.time.LocalDate
import java.time.ZoneId
import java.time.ZonedDateTime

/** Reads daily step totals from Health Connect. Steps only: nothing else is requested. */
object StepReader {

    /** The server counts days in Dubai time, so the phone does too (even if set to another zone). */
    val DUBAI: ZoneId = ZoneId.of("Asia/Dubai")

    const val PROVIDER_PACKAGE = "com.google.android.apps.healthdata"

    val STEPS_PERMISSION: String = HealthPermission.getReadPermission(StepsRecord::class)
    val BACKGROUND_PERMISSION: String = HealthPermission.PERMISSION_READ_HEALTH_DATA_IN_BACKGROUND

    data class Status(
        val sdkStatus: Int,
        val stepsGranted: Boolean,
        val backgroundSupported: Boolean,
        val backgroundGranted: Boolean,
    ) {
        val available get() = sdkStatus == HealthConnectClient.SDK_AVAILABLE
    }

    data class DayTotal(val date: LocalDate, val steps: Long)

    fun sdkStatus(c: Context): Int = HealthConnectClient.getSdkStatus(c, PROVIDER_PACKAGE)

    private fun backgroundSupported(client: HealthConnectClient): Boolean = try {
        client.features.getFeatureStatus(
            HealthConnectFeatures.FEATURE_READ_HEALTH_DATA_IN_BACKGROUND
        ) == HealthConnectFeatures.FEATURE_STATUS_AVAILABLE
    } catch (e: Exception) {
        false
    }

    /** What to ask the user for: steps, plus background reading where this phone supports it. */
    fun permissionsToRequest(c: Context): Set<String> {
        val client = HealthConnectClient.getOrCreate(c)
        return if (backgroundSupported(client)) setOf(STEPS_PERMISSION, BACKGROUND_PERMISSION)
        else setOf(STEPS_PERMISSION)
    }

    suspend fun status(c: Context): Status {
        val sdk = sdkStatus(c)
        if (sdk != HealthConnectClient.SDK_AVAILABLE) return Status(sdk, false, false, false)
        val client = HealthConnectClient.getOrCreate(c)
        val granted = try {
            client.permissionController.getGrantedPermissions()
        } catch (e: Exception) {
            emptySet()
        }
        val bgSupported = backgroundSupported(client)
        return Status(
            sdkStatus = sdk,
            stepsGranted = STEPS_PERMISSION in granted,
            backgroundSupported = bgSupported,
            backgroundGranted = bgSupported && BACKGROUND_PERMISSION in granted,
        )
    }

    /**
     * Yesterday's and today's totals, with Dubai midnight as the day boundary.
     * aggregate() merges phone + watch + other apps without double counting.
     */
    suspend fun readYesterdayAndToday(c: Context): List<DayTotal> {
        val client = HealthConnectClient.getOrCreate(c)
        val now = ZonedDateTime.now(DUBAI)
        val today = now.toLocalDate()
        return listOf(today.minusDays(1), today).map { day ->
            val start = day.atStartOfDay(DUBAI).toInstant()
            val nextDay = day.plusDays(1).atStartOfDay(DUBAI).toInstant()
            val end = if (nextDay.isAfter(now.toInstant())) now.toInstant() else nextDay
            if (!end.isAfter(start)) {
                DayTotal(day, 0L)
            } else {
                val response = client.aggregate(
                    AggregateRequest(
                        metrics = setOf(StepsRecord.COUNT_TOTAL),
                        timeRangeFilter = TimeRangeFilter.between(start, end),
                    )
                )
                DayTotal(day, response[StepsRecord.COUNT_TOTAL] ?: 0L)
            }
        }
    }
}
