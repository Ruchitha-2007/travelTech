package com.traveltech.app.data.remote

import com.google.gson.annotations.SerializedName
import retrofit2.Response
import retrofit2.http.*

data class RegisterRequest(
    val device_id: String,
    val language: String,
    val country: String,
    val emergency_contacts: List<Map<String, String>>
)

data class LocationUpdateRequest(
    val device_id: String,
    val lat: Double,
    val lon: Double
)

data class SafetyCheckRequest(
    val lat: Double,
    val lon: Double
)

data class RouteSafeRequest(
    val origin: List<Double>,
    val destination: List<Double>,
    val profile: String = "driving-car"
)

data class SOSRequest(
    val device_id: String,
    val lat: Double,
    val lon: Double
)

data class HazardDto(
    val id: String,
    val type: String,
    val severity: Int,
    @SerializedName("center_lat") val centerLat: Double,
    @SerializedName("center_lon") val centerLon: Double,
    @SerializedName("radius_km") val radiusKm: Double,
    @SerializedName("start_time") val startTime: String,
    @SerializedName("end_time") val endTime: String,
    val source: String,
    @SerializedName("source_url") val sourceUrl: String?,
    @SerializedName("message_key") val messageKey: String,
    val verified: Boolean
)

data class NearbyHazardsResponse(
    val count: Int,
    val hazards: List<HazardDto>,
    @SerializedName("checked_at") val checkedAt: String
)

data class SafetyCheckResponse(
    val status: String, // SAFE, CAUTION, DANGEROUS
    val zones: List<HazardDto>,
    val reasons: List<String>,
    val message: String,
    @SerializedName("nearest_shelter") val nearestShelter: Map<String, Any>?,
    @SerializedName("is_stale") val isStale: Boolean
)

data class RouteSafeResponse(
    val status: String, // SAFE, REROUTED, UNREACHABLE, ORIGIN_UNSAFE, DESTINATION_UNSAFE
    val message: String,
    val routes: List<Map<String, Any>>,
    @SerializedName("hazards_on_route") val hazardsOnRoute: List<Map<String, Any>>
)

interface ApiService {
    @POST("/api/device/register")
    suspend fun registerDevice(@Body body: RegisterRequest): Response<Map<String, Any>>

    @POST("/api/location/update")
    suspend fun updateLocation(@Body body: LocationUpdateRequest): Response<Map<String, Any>>

    @POST("/api/safety/check")
    suspend fun checkSafety(
        @Body body: SafetyCheckRequest,
        @Query("lang") lang: String
    ): Response<SafetyCheckResponse>

    @GET("/api/hazards/nearby")
    suspend fun getNearbyHazards(
        @Query("lat") lat: Double,
        @Query("lon") lon: Double,
        @Query("radius_km") radiusKm: Double = 50.0
    ): Response<NearbyHazardsResponse>

    @POST("/api/route/safe")
    suspend fun getSafeRoute(
        @Body body: RouteSafeRequest,
        @Query("lang") lang: String
    ): Response<RouteSafeResponse>

    @GET("/api/shelters/nearby")
    suspend fun getNearbyShelters(
        @Query("lat") lat: Double,
        @Query("lon") lon: Double,
        @Query("type") type: String = "shelter"
    ): Response<Map<String, Any>>

    @GET("/api/places/search")
    suspend fun searchPlaces(
        @Query("q") query: String,
        @Query("lang") lang: String
    ): Response<Map<String, Any>>

    @POST("/api/sos")
    suspend fun triggerSOS(@Body body: SOSRequest): Response<Map<String, Any>>

    @GET("/api/emergency-numbers")
    suspend fun getEmergencyNumbers(@Query("country") country: String): Response<Map<String, Any>>
}
