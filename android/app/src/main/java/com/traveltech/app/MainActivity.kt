package com.traveltech.app

import android.Manifest
import android.annotation.SuppressLint
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.media.AudioManager
import android.media.RingtoneManager
import android.media.ToneGenerator
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.util.Log
import android.webkit.*
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import com.traveltech.app.service.LocationForegroundService
import dagger.hilt.android.AndroidEntryPoint

@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    private var vibrator: Vibrator? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        initVibrator()
        createNotificationChannel()
        tryStartLocationService()
        scheduleGeoFenceSync()

        setContent {
            TravelTechAppScreen(
                vibrator = vibrator,
                onStartLocationService = { tryStartLocationService() }
            )
        }
    }

    private fun scheduleGeoFenceSync() {
        try {
            val constraints = androidx.work.Constraints.Builder()
                .setRequiredNetworkType(androidx.work.NetworkType.CONNECTED)
                .build()

            val syncWork = androidx.work.PeriodicWorkRequestBuilder<com.traveltech.app.sync.GeoFenceSyncWorker>(
                6, java.util.concurrent.TimeUnit.HOURS
            ).setConstraints(constraints).build()

            androidx.work.WorkManager.getInstance(applicationContext).enqueueUniquePeriodicWork(
                "GeoFenceSyncWork",
                androidx.work.ExistingPeriodicWorkPolicy.KEEP,
                syncWork
            )
            Log.d("MainActivity", "Proactive GeoFenceSyncWorker scheduled")
        } catch (e: Exception) {
            Log.e("MainActivity", "Failed to schedule GeoFenceSyncWorker", e)
        }
    }

    private fun initVibrator() {
        vibrator = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            val vibratorManager = getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as? VibratorManager
            vibratorManager?.defaultVibrator
        } else {
            @Suppress("DEPRECATION")
            getSystemService(Context.VIBRATOR_SERVICE) as? Vibrator
        }
    }

    private fun tryStartLocationService() {
        val fineGranted = ContextCompat.checkSelfPermission(
            this,
            Manifest.permission.ACCESS_FINE_LOCATION
        ) == PackageManager.PERMISSION_GRANTED

        if (fineGranted) {
            try {
                val serviceIntent = Intent(this, LocationForegroundService::class.java)
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    startForegroundService(serviceIntent)
                } else {
                    startService(serviceIntent)
                }
            } catch (e: Exception) {
                Log.e("MainActivity", "Failed to start LocationForegroundService", e)
            }
        }
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                EMERGENCY_CHANNEL_ID,
                "Emergency Disaster Alerts",
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "High priority alerts for immediate disaster threats and severe weather"
                enableVibration(true)
                vibrationPattern = longArrayOf(0, 600, 200, 600, 200, 600)
            }
            val manager = getSystemService(NotificationManager::class.java)
            manager?.createNotificationChannel(channel)
        }
    }

    companion object {
        const val EMERGENCY_CHANNEL_ID = "channel_emergency_v2"
    }
}

@Composable
fun TravelTechAppScreen(
    vibrator: Vibrator?,
    onStartLocationService: () -> Unit
) {
    val context = LocalContext.current
    var webViewInstance by remember { mutableStateOf<WebView?>(null) }
    var canGoBack by remember { mutableStateOf(false) }

    // Request runtime permissions for GPS location & notifications
    val permissionsToRequest = remember {
        buildList {
            add(Manifest.permission.ACCESS_FINE_LOCATION)
            add(Manifest.permission.ACCESS_COARSE_LOCATION)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                add(Manifest.permission.POST_NOTIFICATIONS)
            }
        }.toTypedArray()
    }

    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        val fineLocation = permissions[Manifest.permission.ACCESS_FINE_LOCATION] ?: false
        if (fineLocation) {
            onStartLocationService()
            webViewInstance?.reload()
        }
    }

    LaunchedEffect(Unit) {
        val fineGranted = ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.ACCESS_FINE_LOCATION
        ) == PackageManager.PERMISSION_GRANTED

        if (!fineGranted) {
            permissionLauncher.launch(permissionsToRequest)
        }
    }

    BackHandler(enabled = canGoBack) {
        webViewInstance?.goBack()
    }

    Box(modifier = Modifier.fillMaxSize()) {
        TravelTechWebView(
            vibrator = vibrator,
            onWebViewCreated = { webViewInstance = it },
            onCanGoBackChanged = { canGoBack = it }
        )
    }
}

@SuppressLint("SetJavaScriptEnabled")
@Composable
fun TravelTechWebView(
    vibrator: Vibrator?,
    onWebViewCreated: (WebView) -> Unit,
    onCanGoBackChanged: (Boolean) -> Unit
) {
    AndroidView(
        modifier = Modifier.fillMaxSize(),
        factory = { ctx ->
            WebView(ctx).apply {
                settings.apply {
                    javaScriptEnabled = true
                    domStorageEnabled = true
                    databaseEnabled = true
                    setGeolocationEnabled(true)
                    mediaPlaybackRequiresUserGesture = false
                    allowFileAccess = true
                    allowContentAccess = true
                    allowFileAccessFromFileURLs = true
                    allowUniversalAccessFromFileURLs = true
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
                        mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
                    }
                    cacheMode = WebSettings.LOAD_DEFAULT
                    builtInZoomControls = false
                    displayZoomControls = false
                }

                webChromeClient = object : WebChromeClient() {
                    override fun onGeolocationPermissionsShowPrompt(
                        origin: String?,
                        callback: GeolocationPermissions.Callback?
                    ) {
                        callback?.invoke(origin, true, false)
                    }

                    override fun onConsoleMessage(consoleMessage: ConsoleMessage?): Boolean {
                        Log.d("TravelTechWebView", "[JS] ${consoleMessage?.message()} (line: ${consoleMessage?.lineNumber()})")
                        return true
                    }
                }

                webViewClient = object : WebViewClient() {
                    override fun onPageFinished(view: WebView?, url: String?) {
                        super.onPageFinished(view, url)
                        onCanGoBackChanged(canGoBack())
                    }

                    override fun onReceivedError(view: WebView?, errorCode: Int, description: String?, failingUrl: String?) {
                        super.onReceivedError(view, errorCode, description, failingUrl)
                        Log.e("TravelTechWebView", "Error $errorCode: $description on $failingUrl")
                    }
                }

                addJavascriptInterface(
                    AndroidBridge(
                        context = ctx,
                        vibrator = vibrator
                    ),
                    "AndroidBridge"
                )

                loadUrl("file:///android_asset/web/index.html")
                onWebViewCreated(this)
            }
        },
        update = { webView ->
            onCanGoBackChanged(webView.canGoBack())
        }
    )
}

class AndroidBridge(
    private val context: Context,
    private val vibrator: Vibrator?
) {
    private var toneGenerator: ToneGenerator? = null

    @JavascriptInterface
    fun getBaseUrl(): String {
        return ""
    }

    @JavascriptInterface
    fun triggerBuzzer(details: String) {
        try {
            val pattern = longArrayOf(0, 800, 200, 800, 200, 800)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                vibrator?.vibrate(VibrationEffect.createWaveform(pattern, -1))
            } else {
                @Suppress("DEPRECATION")
                vibrator?.vibrate(pattern, -1)
            }
        } catch (e: Exception) {
            Log.e("AndroidBridge", "Vibration failed", e)
        }

        // Play loud audible siren tone offline with ToneGenerator / RingtoneManager
        try {
            if (toneGenerator == null) {
                toneGenerator = ToneGenerator(AudioManager.STREAM_ALARM, 100)
            }
            toneGenerator?.startTone(ToneGenerator.TONE_CDMA_EMERGENCY_RINGBACK, 3500)
        } catch (e: Exception) {
            try {
                val alertSound = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM)
                    ?: RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION)
                val ringtone = RingtoneManager.getRingtone(context, alertSound)
                ringtone?.play()
            } catch (ignored: Exception) {}
        }

        showNotification("🚨 Hazard Alert!", details)
    }

    @JavascriptInterface
    fun stopBuzzer() {
        try {
            vibrator?.cancel()
        } catch (e: Exception) {
            Log.e("AndroidBridge", "Stop vibration failed", e)
        }
        try {
            toneGenerator?.stopTone()
            toneGenerator?.release()
            toneGenerator = null
        } catch (e: Exception) {
            Log.e("AndroidBridge", "Stop tone failed", e)
        }
    }

    @JavascriptInterface
    fun showNotification(title: String, message: String) {
        try {
            val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as? NotificationManager
            val notification = NotificationCompat.Builder(context, MainActivity.EMERGENCY_CHANNEL_ID)
                .setSmallIcon(android.R.drawable.ic_dialog_alert)
                .setContentTitle(title)
                .setContentText(message)
                .setStyle(NotificationCompat.BigTextStyle().bigText(message))
                .setPriority(NotificationCompat.PRIORITY_MAX)
                .setDefaults(NotificationCompat.DEFAULT_ALL)
                .setAutoCancel(true)
                .build()
            manager?.notify((System.currentTimeMillis() % 100000).toInt(), notification)
        } catch (e: Exception) {
            Log.e("AndroidBridge", "Notification failed", e)
        }
    }

    @JavascriptInterface
    fun openDialer(phoneNumber: String) {
        try {
            val intent = Intent(Intent.ACTION_DIAL, Uri.parse("tel:$phoneNumber")).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            context.startActivity(intent)
        } catch (e: Exception) {
            Log.e("AndroidBridge", "Dialer failed", e)
        }
    }

    @JavascriptInterface
    fun sendSms(phoneNumber: String, body: String) {
        try {
            val intent = Intent(Intent.ACTION_SENDTO, Uri.parse("smsto:$phoneNumber")).apply {
                putExtra("sms_body", body)
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            context.startActivity(intent)
        } catch (e: Exception) {
            Log.e("AndroidBridge", "SMS failed", e)
        }
    }

    @JavascriptInterface
    fun showToast(message: String) {
        Toast.makeText(context, message, Toast.LENGTH_SHORT).show()
    }

    @JavascriptInterface
    fun cacheGeoFenceTile(tileJson: String) {
        try {
            val file = java.io.File(context.filesDir, "geofence_tile_cache.json")
            file.writeText(tileJson)
            Log.d("AndroidBridge", "Cached geofence tile (${tileJson.length} bytes)")
        } catch (e: Exception) {
            Log.e("AndroidBridge", "Error caching geofence tile", e)
        }
    }

    @JavascriptInterface
    fun getCachedGeoFenceTile(): String {
        return try {
            val file = java.io.File(context.filesDir, "geofence_tile_cache.json")
            if (file.exists()) file.readText() else ""
        } catch (e: Exception) {
            ""
        }
    }
}
