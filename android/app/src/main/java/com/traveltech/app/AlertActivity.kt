package com.traveltech.app

import android.app.KeyguardManager
import android.content.Context
import android.media.AudioAttributes
import android.media.AudioManager
import android.media.RingtoneManager
import android.media.ToneGenerator
import android.os.Build
import android.os.Bundle
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.traveltech.app.ui.theme.*

class AlertActivity : ComponentActivity() {

    private var toneGenerator: ToneGenerator? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // 1. Wake screen and turn on over lock screen
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O_MR1) {
            setShowWhenLocked(true)
            setTurnScreenOn(true)
            val keyguardManager = getSystemService(Context.KEYGUARD_SERVICE) as KeyguardManager
            keyguardManager.requestDismissKeyguard(this, null)
        } else {
            @Suppress("DEPRECATION")
            window.addFlags(
                WindowManager.LayoutParams.FLAG_DISMISS_KEYGUARD or
                        WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED or
                        WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON
            )
        }

        // 2. Play High-Pitch Buzzer Alarm Tone
        try {
            toneGenerator = ToneGenerator(AudioManager.STREAM_ALARM, 100)
            toneGenerator?.startTone(ToneGenerator.TONE_CDMA_EMERGENCY_RINGBACK, 3000)
        } catch (e: Exception) {
            // Fallback to default alarm ringtone
            try {
                val alertSound = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM)
                val ringtone = RingtoneManager.getRingtone(applicationContext, alertSound)
                ringtone?.play()
            } catch (e2: Exception) {
                // Ignore
            }
        }

        // 3. Continuous Emergency Vibration Pattern (Buzzer Pulse)
        try {
            val pattern = longArrayOf(0, 800, 200, 800, 200, 800)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                val vibratorManager = getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as VibratorManager
                vibratorManager.defaultVibrator.vibrate(VibrationEffect.createWaveform(pattern, -1))
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
            // Ignore
        }

        val status = intent.getStringExtra("EXTRA_STATUS") ?: "DANGEROUS"
        val details = intent.getStringExtra("EXTRA_DETAILS") ?: "Severe weather hazard reported at your location."

        setContent {
            FullScreenAlertScreen(
                status = status,
                details = details,
                onDismiss = {
                    stopBuzzerTone()
                    finish()
                },
                onNavigateShelter = {
                    stopBuzzerTone()
                    finish()
                }
            )
        }
    }

    private fun stopBuzzerTone() {
        try {
            toneGenerator?.stopTone()
            toneGenerator?.release()
            toneGenerator = null
        } catch (e: Exception) {
            // Ignore
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        stopBuzzerTone()
    }
}

@Composable
fun FullScreenAlertScreen(
    status: String,
    details: String,
    onDismiss: () -> Unit,
    onNavigateShelter: () -> Unit
) {
    val isDanger = status == "DANGEROUS"
    val bannerBg = if (isDanger) BadgeDangerBg else BadgeCautionBg
    val bannerText = if (isDanger) BadgeDangerText else BadgeCautionText

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(CanvasSkyBlue)
            .padding(24.dp),
        contentAlignment = Alignment.Center
    ) {
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(16.dp),
            colors = CardDefaults.cardColors(containerColor = CardWhite),
            elevation = CardDefaults.cardElevation(8.dp)
        ) {
            Column(
                modifier = Modifier.padding(24.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                // Hazard Badge
                Box(
                    modifier = Modifier
                        .background(bannerBg, RoundedCornerShape(20.dp))
                        .padding(horizontal = 16.dp, vertical = 6.dp)
                ) {
                    Text(
                        text = if (isDanger) "🚨 CRITICAL HAZARD ALERT: DANGER" else "⚠️ WEATHER ADVISORY: CAUTION",
                        color = bannerText,
                        fontWeight = FontWeight.Bold,
                        fontSize = 13.sp
                    )
                }

                Spacer(modifier = Modifier.height(16.dp))

                Text(
                    text = "Severe Weather Hazard Zone",
                    fontSize = 20.sp,
                    fontWeight = FontWeight.Bold,
                    color = TextHeadingSlate
                )

                Spacer(modifier = Modifier.height(12.dp))

                Text(
                    text = details,
                    fontSize = 14.sp,
                    color = TextSecondaryMuted,
                    lineHeight = 20.sp
                )

                Spacer(modifier = Modifier.height(24.dp))

                // Actions
                Button(
                    onClick = onNavigateShelter,
                    modifier = Modifier.fillMaxWidth(),
                    colors = ButtonDefaults.buttonColors(containerColor = CobaltBluePrimary),
                    shape = RoundedCornerShape(8.dp)
                ) {
                    Text("Navigate to Safe Shelter", fontWeight = FontWeight.Bold, color = Color.White)
                }

                Spacer(modifier = Modifier.height(12.dp))

                OutlinedButton(
                    onClick = onDismiss,
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(8.dp)
                ) {
                    Text("Silence Buzzer & Dismiss", color = TextHeadingSlate)
                }
            }
        }
    }
}
