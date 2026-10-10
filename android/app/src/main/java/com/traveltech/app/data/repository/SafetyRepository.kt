package com.traveltech.app.data.repository

import com.traveltech.app.data.local.HazardDao
import com.traveltech.app.data.local.HazardZoneEntity
import com.traveltech.app.data.local.ShelterDao
import com.traveltech.app.data.local.ShelterEntity
import com.traveltech.app.data.remote.*
import kotlinx.coroutines.flow.Flow
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class SafetyRepository @Inject constructor(
    private val api: ApiService,
    private val hazardDao: HazardDao,
    private val shelterDao: ShelterDao
) {
    val cachedZones: Flow<List<HazardZoneEntity>> = hazardDao.getAllZones()
    val cachedShelters: Flow<List<ShelterEntity>> = shelterDao.getShelters()

    suspend fun registerDevice(deviceId: String, lang: String, country: String, contacts: List<Map<String, String>>) {
        try {
            api.registerDevice(RegisterRequest(deviceId, lang, country, contacts))
        } catch (e: Exception) {
            // Offline fallback
        }
    }

    suspend fun updateLocation(deviceId: String, lat: Double, lon: Double): Result<Map<String, Any>> {
        return try {
            val resp = api.updateLocation(LocationUpdateRequest(deviceId, lat, lon))
            if (resp.isSuccessful && resp.body() != null) {
                Result.success(resp.body()!!)
            } else {
                Result.failure(Exception("Server returned ${resp.code()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun refreshNearbyHazards(lat: Double, lon: Double, radiusKm: Double = 50.0): Result<List<HazardZoneEntity>> {
        return try {
            val resp = api.getNearbyHazards(lat, lon, radiusKm)
            if (resp.isSuccessful && resp.body() != null) {
                val entities = resp.body()!!.hazards.map { dto ->
                    HazardZoneEntity(
                        id = dto.id,
                        type = dto.type,
                        severity = dto.severity,
                        centerLat = dto.centerLat,
                        centerLon = dto.centerLon,
                        radiusKm = dto.radiusKm,
                        startTime = dto.startTime,
                        endTime = dto.endTime,
                        source = dto.source,
                        sourceUrl = dto.sourceUrl,
                        messageKey = dto.messageKey,
                        verified = dto.verified
                    )
                }
                hazardDao.clearAll()
                hazardDao.insertZones(entities)
                Result.success(entities)
            } else {
                Result.failure(Exception("Failed to fetch hazards"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun checkDestinationSafety(lat: Double, lon: Double, lang: String): Result<SafetyCheckResponse> {
        return try {
            val resp = api.checkSafety(SafetyCheckRequest(lat, lon), lang)
            if (resp.isSuccessful && resp.body() != null) {
                Result.success(resp.body()!!)
            } else {
                Result.failure(Exception("Failed destination check"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getSafeRoute(origLat: Double, origLon: Double, destLat: Double, destLon: Double, lang: String): Result<RouteSafeResponse> {
        return try {
            val resp = api.getSafeRoute(RouteSafeRequest(listOf(origLat, origLon), listOf(destLat, destLon)), lang)
            if (resp.isSuccessful && resp.body() != null) {
                Result.success(resp.body()!!)
            } else {
                Result.failure(Exception("Failed safe route"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun triggerSOS(deviceId: String, lat: Double, lon: Double): Result<Map<String, Any>> {
        return try {
            val resp = api.triggerSOS(SOSRequest(deviceId, lat, lon))
            if (resp.isSuccessful && resp.body() != null) {
                Result.success(resp.body()!!)
            } else {
                Result.failure(Exception("Failed SOS"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
