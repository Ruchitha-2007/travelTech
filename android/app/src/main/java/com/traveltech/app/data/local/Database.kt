package com.traveltech.app.data.local

import androidx.room.*
import kotlinx.coroutines.flow.Flow

@Entity(tableName = "hazard_zones")
data class HazardZoneEntity(
    @PrimaryKey val id: String,
    val type: String,
    val severity: Int,
    val centerLat: Double,
    val centerLon: Double,
    val radiusKm: Double,
    val startTime: String, // ISO UTC
    val endTime: String,   // ISO UTC
    val source: String,
    val sourceUrl: String?,
    val messageKey: String,
    val verified: Boolean
)

@Entity(tableName = "shelters")
data class ShelterEntity(
    @PrimaryKey val id: String,
    val name: String,
    val type: String,
    val lat: Double,
    val lon: Double,
    val distanceKm: Double,
    val phone: String?,
    val address: String?
)

@Dao
interface HazardDao {
    @Query("SELECT * FROM hazard_zones")
    fun getAllZones(): Flow<List<HazardZoneEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertZones(zones: List<HazardZoneEntity>)

    @Query("DELETE FROM hazard_zones WHERE id = :id")
    suspend fun deleteZone(id: String)

    @Query("DELETE FROM hazard_zones")
    suspend fun clearAll()
}

@Dao
interface ShelterDao {
    @Query("SELECT * FROM shelters ORDER BY distanceKm ASC")
    fun getShelters(): Flow<List<ShelterEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertShelters(shelters: List<ShelterEntity>)

    @Query("DELETE FROM shelters")
    suspend fun clearShelters()
}

@Database(entities = [HazardZoneEntity::class, ShelterEntity::class], version = 1, exportSchema = false)
abstract class AppDatabase : RoomDatabase() {
    abstract fun hazardDao(): HazardDao
    abstract fun shelterDao(): ShelterDao
}
