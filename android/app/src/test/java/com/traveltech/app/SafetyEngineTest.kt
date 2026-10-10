package com.traveltech.app

import com.traveltech.app.data.local.HazardZoneEntity
import com.traveltech.app.util.SafetyEngine
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.text.SimpleDateFormat
import java.util.*

class SafetyEngineTest {

    @Test
    fun testHaversineDistanceAccuracy() {
        val centralLat = 13.0827
        val centralLon = 80.2707
        val marinaLat = 13.0500
        val marinaLon = 80.2824

        val dist = SafetyEngine.haversineDistance(centralLat, centralLon, marinaLat, marinaLon)
        // Marina Beach is roughly 3.8 to 4.2 km from Chennai Central
        assertTrue("Distance should be around 4 km", dist in 3.5..4.5)
    }

    @Test
    fun testEvaluateOnDeviceSafetyDangerousClassification() {
        val sdf = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.US).apply {
            timeZone = TimeZone.getTimeZone("UTC")
        }
        val now = Date()
        val oneHourAgo = Date(now.time - 3600 * 1000)
        val twoHoursLater = Date(now.time + 7200 * 1000)

        val floodZone = HazardZoneEntity(
            id = "hz_test_1",
            type = "FLOOD",
            severity = 3,
            centerLat = 13.0827,
            centerLon = 80.2707,
            radiusKm = 5.0,
            startTime = sdf.format(oneHourAgo),
            endTime = sdf.format(twoHoursLater),
            source = "Admin",
            sourceUrl = null,
            messageKey = "flood_warning",
            verified = true
        )

        val result = SafetyEngine.evaluateOnDeviceSafety(13.0827, 80.2707, listOf(floodZone), now)
        assertEquals("DANGEROUS", result.status)
        assertEquals(1, result.matchedZones.size)
    }

    @Test
    fun testExpiredZoneIgnoredInOfflineEvaluation() {
        val sdf = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.US).apply {
            timeZone = TimeZone.getTimeZone("UTC")
        }
        val now = Date()
        val fiveHoursAgo = Date(now.time - 5 * 3600 * 1000)
        val oneHourAgo = Date(now.time - 3600 * 1000)

        // Expired zone
        val expiredZone = HazardZoneEntity(
            id = "hz_expired",
            type = "CYCLONE",
            severity = 4,
            centerLat = 13.0827,
            centerLon = 80.2707,
            radiusKm = 10.0,
            startTime = sdf.format(fiveHoursAgo),
            endTime = sdf.format(oneHourAgo),
            source = "GDACS",
            sourceUrl = null,
            messageKey = "cyclone_warning",
            verified = true
        )

        val result = SafetyEngine.evaluateOnDeviceSafety(13.0827, 80.2707, listOf(expiredZone), now)
        assertEquals("SAFE", result.status)
        assertEquals(0, result.matchedZones.size)
    }
}
