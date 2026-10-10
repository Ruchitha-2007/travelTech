package com.traveltech.app.util

import com.traveltech.app.data.local.HazardZoneEntity
import java.text.SimpleDateFormat
import java.util.*
import kotlin.math.*

object SafetyEngine {

    const val EARTH_RADIUS_KM = 6371.0

    fun haversineDistance(lat1: Double, lon1: Double, lat2: Double, lon2: Double): Double {
        val phi1 = Math.toRadians(lat1)
        val phi2 = Math.toRadians(lat2)
        val deltaPhi = Math.toRadians(lat2 - lat1)
        val deltaLambda = Math.toRadians(lon2 - lon1)

        val a = sin(deltaPhi / 2.0).pow(2) +
                cos(phi1) * cos(phi2) * sin(deltaLambda / 2.0).pow(2)
        val c = 2.0 * atan2(sqrt(a), sqrt(1.0 - a))
        return EARTH_RADIUS_KM * c
    }

    fun isPointInCircle(lat: Double, lon: Double, centerLat: Double, centerLon: Double, radiusKm: Double): Boolean {
        return haversineDistance(lat, lon, centerLat, centerLon) <= radiusKm
    }

    /**
     * ACTIVE-ONLY RULE:
     * Drops expired zones.
     * Evaluates current user point against active zones in offline Room cache.
     */
    fun evaluateOnDeviceSafety(
        userLat: Double,
        userLon: Double,
        zones: List<HazardZoneEntity>,
        nowUtc: Date = Date()
    ): SafetyResult {
        val sdf = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.US).apply {
            timeZone = TimeZone.getTimeZone("UTC")
        }

        var maxSeverity = 1
        val matchedZones = mutableListOf<HazardZoneEntity>()
        val reasons = mutableListOf<String>()

        for (z in zones) {
            try {
                val cleanStart = z.startTime.replace("Z", "").split("+")[0].split(".")[0]
                val cleanEnd = z.endTime.replace("Z", "").split("+")[0].split(".")[0]
                val startDate = sdf.parse(cleanStart)
                val endDate = sdf.parse(cleanEnd)

                if (endDate != null) {
                    // Ignore only past expired zones
                    if (nowUtc.after(endDate)) {
                        continue
                    }
                }
            } catch (e: Exception) {
                // If unparseable, continue
            }

            val dist = haversineDistance(userLat, userLon, z.centerLat, z.centerLon)
            if (dist <= z.radiusKm) {
                matchedZones.add(z)
                reasons.add("Inside ${z.type} zone (${z.source}) of severity ${z.severity}")
                if (z.severity > maxSeverity) {
                    maxSeverity = z.severity
                }
            }
        }

        val status = when {
            maxSeverity >= 3 -> "DANGEROUS"
            maxSeverity == 2 -> "CAUTION"
            else -> "SAFE"
        }

        return SafetyResult(status, maxSeverity, matchedZones, reasons)
    }
}

data class SafetyResult(
    val status: String,
    val maxSeverity: Int,
    val matchedZones: List<HazardZoneEntity>,
    val reasons: List<String>
)
