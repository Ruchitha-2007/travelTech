package com.traveltech.app.service

import android.app.*
import android.content.Context
import android.content.Intent
import android.media.AudioAttributes
import android.media.RingtoneManager
import android.os.Build
import android.os.IBinder
import android.os.Looper
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.util.Log
import androidx.core.app.NotificationCompat
import com.google.android.gms.location.*
import com.traveltech.app.AlertActivity
import com.traveltech.app.data.repository.SafetyRepository
import com.traveltech.app.util.SafetyEngine
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import javax.inject.Inject

@AndroidEntryPoint
class LocationForegroundService : Service() {

    @Inject
    lateinit var safetyRepository: SafetyRepository

    private lateinit var fusedLocationClient: FusedLocationProviderClient
    private lateinit var locationCallback: LocationCallback
    private val serviceScope = CoroutineScope(Dispatchers.IO)

    private var lastFetchLat = 0.0
    private var lastFetchLon = 0.0
    private var lastAlertedStatus = "SAFE"

    override fun onCreate() {
        super.onCreate()
        createNotificationChannels()
        startForeground(FOREGROUND_NOTIFICATION_ID, createForegroundNotification("Live radar actively monitoring weather hazards..."))

        fusedLocationClient = LocationServices.getFusedLocationProviderClient(this)

        // Continuous high accuracy background location polling
        val locationRequest = LocationRequest.Builder(Priority.PRIORITY_HIGH_ACCURACY, 5000)
            .setMinUpdateDistanceMeters(50f)
            .build()

        locationCallback = object : LocationCallback() {
            override fun onLocationResult(locationResult: LocationResult) {
                for (location in locationResult.locations) {
                    val lat = location.latitude
                    val lon = location.longitude
                    handleLocationUpdate(lat, lon)
                }
            }
        }

        try {
            fusedLocationClient.requestLocationUpdates(locationRequest, locationCallback, Looper.getMainLooper())
        } catch (e: SecurityException) {
            Log.e("LocationService", "Missing fine location permission", e)
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        return START_STICKY
    }

    private fun playEmergencyBuzzer() {
        try {
            val audioManager = getSystemService(Context.AUDIO_SERVICE) as? android.media.AudioManager
            // Temporarily unmute alarm volume for life-safety hazard warning
            audioManager?.setStreamVolume(
                android.media.AudioManager.STREAM_ALARM,
                audioManager.getStreamMaxVolume(android.media.AudioManager.STREAM_ALARM),
                0
            )
            val alarmSound = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM)
            val ringtone = RingtoneManager.getRingtone(applicationContext, alarmSound)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
                ringtone?.audioAttributes = AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_ALARM)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                    .build()
            }
            ringtone?.play()

            // Continuous emergency vibration pulse
            val pattern = longArrayOf(0, 800, 200, 800, 200, 800)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                val vibratorManager = getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as? VibratorManager
                vibratorManager?.defaultVibrator?.vibrate(VibrationEffect.createWaveform(pattern, -1))
            } else {
                @Suppress("DEPRECATION")
                val vibrator = getSystemService(Context.VIBRATOR_SERVICE) as? Vibrator
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    vibrator?.vibrate(VibrationEffect.createWaveform(pattern, -1))
                } else {
                    @Suppress("DEPRECATION")
                    vibrator?.vibrate(pattern, -1)
                }
            }
        } catch (e: Exception) {
            Log.e("LocationService", "Error playing alarm sound", e)
        }
    }

    private var lastAlertedLocKey = ""

    private fun handleLocationUpdate(lat: Double, lon: Double) {
        serviceScope.launch {
            // Live background weather check from Open-Meteo for real hazards
            var isSevere = false
            var severeReason = ""
            var currentTemp = 28.0

            try {
                val url = java.net.URL("https://api.open-meteo.com/v1/forecast?latitude=$lat&longitude=$lon&current=temperature_2m,precipitation,weather_code,wind_gusts_10m")
                val conn = url.openConnection() as java.net.HttpURLConnection
                conn.connectTimeout = 4000
                conn.readTimeout = 4000
                if (conn.responseCode == 200) {
                    val body = conn.inputStream.bufferedReader().use { it.readText() }
                    val json = org.json.JSONObject(body)
                    val current = json.optJSONObject("current")
                    if (current != null) {
                        currentTemp = current.optDouble("temperature_2m", 28.0)
                        val gusts = current.optDouble("wind_gusts_10m", 0.0)
                        val precip = current.optDouble("precipitation", 0.0)
                        val code = current.optInt("weather_code", 0)

                        if (code in listOf(96, 99)) {
                            isSevere = true
                            severeReason = "Severe Thunderstorm with Hail detected at your location!"
                        } else if (code == 95 && (gusts >= 55.0 || precip >= 30.0)) {
                            isSevere = true
                            severeReason = "Active Thunderstorm with squall winds (${gusts.toInt()} km/h)!"
                        } else if (gusts >= 60.0) {
                            isSevere = true
                            severeReason = "Dangerous Gale Wind Gusts (${gusts.toInt()} km/h) detected!"
                        } else if (precip >= 35.0) {
                            isSevere = true
                            severeReason = "Heavy downpour and localized flooding risk ($precip mm/h)!"
                        }
                    }
                }
            } catch (e: Exception) {
                Log.w("LocationService", "Live background weather check: ${e.message}")
            }

            // Also evaluate offline cached zones if present
            try {
                val cachedZones = safetyRepository.cachedZones.first()
                val eval = SafetyEngine.evaluateOnDeviceSafety(lat, lon, cachedZones)
                if (eval.status == "DANGEROUS") {
                    isSevere = true
                    severeReason = eval.reasons.joinToString("\n")
                }
            } catch (e: Exception) {
                // Ignore cache read failures
            }

            val locKey = "${(lat * 100).toInt()}_${(lon * 100).toInt()}"

            if (isSevere) {
                // Only alert once for this hazard location
                if (lastAlertedLocKey != locKey) {
                    lastAlertedLocKey = locKey
                    playEmergencyBuzzer()
                    postEmergencyNotification("DANGEROUS", severeReason)
                    launchFullScreenAlert("DANGEROUS", severeReason)
                }
            } else {
                if (lastAlertedLocKey.isNotEmpty()) {
                    lastAlertedLocKey = ""
                    postAllClearNotification()
                }
                // Update persistent foreground notification with live calm weather status
                val manager = getSystemService(NotificationManager::class.java)
                val notif = createForegroundNotification("Live radar active: Safe & calm conditions (${currentTemp.toInt()}°C).")
                manager?.notify(FOREGROUND_NOTIFICATION_ID, notif)
            }
        }
    }

    private fun postEmergencyNotification(status: String, details: String) {
        val intent = Intent(this, AlertActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            putExtra("EXTRA_STATUS", status)
            putExtra("EXTRA_DETAILS", details)
        }
        val pendingIntent = PendingIntent.getActivity(
            this, 0, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val alarmSound = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM)
        val vibrationPattern = longArrayOf(0, 1000, 300, 1000, 300, 1000)

        val notification = NotificationCompat.Builder(this, EMERGENCY_CHANNEL_ID)
            .setContentTitle("🚨 CRITICAL WEATHER HAZARD DETECTED")
            .setContentText(details)
            .setStyle(NotificationCompat.BigTextStyle().bigText(details))
            .setSmallIcon(android.R.drawable.ic_dialog_alert)
            .setPriority(NotificationCompat.PRIORITY_MAX)
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .setSound(alarmSound)
            .setVibrate(vibrationPattern)
            .setFullScreenIntent(pendingIntent, true)
            .setContentIntent(pendingIntent)
            .setAutoCancel(true)
            .build()

        val manager = getSystemService(NotificationManager::class.java)
        manager?.notify(EMERGENCY_NOTIFICATION_ID, notification)
    }

    private fun postAllClearNotification() {
        val notification = NotificationCompat.Builder(this, FOREGROUND_CHANNEL_ID)
            .setContentTitle("✅ ALL CLEAR: Exited Hazard Zone")
            .setContentText("You have moved safely out of the weather danger area.")
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)
            .setAutoCancel(true)
            .build()

        val manager = getSystemService(NotificationManager::class.java)
        manager?.notify(ALL_CLEAR_NOTIFICATION_ID, notification)
    }

    private fun launchFullScreenAlert(status: String, details: String) {
        val intent = Intent(this, AlertActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            putExtra("EXTRA_STATUS", status)
            putExtra("EXTRA_DETAILS", details)
        }
        startActivity(intent)
    }

    private fun createForegroundNotification(contentText: String): Notification {
        return NotificationCompat.Builder(this, FOREGROUND_CHANNEL_ID)
            .setContentTitle("TravelTech Crisis Radar")
            .setContentText(contentText)
            .setSmallIcon(android.R.drawable.ic_dialog_alert)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
    }

    private fun createNotificationChannels() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val audioAttributes = AudioAttributes.Builder()
                .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                .setUsage(AudioAttributes.USAGE_ALARM)
                .build()
            val alarmSound = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM)

            val emergencyChannel = NotificationChannel(
                EMERGENCY_CHANNEL_ID,
                "Emergency Hazard Alarms",
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "High priority alarms with loud buzzer and vibration when in danger"
                setSound(alarmSound, audioAttributes)
                enableVibration(true)
                vibrationPattern = longArrayOf(0, 1000, 300, 1000, 300, 1000)
                lockscreenVisibility = Notification.VISIBILITY_PUBLIC
            }

            val foregroundChannel = NotificationChannel(
                FOREGROUND_CHANNEL_ID,
                "TravelTech Live Radar Status",
                NotificationManager.IMPORTANCE_LOW
            )

            val manager = getSystemService(NotificationManager::class.java)
            manager?.createNotificationChannel(emergencyChannel)
            manager?.createNotificationChannel(foregroundChannel)
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        fusedLocationClient.removeLocationUpdates(locationCallback)
    }

    override fun onBind(intent: Intent?): IBinder? = null

    companion object {
        const val FOREGROUND_CHANNEL_ID = "traveltech_radar_channel"
        const val EMERGENCY_CHANNEL_ID = "traveltech_emergency_alarm_channel"
        const val FOREGROUND_NOTIFICATION_ID = 101
        const val EMERGENCY_NOTIFICATION_ID = 202
        const val ALL_CLEAR_NOTIFICATION_ID = 203
    }
}
